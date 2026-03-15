# QA Agent - AI Agent Design

## Overview

The AI Agent is the core reasoning component that interprets human-written test cases and translates them into browser automation actions. It uses LLM models (OpenAI GPT-4o by default, any provider via LiteLLM) in a tool-use loop, invoking Playwright MCP server tools to control the browser.

---

## 1. Agent Architecture

```
+---------------------------------------------------+
|                  Agent Runner                      |
|                                                    |
|  +----------------------------------------------+ |
|  |           System Prompt Builder               | |
|  |  BASE_SYSTEM_PROMPT + Custom prompt           | |
|  |  + Test context + Config + Available files    | |
|  +----------------------------------------------+ |
|                                                    |
|  +----------------------------------------------+ |
|  |           Message Loop                        | |
|  |                                               | |
|  |  System message (full prompt)                 | |
|  |  User message (test case + steps)             | |
|  |       |                                       | |
|  |  LLM response (tool_calls or stop)            | |
|  |       |                                       | |
|  |  _broadcast_step("executing")                 | |
|  |  Tool execution via MCP                       | |
|  |  _broadcast_step("passed"/"failed")           | |
|  |  _build_tool_result_content() -> back to LLM  | |
|  |       |                                       | |
|  |  Repeat until stop (max 75 iterations)        | |
|  +----------------------------------------------+ |
|                                                    |
|  +----------------------------------------------+ |
|  |           Status Reporter                     | |
|  |  _broadcast_step() -> step_update messages    | |
|  |  status_callback  -> test_status messages     | |
|  |  Both sent with proper "type" field           | |
|  +----------------------------------------------+ |
|                                                    |
|  +----------------------------------------------+ |
|  |           Artifact Collector                  | |
|  |  Screenshots, video path, downloads           | |
|  +----------------------------------------------+ |
+---------------------------------------------------+
```

### `_broadcast_step()` Helper

The agent includes an internal `_broadcast_step()` async function that sends typed WebSocket messages through the `status_callback`. Each call produces a `step_update` message with fields: `type`, `test_id`, `step_index`, `action`, `action_detail`, `status`, `step_description`, `timestamp`, and `error`. This helper is used to report:

- **"executing"** status before a tool call runs
- **"passed"/"failed"** status after the tool call completes
- **"info"** status for LLM reasoning/thinking text
- **"failed"** status for LLM API errors

The agent also sends **`test_status`** messages separately (not through `_broadcast_step`) to report the overall test-level progress: current step number, total steps, last action, and running status.

---

## 2. Agent Function Signature

```python
async def execute_test_case(
    test_case: dict,               # Dict with id, title, steps, expected_result, etc.
    config: dict[str, Any],        # Merged config dict (global + test-specific)
    model: str,                    # LiteLLM model identifier (e.g., "gpt-4o")
    playwright_mcp: MCPClient,     # Started MCP client for Playwright browser
    export_dir: str,               # Path to this test case's export directory
    custom_prompt: str = "",       # User-provided system prompt addition
    upload_folder: str | None = None,  # Path to folder with files for upload
    status_callback: Callable | None = None,  # Async callable for WebSocket updates
    browser_type: str = "chromium",    # Browser engine name
    executable_path: str = "",         # Path to custom browser executable
) -> TestResult:
```

### Return Type

```python
class TestResult(BaseModel):
    test_id: str
    test_title: str
    status: Literal["passed", "failed", "skipped", "error"]
    steps: list[StepResult]     # Per-action results
    summary: str                # LLM's final output text
    duration_ms: int
    video_path: str | None
    retry_count: int = 0
    browser: str = "chromium"
```

---

## 3. Key Agent Behaviors

### Browser Launch

The agent launches the browser at the start of execution with the specified `browser_type` and optional `executable_path` for custom/enterprise browsers. Launch arguments include headless mode, screenshot directory, video directory, and download directory. If the browser fails to launch, the agent returns immediately with an `"error"` status TestResult.

### Prompt Construction

The system prompt is built via `prompt_builder.py` using `build_system_prompt()`, which assembles:

1. `BASE_SYSTEM_PROMPT` (identity, rules, output format)
2. Custom system prompt (user-provided, if any)
3. Test context: app URL, credentials, test steps, test-specific inputs, additional config
4. Available files for upload (listed with full paths from the upload folder)

An initial user message is built via `build_initial_user_message()` instructing the agent to navigate to the app URL and begin execution.

### Tool Setup

MCP tools from the Playwright server are converted to OpenAI function-calling format. Lifecycle tools (`launch_browser`, `close_browser`) are filtered out since the agent manages those directly.

### Agent Loop

The main loop runs for up to 75 iterations:

1. Call `acompletion()` with the current messages and available tools
2. If the LLM returns tool calls:
   - Capture any assistant reasoning text and broadcast as a "thinking" trajectory entry (status: `"info"`)
   - For each tool call:
     - Broadcast `step_update` with status `"executing"`
     - Execute the tool via MCP
     - Record a `StepResult`
     - Broadcast `step_update` with status `"passed"` or `"failed"`
     - Broadcast `test_status` with current step progress
     - Build tool result content and append to messages
3. If the LLM returns a stop (no tool calls):
   - Parse final status from the completion text (PASSED/FAILED)
   - Close the browser (to finalize video recording)
   - Return `TestResult` with all collected data

### LLM Reasoning Capture

When the LLM includes text content alongside tool calls (reasoning/thinking), the agent captures this text (truncated to 300 characters) and broadcasts it as a trajectory entry with action `"thinking"` and status `"info"`. This allows the UI to display the agent's reasoning in the trajectory log.

### Final Status Parsing

The `_parse_test_status()` function extracts the test outcome from the LLM's final text:

1. Looks for explicit "TEST RESULT: PASSED" or "TEST RESULT: FAILED"
2. Falls back to checking for presence of "PASSED" or "FAILED" keywords
3. Defaults to `"error"` if neither is found

---

## 4. Tool Result Processing

### What Gets Sent Back to the LLM

The `_build_tool_result_content()` function formats tool results as a text string containing:

- Success/failure status line
- Current page URL (if available)
- Page title (if available)
- Full accessibility snapshot (truncated to 8000 characters if very long)

Screenshots are saved to disk but are **NOT** sent as images to the LLM by default. Instead, a text reference to the screenshot path is included when `_should_include_image()` returns true. This keeps token usage efficient while still recording visual evidence.

### Screenshot Reference Strategy

The `_should_include_image()` function determines when to note the screenshot path in the LLM context:

- When the tool is `take_screenshot` (explicit request)
- When the tool is `navigate` and it is one of the first two steps
- Every 5th step for periodic awareness

In all other cases, the LLM relies on the accessibility snapshot for page understanding.

---

## 5. System Prompt Design

The system prompt is built in layers by `prompt_builder.py`:

### Layer 1: BASE_SYSTEM_PROMPT (Identity & Rules)

The base prompt establishes the agent's identity and comprehensive rules:

- **Identity**: QA testing agent that executes test cases by controlling a browser
- **Step execution**: Follow steps in order, do not skip
- **Verification**: After every action, examine the accessibility snapshot to verify success
- **Element finding**: Try alternative selectors (text, role, aria-label, CSS), scroll, wait for dynamic content. Mark as FAILED after 3 attempts.
- **Semantic selectors**: Prefer `text=`, `role=`, `label=`, `placeholder=` over CSS selectors
- **Page transitions**: Handle slow-loading pages with `wait_for_page_ready`, verify via accessibility snapshot. Use `wait_until='networkidle'` for full page reloads. Never assume a page loaded just because a click succeeded.
- **Error recovery**: Reload page, navigate back to app URL, max 3 recovery attempts
- **DevTools usage**: Console logs, network requests, local/session storage, cookies, JavaScript evaluation -- all available for test steps that need them
- **Output format**: `TEST RESULT: [PASSED/FAILED]`, `STEPS COMPLETED: X/Y`, `SUMMARY`, `FAILURE REASON`

### Layer 2: Custom System Prompt

User-provided text appended under a `CUSTOM INSTRUCTIONS:` heading. Examples:

- "Always log in using the admin credentials before starting any test"
- "The application has a slow API, always wait at least 5 seconds after form submissions"
- "Navigate using the sidebar menu, not direct URLs"

### Layer 3: Test Context

Appended dynamically per test case:

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

TEST-SPECIFIC INPUTS:
  expected_dashboard_title: Admin Dashboard

ADDITIONAL CONFIGURATION:
  (any extra config keys not covered above)

AVAILABLE FILES FOR UPLOAD:
  - invoice.pdf (path: /uploads/session_123/files/invoice.pdf)
  - sample_data.csv (path: /uploads/session_123/files/sample_data.csv)
```

The available files section is populated by scanning the `upload_folder` directory on disk and listing each file with its full path, so the agent knows exactly which files it can use for upload test steps.

---

## 6. Selector Strategy

The agent does not have pre-defined selectors. It must figure out how to interact with elements based on:

1. **Test step description**: "Click the Login button" -- the agent looks for a button with text "Login"
2. **Accessibility snapshot**: The structured tree showing all interactive elements with their roles, names, and states
3. **Contextual reasoning**: If "Enter username" but there is no field labeled "username", look for "email", "user", etc.

### Selector Priority Order

The agent is instructed to try selectors in this order:

1. **Text content**: `text=Login`, `text=Submit Order`
2. **Role + name**: `role=button[name="Login"]`, `role=textbox[name="Email"]`
3. **Label**: `label=Email Address`, `label=Password`
4. **Placeholder**: `placeholder=Enter your email`
5. **CSS selector**: `#id`, `.class`, `[data-test="value"]`, `[data-testid="login-btn"]`, `[aria-label="Close dialog"]`

### Handling Ambiguity

When the test step is vague (e.g., "Fill in the form"), the agent:

1. Gets the accessibility snapshot to see all form fields
2. Matches field labels to config values or reasonable defaults
3. Fills fields in DOM order
4. Reports what it filled in the step result

---

## 7. Conversation Management

### Message History Structure

```
System: [Full system prompt: BASE_SYSTEM_PROMPT + custom prompt + test context]

User: "Execute the following test case. Begin by navigating to https://staging.example.com
       and completing the login if credentials are provided.

       Test: Login with valid credentials
       Steps:
         1. Navigate to the login page
         2. Enter username
         ..."
Assistant → tool_calls: [navigate(url="https://staging.example.com")]

Tool result: "Action completed successfully.
  Current URL: https://staging.example.com/login
  Page title: Login - MyApp
  Page accessibility snapshot:
    document 'Login - MyApp'
      heading 'Welcome Back'
      textbox 'Email'
      textbox 'Password'
      button 'Login'
      link 'Forgot password?'"

Assistant → tool_calls: [type_text(selector="label=Email", text="admin@example.com")]

... (continues until all steps are done or test fails)

Assistant → stop: "TEST RESULT: PASSED
  STEPS COMPLETED: 5/5
  SUMMARY: Successfully logged in with valid credentials.
  All steps completed without errors."
```

### Token Budget Management

Including base64 screenshots in every LLM message would be extremely expensive. Strategy:

- **Always include**: accessibility snapshot (text, ~2-5KB)
- **Selectively include screenshot reference**: when the agent explicitly requests visual inspection, the first navigation, or every 5th step
- **Always save screenshots to disk**: regardless of whether they are referenced in the LLM context

### Context Window Management

Long test cases with many tool calls could exhaust the context window:

- GPT-4o has 128K context window; other models may vary
- The agent loop has a max iteration limit (75) as a safety net
- If conversation gets too long, the LLM will naturally produce shorter responses
- Keep: system prompt, all exchanges (tool calls and results), accumulated step results

---

## 8. Error Handling

### Three Levels of Retry

**Level 1: Action-level (within the agent)**
- Element not found, click fails, timeout on single action
- Agent autonomously retries with alternative selectors, longer waits
- The LLM decides when and how to retry based on the error message

**Level 2: Page-level recovery (within the agent)**
- Page crash, unresponsive, error page
- Agent calls `reload()` or `navigate()` back to last URL
- Max 3 page-level recoveries per test case (enforced by the prompt)

**Level 3: Test-case-level retry (orchestrator)**
- Agent reports test case failure
- Orchestrator can retry entire test case with fresh browser + conversation
- Configurable via `max_retries` (0-3, default 0)

### Error Type Matrix

| Error Type | Detection | Handler |
|-----------|-----------|---------|
| Element not found | Tool returns error | Agent retries with alternative selector |
| Navigation timeout | Tool returns timeout | Agent calls `reload()` or re-navigates |
| Browser crash | MCP connection lost | Orchestrator restarts MCP server |
| LLM API error | HTTP error from LiteLLM | Broadcast as failed step, end test |
| MCP server crash | Tool call exception | Agent returns with error status |
| Max iterations | Loop counter >= 75 | Force stop, return collected results |
| Test step ambiguity | Agent cannot determine action | Agent marks step as SKIPPED with explanation |
