# QA Agent - Technical Design Document

## 1. Data Flow

### Phase 1: Upload and Parse

```
User uploads .docx + optional YAML config
        |
        v
POST /api/upload/document  -->  Save to /uploads/<session_id>/
POST /api/upload/config     -->  Save to /uploads/<session_id>/
        |
        v
POST /api/sessions/<id>/parse  (JSON body: { parsing_hint?, model? })
        |
        v
Two parsing paths:
        |
        +--> [Primary] LLM Parser (core/llm_parser.py)
        |       Extracts raw text/tables from .docx
        |       Sends to LLM with optional parsing_hint
        |       Returns structured ParsedDocument
        |
        +--> [Legacy] Document MCP Server (mcp_servers/document/)
                Still used for report generation
                No longer primary parser for test case extraction
        |
        v
Returns structured data:
{
  "filename": "test_plan.docx",
  "document_title": "Progressive Test Suite",
  "total_sections": 2,
  "total_test_cases": 5,
  "sections": [
    {
      "name": "Progressive Tests",
      "heading_level": 1,
      "test_cases": [
        {
          "id": "TC-001",
          "title": "Login with valid credentials",
          "description": "Verify user can log in",
          "steps": [
            "Navigate to login page",
            "Enter username",
            "Enter password",
            "Click login button",
            "Verify dashboard is displayed"
          ],
          "expected_result": "Dashboard is displayed",
          "raw_text": ""
        }
      ]
    }
  ]
}
```

Config parsing also has an LLM path: the parser detects whether a YAML file follows the standard `global/tests` format and uses the rigid parser (`core/config_parser.py`). If the format is non-standard, it sends the YAML content to the LLM for intelligent mapping.

### Phase 2: Review and Configure

```
Frontend displays parsed test cases as cards
        |
User selects sections, adjusts execution mode, edits system prompt
User selects browsers (standard + custom browsers with executable paths)
User uploads test files the agent may need
        |
POST /api/sessions/check-browsers  -->  Pre-flight browser availability check
        |
POST /api/sessions/<id>/configure
{
  "selected_sections": ["Progressive Tests"],
  "selected_test_ids": ["TC-001", "TC-002"],
  "execution_mode": "parallel",
  "concurrency": 3,
  "system_prompt": "...",
  "upload_folder": "/path/to/test-files",
  "browsers": ["chromium", "firefox"],
  "custom_browsers": [
    { "name": "Chrome Beta", "executable_path": "/usr/bin/chrome-beta" }
  ]
}
```

### Phase 3: Execution

```
POST /api/sessions/<id>/run
        |
Backend creates execution plan with BrowserRun concept
(each test case runs across all selected browsers)
        |
Pre-flight browser check skips unavailable browsers with clear messages
        |
For each test case x browser combination (parallel or sequential):
  1. Spawn dedicated Playwright MCP Server instance
  2. Initialize AI Agent with system prompt + test context + MCP tools
  3. Agent loop:
     a. LLM reads next step(s)
     b. LLM decides tool call (navigate, click, type, etc.)
     c. Tool executes via Playwright MCP
     d. Screenshot captured after action
     e. LLM observes result (accessibility snapshot + screenshot path)
     f. LLM decides next action or confirms step complete
     g. _broadcast_step() sends typed WebSocket messages for real-time trajectory
        - step_update messages include action name, detail, and status
        - LLM reasoning text captured as "thinking" entries
     h. Repeat until all steps done or failure after retries
  4. Collect artifacts (screenshots, video, downloads)
```

### Phase 4: Results and Export

```
All test cases complete
        |
Backend calls Document MCP: generate_report(session_id, test_results)
        |
Document MCP creates results_report.docx
        |
GET /api/sessions/<id>/export  -->  Download ZIP
GET /api/sessions/<id>/report  -->  Download .docx
```

---

## 2. MCP Server Design

### 2a. Document MCP Server

**Transport**: stdio
**Lifecycle**: Spawned per session. Primarily used for report generation; test case parsing is now handled by the LLM parser.

#### Tools

| Tool Name | Input | Output | Description |
|-----------|-------|--------|-------------|
| `parse_document` | `file_path: str` | `DocumentStructure` (JSON) | Parse .docx, extract all sections and test cases |
| `list_sections` | `file_path: str` | `SectionList` (JSON) | Quick scan returning section names and test case counts |
| `extract_test_cases` | `file_path: str, section_name: str` | `TestCaseList` (JSON) | Extract test cases from a specific section |
| `generate_report` | `session_path: str, test_results: TestResults` | `report_path: str` | Generate results .docx with tables, screenshots, verification info |
| `append_test_result` | `report_path: str, test_result: SingleTestResult` | `success: bool` | Incrementally add a completed test result to the report |

#### Implementation Notes

- Uses `python-docx` for both reading and writing
- Test cases are typically in tables with columns: Test ID/Title, Description/Steps
- Parsing handles: merged cells, nested tables, multi-paragraph cells, numbered lists within cells
- For images in report cells: use `cell.paragraphs[0].add_run().add_picture()` pattern
- For stacking multiple screenshots in a single cell: add multiple runs with pictures separated by line breaks

### 2b. Playwright MCP Server

**Transport**: stdio
**Lifecycle**: One instance per test case execution. Each gets its own browser context.

#### Tools

| Tool Name | Input | Output | Description |
|-----------|-------|--------|-------------|
| `launch_browser` | `headless: bool, video_dir: str` | `browser_id: str` | Launch browser with video recording |
| `navigate` | `url: str, wait_until: str` | `ScreenshotResult` | Navigate to URL, wait for load |
| `click` | `selector: str, description: str` | `ScreenshotResult` | Click element |
| `type_text` | `selector: str, text: str, clear_first: bool` | `ScreenshotResult` | Type into input field |
| `select_option` | `selector: str, value: str` | `ScreenshotResult` | Select dropdown option |
| `scroll` | `direction: str, amount: int` | `ScreenshotResult` | Scroll page |
| `upload_file` | `selector: str, file_paths: list[str]` | `ScreenshotResult` | Upload file(s) via file input |
| `download_file` | `trigger_selector: str, save_dir: str` | `DownloadResult` | Click to trigger download |
| `take_screenshot` | `full_page: bool, selector: str?` | `ScreenshotResult` | Manual screenshot capture |
| `get_page_content` | `mode: "text" \| "accessibility"` | `PageContent` | Get page text or accessibility tree |
| `wait_for_selector` | `selector: str, state: str, timeout: int` | `WaitResult` | Wait for element |
| `wait_for_navigation` | `timeout: int` | `WaitResult` | Wait for navigation |
| `go_back` | — | `ScreenshotResult` | Browser back |
| `reload` | — | `ScreenshotResult` | Reload page |
| `close_browser` | — | `CloseResult` | Close browser, finalize video |
| `get_element_text` | `selector: str` | `str` | Get text content |
| `press_key` | `key: str` | `ScreenshotResult` | Press keyboard key |
| `hover` | `selector: str` | `ScreenshotResult` | Hover over element |

#### ScreenshotResult Schema

```python
@dataclass
class ScreenshotResult:
    screenshot_path: str          # File path of saved screenshot
    screenshot_base64: str        # Base64 for sending to the LLM as image
    page_url: str                 # Current URL after action
    page_title: str               # Current page title
    accessibility_snapshot: str   # Text-based accessibility tree (compact)
    success: bool
    error: str | None
```

Every action tool returns a `ScreenshotResult` by default. The accessibility snapshot is the primary observation mechanism (cheap in tokens); the screenshot is saved to disk for reports and optionally included in the LLM's context for visual verification.

---

## 3. AI Agent Design

### System Prompt Structure

```
[BASE SYSTEM PROMPT]
You are a QA testing agent. You execute test cases on web applications
by controlling a browser through tools. You follow test steps precisely,
take screenshots after each action, and report results accurately.

[BEHAVIORAL RULES]
- Execute each test step sequentially
- After each browser action, examine the accessibility snapshot to confirm
  the action succeeded before moving to the next step
- If an action fails, retry up to 3 times with increasing wait times
- If a step is ambiguous, use your best judgment to identify the correct
  UI element (use accessibility labels, text content, role attributes)
- Always wait for page loads to complete before taking actions
- Report each step's outcome: PASS, FAIL, or SKIP

[CUSTOM SYSTEM PROMPT]
{user_provided_system_prompt}

[TEST CONTEXT]
Application URL: {app_url}
Login Credentials: {username} / {password}

[TEST CASE]
Title: {test_title}
Steps:
1. {step_1}
2. {step_2}
...

[TEST-SPECIFIC CONFIG]
{yaml_config_values_for_this_test}

[AVAILABLE FILES FOR UPLOAD]
{list_of_files_in_upload_folder}
```

### Agent Loop

```python
from litellm import acompletion

async def execute_test_case(test_case, config, session, status_callback):
    tools = build_tools_from_mcp(playwright_mcp_server)
    system_prompt = build_system_prompt(test_case, config)
    model = config.model or "gpt-4o"  # Default to GPT-4o, configurable

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": f"Execute the following test case. Begin by navigating "
                       f"to {config.app_url} and completing login if needed.\n\n"
                       f"Test: {test_case.title}\n"
                       f"Steps:\n{format_steps(test_case.steps)}"
        },
    ]

    step_results = []

    while True:
        response = await acompletion(
            model=model,
            messages=messages,
            tools=tools,
            max_tokens=4096,
        )

        choice = response.choices[0]

        if choice.finish_reason == "tool_calls":
            messages.append(choice.message)

            for tool_call in choice.message.tool_calls:
                result = await execute_mcp_tool(
                    playwright_mcp_server,
                    tool_call.function.name,
                    json.loads(tool_call.function.arguments),
                    session,
                )

                if hasattr(result, 'screenshot_path'):
                    step_results.append(StepResult(
                        step=infer_current_step(tool_call, test_case),
                        screenshot=result.screenshot_path,
                        status="executed",
                    ))

                # _broadcast_step() sends typed WebSocket messages
                await status_callback({
                    "type": "step_update",
                    "test_id": test_case.id,
                    "action": tool_call.function.name,
                    "detail": str(tool_call.function.arguments),
                    "status": "executing",
                    "step_index": len(step_results),
                    "error": None,
                })

                tool_result_content = build_tool_result_content(
                    result, include_image=should_include_image(tool_call)
                )

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_result_content,
                })

        elif choice.finish_reason == "stop":
            # LLM reasoning text is also captured as "thinking" entries
            final_text = choice.message.content
            return TestResult(
                test_case=test_case,
                status=parse_status(final_text),
                steps=step_results,
                summary=final_text,
            )
```

### Selector Strategy

The agent finds elements without pre-defined selectors:

1. **Accessibility-first**: Agent receives the accessibility tree snapshot. It constructs selectors like `role=button[name="Submit"]` or `text=Login`.
2. **CSS fallback**: If accessibility selectors fail, the agent can request page HTML and construct CSS selectors.
3. **Playwright locator syntax**: Agent uses Playwright's semantic locators (`getByRole`, `getByText`, `getByLabel`).

### Token Budget Management

Including base64 screenshots in every LLM message would be extremely expensive. Strategy:

- **Always include**: accessibility snapshot (text, ~2-5KB)
- **Selectively include screenshot image**: when the agent explicitly requests visual inspection, a step fails and needs diagnosis, or the test step specifically involves visual verification
- **Always save screenshots to disk**: regardless of whether they're in the LLM context

### Context Window Management

Long test cases with many screenshots could exhaust the context window:

- GPT-4o has 128K context window; other models may vary
- If conversation gets long, summarize earlier steps and truncate old messages
- Keep: system prompt, last 5-10 exchanges, accumulated step results

---

## 4. Error Handling

### Three Levels of Retry

**Level 1: Action-level (within the agent)**
- Element not found, click fails, timeout on single action
- Agent autonomously retries with alternative selectors, longer waits
- Max 3 attempts per action

**Level 2: Page-level recovery (within the agent)**
- Page crash, unresponsive, error page
- Agent calls `reload()` -> `navigate()` back to last URL -> `close_browser()` + `launch_browser()` for fresh context
- Max 3 page-level recoveries per test case

**Level 3: Test-case-level retry (orchestrator)**
- Agent reports test case failure
- Orchestrator can retry entire test case with fresh browser + conversation
- Configurable (0-3 retries, default 0)

### Error Type Matrix

| Error Type | Detection | Handler |
|-----------|-----------|---------|
| Element not found | Tool returns error | Agent retries with alternative selector |
| Navigation timeout | Tool returns timeout | Agent calls `reload()` or re-navigates |
| Browser crash | MCP connection lost | Orchestrator restarts MCP server |
| LLM API error | HTTP error from LiteLLM | Exponential backoff retry |
| MCP server crash | Stdio pipe broken | Orchestrator restarts, resumes from last step |
| Token limit exceeded | `max_tokens` reached | Split remaining steps into continuation |
| Test step ambiguity | Agent can't determine action | Agent marks step as SKIPPED with explanation |
| Browser unavailable | Pre-flight check fails | Orchestrator skips browser with clear message |

---

## 5. Parallel Execution Design

```python
async def run_session(session: Session):
    semaphore = asyncio.Semaphore(session.config.concurrency)
    tasks = []

    # BrowserRun: each test runs across all selected browsers
    for test_case in session.selected_test_cases:
        for browser in session.config.browsers:
            task = asyncio.create_task(
                run_with_semaphore(semaphore, test_case, browser, session)
            )
            tasks.append(task)

    results = await asyncio.gather(*tasks, return_exceptions=True)
    return results

async def run_with_semaphore(semaphore, test_case, browser, session):
    async with semaphore:
        # Each test case + browser combination gets its own:
        # 1. Playwright MCP Server process (new browser context)
        # 2. Agent conversation (fresh message history)
        # 3. Output subfolder
        async with PlaywrightMCPServer(browser=browser) as pw_server:
            result = await execute_test_case(
                test_case=test_case,
                config=session.config,
                session=session,
                playwright_mcp=pw_server,
                status_callback=session.ws_broadcast,
            )
        return result
```

### Isolation Guarantees

- Each parallel test gets its own **browser context** (separate cookies, storage, sessions)
- Each parallel test gets its own **MCP server process** (separate stdio pipes, no shared state)
- Each parallel test gets its own **output folder** (`session_<ts>/test_case_<n>/`)
- Shared resource: LLM API, governed by rate limits and the concurrency semaphore

---

## 6. API Design

### REST Endpoints

#### Upload

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/upload/document` | Upload test .docx -> returns `{ session_id, filename }` |
| `POST` | `/api/upload/config/{session_id}` | Upload YAML config |
| `POST` | `/api/upload/files/{session_id}` | Upload test files for browser uploads |

#### Sessions

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/sessions` | List all sessions |
| `GET` | `/api/sessions/{id}` | Get session details |
| `POST` | `/api/sessions/{id}/parse` | Parse uploaded document (accepts `{ parsing_hint?, model? }`) |
| `POST` | `/api/sessions/{id}/configure` | Set execution configuration |
| `POST` | `/api/sessions/check-browsers` | Check browser availability |
| `DELETE` | `/api/sessions/{id}` | Delete session and artifacts |

#### Execution

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/sessions/{id}/run` | Start test execution |
| `GET` | `/api/sessions/{id}/status` | Get execution status (polling fallback) |
| `POST` | `/api/sessions/{id}/abort` | Abort running execution |

#### Export

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/sessions/{id}/report` | Download results .docx |
| `GET` | `/api/sessions/{id}/export` | Download full session ZIP |
| `GET` | `/api/sessions/{id}/screenshots/{test_id}` | Get screenshots for a test case |
| `GET` | `/api/sessions/{id}/screenshot-file/{test_id}/{filename}` | Get individual screenshot file |
| `GET` | `/api/sessions/{id}/video/{test_id}` | Stream test recording video |

### WebSocket Protocol

**Endpoint**: `ws://localhost:8000/ws/sessions/{session_id}`

All messages include a `type` field.

#### Message Types

```typescript
// Execution started
{ type: "execution_started", total_tests: number, execution_mode: string, timestamp: string }

// Test case status update
{
  type: "test_status",
  test_id: string,
  test_title: string,
  status: "queued" | "running" | "passed" | "failed" | "retrying" | "skipped",
  current_step: number,
  total_steps: number,
  last_action: string,
  screenshot_url: string | null,
  error: string | null,
  timestamp: string
}

// Step-level detail
{
  type: "step_update",
  test_id: string,
  step_index: number,
  step_description: string,
  action: string,
  action_detail: string,
  status: "executing" | "passed" | "failed",
  screenshot_url: string | null,
  error: string | null,
  timestamp: string
}

// Agent reasoning (optional debug)
{ type: "agent_thought", test_id: string, thought: string }

// Execution complete (flat structure, not nested summary)
{
  type: "execution_complete",
  total: number,
  passed: number,
  failed: number,
  skipped: number,
  report_url: string,
  timestamp: string
}
```

---

## 7. Data Models

```python
class ParsedTestCase(BaseModel):
    id: str
    title: str
    description: str | None = ""
    steps: list[str] = Field(default_factory=list)
    expected_result: str | None = ""
    raw_text: str = ""

class ParsedSection(BaseModel):
    name: str
    heading_level: int = 1
    test_cases: list[ParsedTestCase] = Field(default_factory=list)

class ParsedDocument(BaseModel):
    filename: str
    sections: list[ParsedSection] = Field(default_factory=list)
    total_sections: int = 0
    total_test_cases: int = 0
    document_title: str = ""

class TestConfig(BaseModel):
    app_url: str = ""
    credentials: dict[str, str] = Field(default_factory=dict)
    timeout_ms: int = 30000
    model: str = "gpt-4o"
    extra: dict[str, Any] = Field(default_factory=dict)
    test_specific: dict[str, dict[str, Any]] = Field(default_factory=dict)

class CustomBrowser(BaseModel):
    name: str
    executable_path: str

class ExecutionConfig(BaseModel):
    selected_sections: list[str] = Field(default_factory=list)
    selected_test_ids: list[str] = Field(default_factory=list)
    execution_mode: Literal["parallel", "sequential"] = "sequential"
    concurrency: int = 3
    model: str = "gpt-4o"
    system_prompt: str = ""
    upload_folder: str | None = None
    max_retries: int = 0
    browsers: list[str] = Field(default_factory=lambda: ["chromium"])
    custom_browsers: list[CustomBrowser] = Field(default_factory=list)

class StepResult(BaseModel):
    step_index: int
    step_description: str = ""
    action: str = ""
    status: Literal["passed", "failed", "skipped"] = "passed"
    screenshot_path: str | None = None
    error: str | None = None
    duration_ms: int = 0

class TestResult(BaseModel):
    test_id: str
    test_title: str
    status: Literal["passed", "failed", "skipped", "error"] = "passed"
    steps: list[StepResult] = Field(default_factory=list)
    summary: str = ""
    duration_ms: int = 0
    video_path: str | None = None
    retry_count: int = 0
    browser: str = "chromium"

class SessionState(str, Enum):
    CREATED = "created"
    DOCUMENT_UPLOADED = "document_uploaded"
    PARSED = "parsed"
    CONFIGURED = "configured"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"
```

---

## 8. Codebase Structure

```
qa-agent/
├── frontend/                          # Next.js application
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx               # Upload page with parsing hints
│   │   │   └── sessions/
│   │   │       └── [id]/
│   │   │           ├── review/page.tsx    # Review, configure, browser selection
│   │   │           ├── execute/page.tsx   # Live execution with trajectory logs
│   │   │           └── results/page.tsx   # Results and export
│   │   ├── components/ui/             # shadcn/ui components
│   │   └── lib/
│   │       ├── api.ts                 # Backend API client
│   │       ├── store.ts              # Zustand store with trajectory tracking
│   │       ├── types.ts              # TypeScript interfaces
│   │       ├── utils.ts              # Utility functions
│   │       └── websocket.ts          # WebSocket hook
│   ├── package.json
│   └── tsconfig.json
│
├── backend/                           # FastAPI application
│   ├── main.py                        # FastAPI app entry point
│   ├── config.py                      # App configuration
│   ├── api/
│   │   ├── routes/
│   │   │   ├── upload.py              # Document, config, and test file uploads
│   │   │   ├── sessions.py           # Session CRUD, parse, configure, browser check
│   │   │   ├── execution.py          # Run, status, abort
│   │   │   └── export.py             # Report, ZIP, screenshots, video
│   │   └── websocket.py              # WebSocket hub
│   ├── core/
│   │   ├── agent.py                   # AI agent loop with trajectory broadcasting
│   │   ├── orchestrator.py            # Multi-browser execution orchestrator
│   │   ├── session.py                 # In-memory session store
│   │   ├── prompt_builder.py          # System prompt construction
│   │   ├── config_parser.py           # Rigid YAML config parser
│   │   ├── llm_parser.py             # LLM-powered document and config parsing
│   │   ├── browser_check.py          # Pre-flight browser availability checks
│   │   ├── mcp_client.py             # MCP stdio client wrapper
│   │   └── models.py                  # Pydantic models + WebSocket message types
│   ├── mcp_servers/
│   │   ├── document/
│   │   │   ├── server.py              # Document MCP server (FastMCP)
│   │   │   ├── parser.py              # .docx parsing logic
│   │   │   └── report_generator.py    # .docx report creation
│   │   └── playwright_browser/
│   │       ├── server.py              # Playwright MCP server (FastMCP)
│   │       └── browser_manager.py     # Browser lifecycle + state management
│   └── pyproject.toml
│
├── tests/
│   └── fixtures/
│       ├── sample_test_doc.docx
│       ├── sample_test_doc_paragraph_steps.docx
│       ├── sample_test_doc_unstructured.docx
│       └── sample_config.yaml
├── exports/                           # Runtime output (gitignored)
├── uploads/                           # Runtime uploads (gitignored)
├── docs/                              # Documentation
├── .env.example
└── .gitignore
```
