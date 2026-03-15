# QA Agent - AI Agent Design

## Overview

The AI Agent is the core reasoning component that interprets human-written test cases and translates them into browser automation actions. It uses LLM models (OpenAI GPT-4o by default, any provider via LiteLLM) in a tool-use loop, invoking Playwright MCP server tools to control the browser.

---

## 1. Agent Architecture

```
┌───────────────────────────────────────────────────┐
│                  Agent Runner                      │
│                                                    │
│  ┌──────────────────────────────────────────────┐ │
│  │           System Prompt Builder               │ │
│  │  Base rules + Custom prompt + Test context    │ │
│  └──────────────────────────────────────────────┘ │
│                                                    │
│  ┌──────────────────────────────────────────────┐ │
│  │           Message Loop                        │ │
│  │                                               │ │
│  │  User message (test case + steps)             │ │
│  │       ↓                                       │ │
│  │  LLM response (tool_calls or stop)             │ │
│  │       ↓                                       │ │
│  │  Tool execution via MCP                       │ │
│  │       ↓                                       │ │
│  │  Tool result → back to LLM                    │ │
│  │       ↓                                       │ │
│  │  Repeat until stop                             │ │
│  └──────────────────────────────────────────────┘ │
│                                                    │
│  ┌──────────────────────────────────────────────┐ │
│  │           Status Reporter                     │ │
│  │  WebSocket callbacks per step/action          │ │
│  └──────────────────────────────────────────────┘ │
│                                                    │
│  ┌──────────────────────────────────────────────┐ │
│  │           Artifact Collector                   │ │
│  │  Screenshots, video path, downloads           │ │
│  └──────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────┘
```

---

## 2. System Prompt Design

The system prompt is built in layers, each adding specific context:

### Layer 1: Base Identity & Rules

```
You are a QA testing agent that executes test cases on web applications by
controlling a browser. You follow test steps precisely, observe the results,
and report outcomes accurately.

RULES:
1. Execute test steps in the order given. Do not skip steps.
2. After EVERY browser action, examine the accessibility snapshot returned
   in the tool result to verify the action succeeded.
3. If an element cannot be found:
   - First, check if the page has finished loading (look for loading indicators)
   - Try alternative selectors: by text content, by role, by aria-label
   - Scroll the page to look for the element
   - Wait up to 10 seconds for dynamic content
   - After 3 failed attempts, mark the step as FAILED
4. Use semantic selectors whenever possible:
   - text="Login" for buttons/links with visible text
   - role=button[name="Submit"] for role-based selection
   - label="Email" for form fields
   - placeholder="Search..." for inputs
5. For file uploads, use the file paths provided in the test configuration.
6. When a step says "verify" or "check", examine the page content to confirm
   the expected state. Report PASS if confirmed, FAIL if not.
7. Always wait for page transitions to complete before proceeding.
8. If the page crashes or shows an error:
   - Attempt to reload the page
   - If reload fails, navigate back to the application URL
   - Maximum 3 recovery attempts before failing the test case

OUTPUT FORMAT:
When you have completed all steps (or determined the test has failed),
provide a final summary in this format:

TEST RESULT: [PASSED/FAILED]
STEPS COMPLETED: X/Y
SUMMARY: Brief description of what happened
FAILURE REASON: (if failed) Description of what went wrong
```

### Layer 2: Custom System Prompt

User-provided text appended directly. Examples:

- "Always log in using the admin credentials before starting any test"
- "The application has a slow API, always wait at least 5 seconds after form submissions"
- "Navigate using the sidebar menu, not direct URLs"

### Layer 3: Test Context

```
APPLICATION UNDER TEST:
  URL: https://staging.example.com
  Login Credentials:
    Username: admin@example.com
    Password: ********

TEST CASE:
  ID: TC-001
  Title: Login with valid credentials
  Steps:
    1. Navigate to the login page
    2. Enter the username in the email field
    3. Enter the password in the password field
    4. Click the "Login" button
    5. Verify that the dashboard page is displayed with a welcome message

TEST-SPECIFIC CONFIGURATION:
  expected_dashboard_title: "Admin Dashboard"

AVAILABLE FILES FOR UPLOAD:
  - invoice.pdf (from /Users/user/test-files/)
  - sample_data.csv (from /Users/user/test-files/)
  - profile_photo.jpg (from /Users/user/test-files/)
```

---

## 3. Tool Result Processing

### What the Agent Receives After Each Action

When the agent calls a Playwright MCP tool, the result contains:

```json
{
  "screenshot_path": "/exports/session_123/tc_001/screenshots/003_click_login.png",
  "page_url": "https://staging.example.com/dashboard",
  "page_title": "Admin Dashboard - MyApp",
  "accessibility_snapshot": "document 'Admin Dashboard - MyApp'\n  navigation 'Main Menu'\n    link 'Home'\n    link 'Orders'\n    link 'Settings'\n  heading 'Welcome, Admin'\n  region 'Dashboard Stats'\n    text 'Total Orders: 145'\n    text 'Revenue: $12,340'\n  ...",
  "success": true,
  "error": null
}
```

### Token-Efficient Response Building

```python
def build_tool_result_content(result, include_image=False):
    """Build the content for a tool result message sent back to the LLM."""
    content = []

    # Always include text-based observation (cheap in tokens)
    text_observation = (
        f"Action completed successfully.\n"
        f"Current URL: {result['page_url']}\n"
        f"Page title: {result['page_title']}\n\n"
        f"Page accessibility snapshot:\n{result['accessibility_snapshot']}"
    )
    content.append({"type": "text", "text": text_observation})

    # Optionally include screenshot as image (expensive in tokens)
    if include_image and result.get("screenshot_base64"):
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{result['screenshot_base64']}",
            }
        })

    return content


def should_include_image(tool_call) -> bool:
    """Decide whether to include the screenshot image in the LLM's context.

    We include the image when:
    1. The action is take_screenshot (explicit request)
    2. The action failed (agent needs to diagnose visually)
    3. This is the first navigation (agent sees the initial page)
    4. Every N steps for periodic visual verification (e.g., every 5th action)
    """
    if tool_call.name == "take_screenshot":
        return True
    if tool_call.name == "navigate" and is_first_navigation:
        return True
    if step_counter % 5 == 0:  # Periodic visual check
        return True
    return False
```

---

## 4. Selector Strategy

The agent doesn't have pre-defined selectors. It must figure out how to interact with elements based on:

1. **Test step description**: "Click the Login button" → the agent looks for a button with text "Login"
2. **Accessibility snapshot**: The structured tree showing all interactive elements with their roles, names, and states
3. **Contextual reasoning**: If "Enter username" but there's no field labeled "username", look for "email", "user", etc.

### Selector Priority Order

The agent is instructed to try selectors in this order:

1. **Text content**: `text=Login`, `text=Submit Order`
2. **Role + name**: `role=button[name="Login"]`, `role=textbox[name="Email"]`
3. **Label**: `label=Email Address`, `label=Password`
4. **Placeholder**: `placeholder=Enter your email`
5. **Test ID / aria**: `[data-testid="login-btn"]`, `[aria-label="Close dialog"]`
6. **CSS selector**: `button.submit-btn`, `input#email` (last resort)

### Handling Ambiguity

When the test step is vague (e.g., "Fill in the form"), the agent:
1. Gets the accessibility snapshot to see all form fields
2. Matches field labels to config values or reasonable defaults
3. Fills fields in DOM order
4. Reports what it filled in the step result

---

## 5. Conversation Management

### Message History Structure

```
System: [Full system prompt with test context]

User: "Execute the test case. Begin by navigating to https://staging.example.com..."