# QA Agent - Technical Design Document

## 1. Data Flow

### Phase 1: Upload and Parse

```
User uploads .docx + YAML config
        |
        v
POST /api/upload/document  -->  Save to /uploads/<session_id>/
POST /api/upload/config     -->  Save to /uploads/<session_id>/
        |
        v
POST /api/sessions/<id>/parse
        |
        v
Backend spawns Document MCP Server (stdio)
        |
        v
Calls tool: parse_document(file_path)
        |
        v
Returns structured data:
{
  "sections": [
    {
      "name": "Progressive Tests",
      "test_cases": [
        {
          "id": "TC-001",
          "title": "Login with valid credentials",
          "steps": [
            "Navigate to login page",
            "Enter username",
            "Enter password",
            "Click login button",
            "Verify dashboard is displayed"
          ]
        }
      ]
    }
  ]
}
```

### Phase 2: Review and Configure

```
Frontend displays parsed test cases as cards
        |
User selects sections, adjusts execution mode, edits system prompt
        |
POST /api/sessions/<id>/configure
{
  "selected_sections": ["Progressive Tests"],
  "selected_test_ids": ["TC-001", "TC-002"],
  "execution_mode": "parallel",
  "concurrency": 3,
  "system_prompt": "...",
  "upload_folder": "/path/to/test-files"
}
```

### Phase 3: Execution

```
POST /api/sessions/<id>/run
        |
Backend creates execution plan
        |
For each test case (parallel or sequential):
  1. Spawn dedicated Playwright MCP Server instance
  2. Initialize AI Agent with system prompt + test context + MCP tools
  3. Agent loop:
     a. LLM reads next step(s)
     b. LLM decides tool call (navigate, click, type, etc.)
     c. Tool executes via Playwright MCP
     d. Screenshot captured after action
     e. LLM observes result (accessibility snapshot + screenshot path)
     f. LLM decides next action or confirms step complete
     g. Status update sent via WebSocket
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
**Lifecycle**: Spawned per session, lives for duration of parse + report generation phases.

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

                await status_callback({
                    "test_id": test_case.id,
                    "action": tool_call.function.name,
                    "status": "executed",
                    "step_index": len(step_results),
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
- Agent calls `reload()` → `navigate()` back to last URL → `close_browser()` + `launch_browser()` for fresh context
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

---

## 5. Parallel Execution Design

```python
async def run_session(session: Session):
    semaphore = asyncio.Semaphore(session.config.concurrency)
    tasks = []

    for test_case in session.selected_test_cases:
        task = asyncio.create_task(
            run_with_semaphore(semaphore, test_case, session)
        )
        tasks.append(task)

    results = await asyncio.gather(*tasks, return_exceptions=True)
    return results

async def run_with_semaphore(semaphore, test_case, session):
    async with semaphore:
        # Each test case gets its own:
        # 1. Playwright MCP Server process (new browser context)
        # 2. Agent conversation (fresh message history)
        # 3. Output subfolder
        async with PlaywrightMCPServer() as pw_server:
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
| `POST` | `/api/upload/document` | Upload test .docx → returns `{ session_id, filename }` |
| `POST` | `/api/upload/config/{session_id}` | Upload YAML config |
| `POST` | `/api/upload/files/{session_id}` | Upload test files for browser uploads |

#### Sessions

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/sessions` | List all sessions |
| `GET` | `/api/sessions/{id}` | Get session details |
| `POST` | `/api/sessions/{id}/parse` | Parse uploaded document |
| `POST` | `/api/sessions/{id}/configure` | Set execution configuration |
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
| `GET` | `/api/sessions/{id}/video/{test_id}` | Stream test recording video |

### WebSocket Protocol

**Endpoint**: `ws://localhost:8000/ws/sessions/{session_id}`

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
  timestamp: string
}

// Agent reasoning (optional debug)
{ type: "agent_thought", test_id: string, thought: string }

// Execution complete
{
  type: "execution_complete",
  summary: { total: number, passed: number, failed: number, skipped: number },
  report_url: string,
  timestamp: string
}
```

---

## 7. Data Models

```python
class TestCase(BaseModel):
    id: str
    title: str
    steps: list[str]
    section: str
    config_overrides: dict[str, Any] | None = None

class TestConfig(BaseModel):
    app_url: str
    credentials: dict[str, str]
    test_specific: dict[str, Any]

class ExecutionConfig(BaseModel):
    selected_sections: list[str]
    selected_test_ids: list[str]
    execution_mode: Literal["parallel", "sequential"]
    concurrency: int = 3
    model: str = "gpt-4o"             # Any LiteLLM-supported model identifier
    system_prompt: str = ""
    upload_folder: str | None = None
    max_retries: int = 0

class StepResult(BaseModel):
    step_index: int
    step_description: str
    action: str
    status: Literal["passed", "failed", "skipped"]
    screenshot_path: str | None
    error: str | None
    duration_ms: int

class TestResult(BaseModel):
    test_case: TestCase
    status: Literal["passed", "failed", "skipped", "error"]
    steps: list[StepResult]
    summary: str
    duration_ms: int
    video_path: str | None
    retry_count: int = 0

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
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx                   # Landing / upload page
│   │   └── sessions/
│   │       └── [id]/
│   │           ├── review/page.tsx    # Review parsed test cases
│   │           ├── execute/page.tsx   # Live execution monitoring
│   │           └── results/page.tsx   # Results and export
│   ├── components/
│   │   ├── upload/
│   │   │   ├── DocumentUploader.tsx
│   │   │   ├── ConfigUploader.tsx
│   │   │   └── FolderSelector.tsx
│   │   ├── review/
│   │   │   ├── TestCaseCard.tsx
│   │   │   ├── SectionSelector.tsx
│   │   │   ├── ExecutionConfig.tsx
│   │   │   └── SystemPromptEditor.tsx
│   │   ├── execution/
│   │   │   ├── ExecutionDashboard.tsx
│   │   │   ├── TestCaseProgress.tsx
│   │   │   ├── LiveScreenshot.tsx
│   │   │   └── StatusTimeline.tsx
│   │   ├── results/
│   │   │   ├── ResultsSummary.tsx
│   │   │   ├── TestCaseResult.tsx
│   │   │   └── ExportControls.tsx
│   │   └── ui/                        # shadcn/ui components
│   ├── lib/
│   │   ├── api.ts                     # Backend API client
│   │   ├── websocket.ts              # WebSocket connection manager
│   │   └── types.ts                  # Shared TypeScript types
│   ├── package.json
│   ├── tailwind.config.ts
│   └── tsconfig.json
│
├── backend/                           # FastAPI application
│   ├── main.py                        # FastAPI app entry point
│   ├── config.py                      # App configuration
│   ├── api/
│   │   ├── routes/
│   │   │   ├── upload.py
│   │   │   ├── sessions.py
│   │   │   ├── execution.py
│   │   │   └── export.py
│   │   ├── websocket.py
│   │   └── dependencies.py
│   ├── core/
│   │   ├── session.py                 # Session model and state machine
│   │   ├── orchestrator.py            # Test execution orchestrator
│   │   ├── agent.py                   # AI agent loop
│   │   ├── prompt_builder.py          # System prompt construction
│   │   ├── config_parser.py           # YAML config loading
│   │   ├── mcp_client.py             # MCP stdio client wrapper
│   │   └── models.py                  # Pydantic models
│   ├── mcp_servers/
│   │   ├── document/
│   │   │   ├── server.py              # Document MCP server (FastMCP)
│   │   │   ├── parser.py              # .docx parsing logic
│   │   │   └── report_generator.py    # .docx report creation
│   │   └── playwright_browser/
│   │       ├── server.py              # Playwright MCP server (FastMCP)
│   │       ├── browser_manager.py     # Browser lifecycle
│   │       ├── actions.py             # Browser action implementations
│   │       └── screenshot.py          # Screenshot management
│   ├── requirements.txt
│   └── pyproject.toml
│
├── exports/                           # Runtime output (gitignored)
├── uploads/                           # Runtime uploads (gitignored)
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
│       ├── sample_test_doc.docx
│       └── sample_config.yaml
├── docker-compose.yml
├── .env.example
└── .gitignore
```

---

## 9. Implementation Phases

### Phase 1: Foundation (Week 1-2)
1. Project structure setup (monorepo with `frontend/` and `backend/`)
2. Document MCP Server: parse .docx, extract sections and test cases
3. Backend API: file upload, session creation, parse endpoint
4. Basic frontend: upload page, review page showing parsed test cases

### Phase 2: Execution Core (Week 3-4)
5. Playwright MCP Server: browser launch, navigate, click, type, screenshot
6. AI Agent loop: system prompt construction, tool routing, message management
7. Orchestrator: sequential execution of a single test case end-to-end
8. WebSocket integration: live status streaming

### Phase 3: Parallel & Polish (Week 5-6)
9. Parallel execution with semaphore-based concurrency
10. Retry logic at all three levels
11. Report generation (Document MCP: generate results .docx)
12. Export system (ZIP download of full session folder)
13. Frontend execution monitoring dashboard and results view

### Phase 4: Hardening (Week 7-8)
14. Context window management (truncation, summarization)
15. Error handling for all edge cases
16. Video recording integration
17. File upload/download support in Playwright MCP
18. End-to-end testing of the complete pipeline
