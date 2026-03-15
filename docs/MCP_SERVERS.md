# QA Agent - MCP Server Specifications

## Overview

The application uses two custom MCP servers, both using **stdio transport** (session-based, spawned per need). They are built with the Python `mcp` SDK (FastMCP pattern).

**Note**: Primary document parsing for test case extraction is now handled by the LLM Parser (`core/llm_parser.py`), not the Document MCP Server. The Document MCP Server's parse tools are still available but the LLM parser is the preferred path for initial document ingestion.

---

## 1. Playwright MCP Server

**Purpose**: Browser automation for executing test steps.

**Location**: `backend/mcp_servers/playwright_browser/server.py`

**Dependencies**: `mcp`, `fastmcp`, `playwright`, `pydantic`

### Server Lifecycle

```python
@asynccontextmanager
async def lifespan(server: FastMCP):
    """Start Playwright and store state for the session."""
    pw = await async_playwright().start()
    state = BrowserState(playwright=pw)
    try:
        yield {"browser_state": state}
    finally:
        if state.is_launched:
            await _close_browser(state)
        await pw.stop()

mcp = FastMCP(
    "playwright-browser",
    lifespan=lifespan,
)
```

### Browser Manager (`browser_manager.py`)

#### Data Classes

```python
@dataclass
class ConsoleEntry:
    type: str          # 'log', 'warning', 'error', 'info', 'debug'
    text: str
    url: str
    timestamp: float   # time.time()

@dataclass
class NetworkEntry:
    url: str
    method: str
    resource_type: str          # 'document', 'script', 'stylesheet', 'image', 'xhr', 'fetch', etc.
    request_headers: dict
    request_post_data: str | None
    status: int | None          # None if response not received yet
    status_text: str
    response_headers: dict
    response_body_size: int     # -1 if unknown
    timestamp: float
    duration_ms: float
```

#### `BrowserState`

Holds all browser state for a single MCP server session:

```python
@dataclass
class BrowserState:
    playwright: Playwright | None = None
    browser: Browser | None = None
    context: BrowserContext | None = None
    page: Page | None = None

    screenshot_dir: str = ""
    download_dir: str = ""
    video_dir: str = ""
    screenshot_counter: int = 0

    console_logs: list[ConsoleEntry]     # populated by console listener
    network_entries: list[NetworkEntry]   # populated by network listener
    _request_start_times: dict           # internal timing tracker

    @property
    def is_launched(self) -> bool:
        return self.page is not None and not self.page.is_closed()
```

#### Browser Launch Logic

`launch_browser()` supports the following browser types:

| `browser_type` | Engine | Mechanism |
|---|---|---|
| `chromium` (default) | `playwright.chromium` | Direct launch |
| `firefox` | `playwright.firefox` | Direct launch |
| `webkit` | `playwright.webkit` | Direct launch |
| `chrome` | `playwright.chromium` | Via `channel="chrome"` (must be installed) |
| `msedge` | `playwright.chromium` | Via `channel="msedge"` (must be installed) |

**Custom browser support**: When `executable_path` is provided, the browser manager uses `playwright.chromium` with the `executable_path` parameter instead of a named channel. This allows launching any Chromium-based browser (Brave, Arc, Island, etc.).

#### Listeners

- `_setup_console_listener(state, page)` -- Attaches a `page.on("console", ...)` handler that captures all console messages into `state.console_logs`.
- `_setup_network_listeners(state, page)` -- Attaches `page.on("request", ...)` and `page.on("response", ...)` handlers that capture all network traffic into `state.network_entries`, including request/response headers, post data, status, resource type, and duration.

#### `capture_screenshot(state, action_name, *, full_page, selector)`

Saves a PNG screenshot to disk (if `screenshot_dir` is set), returns base64 screenshot data plus an accessibility tree snapshot. Every tool that interacts with the page calls this to return visual + a11y feedback.

### Tools

#### `launch_browser`

```python
@mcp.tool()
async def launch_browser(
    ctx: Context,
    headless: bool = True,
    browser_type: str = "chromium",       # 'chromium', 'firefox', 'webkit', 'chrome', 'msedge'
    executable_path: str = "",            # Path to custom browser executable
    video_dir: str = "",                  # Directory to save video recording
    viewport_width: int = 1280,
    viewport_height: int = 720,
    screenshot_dir: str = "",             # Directory to auto-save screenshots
    download_dir: str = "",               # Directory to save downloaded files
) -> dict:
```

Must be called before any other browser action. Sets up console and network listeners automatically.

#### `navigate`

```python
@mcp.tool()
async def navigate(
    ctx: Context,
    url: str,
    wait_until: str = "domcontentloaded",  # 'load', 'domcontentloaded', 'networkidle'
    timeout_ms: int = 60000,
) -> dict:
```

Returns a screenshot and accessibility snapshot of the loaded page.

#### `click`

```python
@mcp.tool()
async def click(
    ctx: Context,
    selector: str,
    timeout_ms: int = 30000,
    force: bool = False,
    wait_after: str = "domcontentloaded",  # 'none', 'domcontentloaded', 'load', 'networkidle'
) -> dict:
```

Clicks an element and optionally waits for a load state after the click. The `wait_after` parameter is important for clicks that trigger page navigations or sub-application transitions.

#### `type_text`

```python
@mcp.tool()
async def type_text(
    ctx: Context,
    selector: str,
    text: str,
    clear_first: bool = True,
    delay_ms: int = 50,
) -> dict:
```

Types text into an input field. Uses `page.fill()` to clear, then `page.type()` with delay for human-like keystroke pacing.

#### `select_option`

```python
@mcp.tool()
async def select_option(
    ctx: Context,
    selector: str,
    value: str,
) -> dict:
```

Select a dropdown option. Tries by value first, then by label as fallback.

#### `press_key`

```python
@mcp.tool()
async def press_key(
    ctx: Context,
    key: str,         # 'Enter', 'Tab', 'Escape', 'ArrowDown', etc.
) -> dict:
```

Press a keyboard key via `page.keyboard.press()`. No `selector` parameter -- always operates at the page level.

#### `hover`

```python
@mcp.tool()
async def hover(
    ctx: Context,
    selector: str,
) -> dict:
```

Hover over an element. Returns a screenshot.

#### `scroll`

```python
@mcp.tool()
async def scroll(
    ctx: Context,
    direction: str = "down",       # 'up' or 'down'
    amount: int = 500,             # pixels
    selector: str | None = None,   # scroll within this element if provided
) -> dict:
```

Scrolls the page or a specific element using `window.scrollBy` or `element.scrollBy`.

#### `upload_file`

```python
@mcp.tool()
async def upload_file(
    ctx: Context,
    selector: str,
    file_paths: list[str],
) -> dict:
```

Upload file(s) via `page.set_input_files()`. Validates that all files exist before uploading.

#### `download_file`

```python
@mcp.tool()
async def download_file(
    ctx: Context,
    trigger_selector: str,
    save_dir: str = "",
) -> dict:
```

Clicks an element that triggers a download and saves the file. Uses `page.expect_download()` context manager. Falls back to `state.download_dir` if `save_dir` is empty.

#### `take_screenshot`

```python
@mcp.tool()
async def take_screenshot(
    ctx: Context,
    full_page: bool = False,
    selector: str | None = None,
    name: str | None = None,
) -> dict:
```

Capture a screenshot of the page or a specific element.

#### `get_page_content`

```python
@mcp.tool()
async def get_page_content(
    ctx: Context,
    mode: str = "accessibility",   # 'text' or 'accessibility'
) -> dict:
```

Returns `{"content": "...", "mode": "...", "url": "...", "title": "..."}`. In `accessibility` mode, formats the a11y tree via `_format_a11y_node()`. In `text` mode, returns `page.inner_text("body")`.

#### `get_element_text`

```python
@mcp.tool()
async def get_element_text(
    ctx: Context,
    selector: str,
) -> dict:
```

Get the text content of a specific element via `page.inner_text()`.

#### `wait_for_selector`

```python
@mcp.tool()
async def wait_for_selector(
    ctx: Context,
    selector: str,
    state_val: str = "visible",     # 'attached', 'detached', 'visible', 'hidden'
    timeout_ms: int = 30000,
) -> dict:
```

Wait for an element to reach a specific state. Note: the parameter is named `state_val` (not `state`) to avoid shadowing the browser state variable.

#### `wait_for_navigation`

```python
@mcp.tool()
async def wait_for_navigation(
    ctx: Context,
    timeout_ms: int = 60000,
) -> dict:
```

Waits for `networkidle` load state. Returns a screenshot on success.

#### `wait_for_page_ready`

```python
@mcp.tool()
async def wait_for_page_ready(
    ctx: Context,
    wait_until: str = "networkidle",          # 'domcontentloaded', 'load', 'networkidle'
    timeout_ms: int = 60000,
    expected_url_pattern: str | None = None,  # regex pattern the URL should match
    expected_selector: str | None = None,     # selector that must be visible
) -> dict:
```

Waits for the page to fully load and stabilize. Designed for complex multi-app systems behind a reverse proxy where pages may take longer to settle. Optionally verifies the URL matches a regex pattern and/or a specific element is visible before considering the page ready.

#### `go_back`

```python
@mcp.tool()
async def go_back(ctx: Context) -> dict:
```

Navigate back in browser history. Returns a screenshot.

#### `reload`

```python
@mcp.tool()
async def reload(ctx: Context) -> dict:
```

Reload the current page. Returns a screenshot.

#### `close_browser`

```python
@mcp.tool()
async def close_browser(ctx: Context) -> dict:
```

Close the browser and finalize video recording. Returns `{"status": "closed", "video_path": ...}`. The video file is only fully written after `context.close()`.

#### `get_console_logs`

```python
@mcp.tool()
async def get_console_logs(
    ctx: Context,
    level: str | None = None,     # 'log', 'warning', 'error', 'info', 'debug', or null for all
    search: str | None = None,    # case-insensitive text filter
    last_n: int = 0,              # return only last N entries (0 = all)
) -> dict:
```

Returns captured browser console logs with counts of errors and warnings. Logs are collected automatically since browser launch. Long messages are truncated to 2000 characters.

#### `get_network_requests`

```python
@mcp.tool()
async def get_network_requests(
    ctx: Context,
    url_pattern: str | None = None,    # substring match, case-insensitive
    method: str | None = None,         # 'GET', 'POST', etc.
    resource_type: str | None = None,  # 'document', 'script', 'xhr', 'fetch', etc.
    status_code: int | None = None,    # exact HTTP status code
    has_error: bool = False,           # only failed requests (status >= 400 or no response)
    last_n: int = 0,                   # return only last N entries (0 = all)
) -> dict:
```

Returns captured network requests including URL, method, resource type, status, headers, post data, and duration. Traffic is recorded automatically since browser launch.

#### `get_network_response_body`

```python
@mcp.tool()
async def get_network_response_body(
    ctx: Context,
    url_pattern: str,         # URL substring to match
    occurrence: int = 0,      # 0 = most recent match, 1 = second most recent, etc.
) -> dict:
```

Retrieves metadata for a specific network request's response. Returns URL, status, and response headers for the matching entry.

#### `get_local_storage`

```python
@mcp.tool()
async def get_local_storage(
    ctx: Context,
    key: str | None = None,   # specific key, or null for all entries
) -> dict:
```

Get data from the browser's `localStorage` for the current page origin. If `key` is null, returns all entries.

#### `get_session_storage`

```python
@mcp.tool()
async def get_session_storage(
    ctx: Context,
    key: str | None = None,   # specific key, or null for all entries
) -> dict:
```

Get data from the browser's `sessionStorage` for the current page origin. If `key` is null, returns all entries.

#### `get_cookies`

```python
@mcp.tool()
async def get_cookies(
    ctx: Context,
    url: str | None = None,    # URL to get cookies for (defaults to current page)
    name: str | None = None,   # filter by cookie name (exact match)
) -> dict:
```

Get browser cookies. Returns name, value, domain, path, expires, httpOnly, secure, and sameSite for each cookie.

#### `evaluate_javascript`

```python
@mcp.tool()
async def evaluate_javascript(
    ctx: Context,
    expression: str,   # JS expression, must return JSON-serializable value
) -> dict:
```

Execute arbitrary JavaScript in the browser page context via `page.evaluate()`. Use for advanced checks like reading IndexedDB, checking performance entries, inspecting the DOM, or reading window variables.

---

## 2. Document MCP Server

**Purpose**: Parse .docx test documents and generate formatted result reports.

**Location**: `backend/mcp_servers/document/server.py`

**Dependencies**: `mcp`, `fastmcp`, `python-docx`, `pydantic`, `Pillow` (for image resizing in reports)

**Note**: Primary document parsing for test case extraction is now handled by the LLM Parser (`core/llm_parser.py`). The Document MCP Server's parse tools are still available but the LLM parser is the preferred path for initial document ingestion.

### Tools

#### `parse_document`

```python
@mcp.tool()
def parse_document(
    file_path: str,   # Absolute path to the .docx test document
) -> dict:
```

Parses a complete .docx file and extracts all sections with their test cases. Returns structured data with sections, each containing test cases with id, title, steps, description, and expected results.

#### `list_sections`

```python
@mcp.tool()
def list_sections(
    file_path: str,   # Absolute path to the .docx test document
) -> dict:
```

Quick scan returning section names and test case counts without full parsing.

#### `extract_test_cases`

```python
@mcp.tool()
def extract_test_cases(
    file_path: str,       # Absolute path to the .docx test document
    section_name: str,    # Exact section heading name to extract from
) -> dict:
```

Extract test cases from a specific named section of the document.

#### `generate_report`

```python
@mcp.tool()
def generate_report(
    session_path: str,
    test_results: list[dict],    # Each: test_title, steps, screenshot_paths, status
    tester_name: str = "GPT-4o",
    test_date: str | None = None,
) -> dict:
```

Generate a formatted results .docx report with a 4-column landscape table:

| Test Title | Steps | Screenshots | Verified By |
|---|---|---|---|

- Steps column: numbered list
- Screenshots column: images embedded inline, stacked vertically
- Verified By column: `{tester_name}\n{date}`
- Page orientation: landscape
- Header row repeats on each page

#### `append_test_result`

```python
@mcp.tool()
def append_test_result(
    report_path: str,
    test_result: dict,           # test_title, steps, screenshot_paths, status
    tester_name: str = "GPT-4o",
) -> dict:
```

Incrementally add a single test result row to an existing report. Creates the report if it does not exist yet.

---

## 3. MCP Client

**Purpose**: Manages MCP server subprocesses over stdio from the backend.

**Location**: `backend/core/mcp_client.py`

**Dependencies**: `mcp` (ClientSession, StdioServerParameters, stdio_client)

```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class MCPClient:
    def __init__(self, server_module: str, env: dict[str, str] | None = None):
        """
        Args:
            server_module: Python module path to run (e.g., 'mcp_servers.document.server')
            env: Optional environment variables for the subprocess.
        """

    async def start(self):
        """Spawn the MCP server subprocess and initialize the connection.

        Uses sys.executable to run the server module with -m flag.
        Working directory is set to the backend package root.
        """

    async def call_tool(self, name: str, arguments: dict | None = None) -> Any:
        """Call a tool on the MCP server.

        Extracts text content from the MCP result blocks and attempts
        to parse as JSON. Returns the parsed dict or raw text.
        """

    async def list_tools(self) -> list[dict]:
        """Get available tools from the MCP server.

        Returns list of dicts with 'name', 'description', 'input_schema'.
        """

    async def stop(self):
        """Close the MCP session and terminate the subprocess."""

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *args):
        await self.stop()
```

The client uses `StdioServerParameters` to configure the subprocess and `ClientSession` for the MCP protocol handshake. It supports use as an async context manager.
