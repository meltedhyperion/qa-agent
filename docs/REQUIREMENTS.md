# QA Agent - Requirements Specification

## 1. Functional Requirements

### 1.1 Document Upload & Parsing

| ID | Requirement | Priority |
|----|------------|----------|
| FR-1.1 | System shall accept .docx/.doc test documents via file upload | Must |
| FR-1.2 | System shall accept YAML configuration files via file upload | Must |
| FR-1.3 | System shall parse .docx files and extract sections (progressive tests, regression tests, etc.) | Must |
| FR-1.4 | System shall extract test cases from tables within sections (test title, test description/steps) | Must |
| FR-1.5 | System shall handle various table formats — merged cells, nested tables, multi-paragraph cells, numbered lists within cells | Must |
| FR-1.6 | System shall display parsed sections and test case counts for user to select | Must |
| FR-1.7 | User shall be able to select which sections to run tests from | Must |
| FR-1.8 | System shall use LLM to intelligently extract test cases from any document format (tables, paragraphs, numbered lists, mixed formats) | Must |
| FR-1.9 | User shall be able to provide parsing hints to guide the LLM on where to find test cases in the document | Should |
| FR-1.10 | System shall handle documents with non-test content (business context, requirements, architecture descriptions) by filtering to only test cases | Must |

### 1.2 Configuration

| ID | Requirement | Priority |
|----|------------|----------|
| FR-2.1 | YAML config shall support global settings: application URL, login credentials, timeout values | Must |
| FR-2.2 | YAML config shall support test-specific overrides: credentials, custom inputs per test case ID | Must |
| FR-2.3 | User shall be able to configure execution mode: parallel or sequential | Must |
| FR-2.4 | User shall be able to configure concurrency level (number of parallel agents) | Must |
| FR-2.5 | User shall be able to configure a filesystem folder for file uploads needed during tests | Must |
| FR-2.6 | User shall be able to provide a system prompt to customize agent behavior | Should |
| FR-2.7 | Agent shall flexibly parse YAML config based on test requirements (no rigid schema required) | Must |
| FR-2.8 | System shall support LLM-powered config parsing for non-standard YAML formats | Must |
| FR-2.9 | System shall auto-detect standard `global/tests` YAML format and use rigid parser (saving an LLM call) | Should |
| FR-2.10 | User shall be able to select which browsers to run tests in (chromium, firefox, webkit, chrome, msedge) | Must |
| FR-2.11 | User shall be able to add custom/enterprise browsers by providing a name and executable path | Should |
| FR-2.12 | System shall validate browser availability before test execution via pre-flight checks | Must |

### 1.3 Test Review (Pre-Execution)

| ID | Requirement | Priority |
|----|------------|----------|
| FR-3.1 | System shall generate a "requirements file" — structured plan of each test case with its configurations | Must |
| FR-3.2 | UI shall display each test case in a separate card with: title, steps, global configs, test-specific configs | Must |
| FR-3.3 | Cards shall be displayed in a scrollable view | Must |
| FR-3.4 | User shall confirm/approve the test plan before execution begins | Must |
| FR-3.5 | User shall be able to deselect individual test cases before running | Should |
| FR-3.6 | User shall be able to upload test files through the UI for use during test execution | Should |
| FR-3.7 | User shall be able to check browser availability from the review page | Should |

### 1.4 Test Execution

| ID | Requirement | Priority |
|----|------------|----------|
| FR-4.1 | System shall use Playwright to open the target application in a browser | Must |
| FR-4.2 | Agent shall perform browser actions: clicks, navigation, scrolls, keyboard typing | Must |
| FR-4.3 | Agent shall take a screenshot after every action/step | Must |
| FR-4.4 | Agent shall wait for pages to load completely before taking actions | Must |
| FR-4.5 | System shall retry failed actions up to 3 times | Must |
| FR-4.6 | If all retries fail, system shall mark test case as failed with reason | Must |
| FR-4.7 | System shall support file uploads during tests using the configured filesystem folder | Must |
| FR-4.8 | System shall capture downloads during tests and save them per-test-case | Must |
| FR-4.9 | System shall record video of the entire browser session per test case | Must |
| FR-4.10 | System shall handle page crashes and timeouts by reloading | Must |
| FR-4.11 | User shall be able to trigger test execution via a "Run" button | Must |
| FR-4.12 | System shall run each test case across all selected browsers (standard + custom) | Must |
| FR-4.13 | System shall skip tests for browsers that fail pre-flight availability checks | Must |
| FR-4.14 | Custom browsers shall be launched using Playwright's executable_path parameter | Must |

### 1.5 Session & Export Management

| ID | Requirement | Priority |
|----|------------|----------|
| FR-5.1 | Each test session shall have its own export folder | Must |
| FR-5.2 | Each test case within a session shall have its own subfolder containing: recording (video), screenshots folder, downloads/output folder | Must |
| FR-5.3 | System shall generate a results document (.docx) with a 4-column table | Must |
| FR-5.4 | Column 1: Test title (from original test doc) | Must |
| FR-5.5 | Column 2: Steps for the test (numbered bullets) | Must |
| FR-5.6 | Column 3: Screenshots stacked vertically within the same cell | Must |
| FR-5.7 | Column 4: Verified by — model name + date of testing | Must |
| FR-5.8 | Results document shall be properly formatted despite potentially many screenshots | Must |
| FR-5.9 | User shall be able to download the full session as a ZIP | Should |

### 1.6 Real-Time Monitoring

| ID | Requirement | Priority |
|----|------------|----------|
| FR-6.1 | UI shall show live status of each test case during execution | Must |
| FR-6.2 | UI shall show which step/action the agent is currently executing | Should |
| FR-6.3 | UI shall show the latest screenshot for each running test | Should |
| FR-6.4 | UI shall provide summary counts: running, passed, failed, queued | Must |
| FR-6.5 | UI shall show real-time trajectory log per test case with action details | Must |
| FR-6.6 | Trajectory entries shall show action name, detail, status, and timestamp | Must |
| FR-6.7 | "Executing" trajectory entries shall be replaced with final "passed"/"failed" status | Should |

---

## 2. Non-Functional Requirements

### 2.1 Performance

| ID | Requirement |
|----|------------|
| NFR-1 | System shall support up to 10 parallel test case executions |
| NFR-2 | Screenshot capture shall not add more than 500ms overhead per action |
| NFR-3 | Document parsing shall complete within 30 seconds for documents up to 200 pages |
| NFR-4 | WebSocket status updates shall be delivered within 1 second of action completion |

### 2.2 Reliability

| ID | Requirement |
|----|------------|
| NFR-5 | System shall gracefully handle browser crashes without affecting other parallel tests |
| NFR-6 | System shall recover from LLM API errors with exponential backoff |
| NFR-7 | System shall handle MCP server crashes by restarting the server process |
| NFR-8 | All artifacts (screenshots, videos, downloads) shall be persisted to disk immediately |

### 2.3 Security

| ID | Requirement |
|----|------------|
| NFR-9 | Credentials shall only be stored in the YAML config file, never in test documents |
| NFR-10 | Uploaded files and session artifacts shall be stored in isolated directories |
| NFR-11 | YAML config files shall not be included in exported results |
| NFR-12 | API endpoints shall validate file types and sizes |

### 2.4 Usability

| ID | Requirement |
|----|------------|
| NFR-13 | Upload-to-review flow shall be completable in under 5 clicks |
| NFR-14 | Test case cards shall clearly show all configuration the agent will use |
| NFR-15 | Results report shall be human-readable without specialized tools (standard .docx viewer) |

### 2.5 Cross-Platform

| ID | Requirement |
|----|------------|
| NFR-16 | System shall support macOS, Windows, and Linux |
| NFR-17 | Browser detection shall use platform-specific paths (Applications on macOS, PROGRAMFILES on Windows, /usr/bin on Linux) |

---

## 3. YAML Configuration Schema

The YAML config file is intentionally flexible — the agent parses it based on test requirements. However, here is the recommended structure:

> **Note:** Non-standard YAML formats are also accepted. The LLM will intelligently map any YAML structure to the required format. Only the standard `global/tests` format shown below triggers the rigid parser; all other formats go through LLM parsing.

```yaml
# Global configuration applied to all tests
global:
  app_url: "https://staging.example.com"
  credentials:
    username: "admin@example.com"
    password: "secret123"
  timeout_ms: 30000
  model: "gpt-4o"                    # Any LiteLLM-supported model (e.g., gpt-4o, gpt-4o-mini, claude-sonnet-4-20250514, gemini/gemini-pro)
  # Any other global key-value pairs the agent might need

# Test-specific configuration (keyed by test case ID or title)
tests:
  "TC-001":                        # Matches test case ID from the document
    credentials:                   # Override global creds for this test
      username: "user@example.com"
      password: "userpass"
    inputs:
      order_id: "ORD-12345"
      product_name: "Widget A"

  "TC-005":
    inputs:
      file_to_upload: "invoice.pdf"  # Resolved from the upload folder
      customer_name: "Jane Doe"

  "Login with valid credentials":   # Can also match by test title
    inputs:
      expected_dashboard: "Admin Dashboard"
```

---

## 4. Session Folder Structure

```
exports/
  <session_id>/
    TC-001_chromium/
      screenshots/            # Screenshot per action, numbered sequentially
        001_navigate_login.png
        002_type_username.png
        003_type_password.png
        004_click_login.png
        005_verify_dashboard.png
      recording/              # Video file of the test run
        recording.webm
      downloads/              # Any files downloaded during the test
        report_Q1.pdf
    TC-001_firefox/
      screenshots/
      recording/
      downloads/
    TC-002_chromium/
      screenshots/
      recording/
      downloads/
    ...
    results_report.docx       # Final formatted results document
```

---

## 5. Results Document Format

The results .docx contains a single large table with one row per test case:

| Test Title | Steps | Screenshots | Verified By |
|-----------|-------|-------------|-------------|
| Login with valid credentials | 1. Navigate to login page<br>2. Enter username "admin@example.com"<br>3. Enter password<br>4. Click "Login" button<br>5. Verify dashboard appears | ![screenshot1](001.png)<br>![screenshot2](002.png)<br>![screenshot3](003.png)<br>![screenshot4](004.png)<br>![screenshot5](005.png) | GPT-4o<br>2026-03-15 |
| Create new order | 1. Navigate to Orders page<br>2. Click "New Order"<br>3. Fill in order form<br>4. Submit order<br>5. Verify confirmation | ![screenshot1](001.png)<br>...more... | GPT-4o<br>2026-03-15 |

Notes:
- Screenshots are embedded as images within the cell, stacked vertically
- Each screenshot is sized to fit the column width while maintaining aspect ratio
- The document can be very long; proper page breaks and header row repetition are applied
