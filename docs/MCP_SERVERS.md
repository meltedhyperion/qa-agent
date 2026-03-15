# QA Agent - MCP Server Specifications

## Overview

The application uses two custom MCP servers, both using **stdio transport** (session-based, spawned per need). They are built with the Python `mcp` SDK (FastMCP pattern).

---

## 1. Document MCP Server

**Purpose**: Parse .docx test documents and generate formatted result reports.

**Location**: `backend/mcp_servers/document/server.py`

**Dependencies**: `mcp`, `python-docx`, `Pillow` (for image resizing)

### Tools

#### `parse_document`

Parses a complete .docx file and extracts all sections with their test cases.

```python
@mcp.tool()
async def parse_document(file_path: str) -> dict:
    """
    Parse a .docx test document and extract all sections and test cases.

    Args:
        file_path: Absolute path to the .docx file

    Returns:
        {
            "filename": "test_suite.docx",
            "sections": [
                {
                    "name": "Progressive Tests",
                    "heading_level": 1,
                    "test_cases": [
                        {
                            "id": "TC-001",
                            "title": "Login with valid credentials",
                            "description": "Verify user can log in with valid creds",
                            "steps": [
                                "Navigate to login page",
                                "Enter valid username",
                                "Enter valid password",
                                "Click Login button",
                                "Verify dashboard is displayed"
                            ],
                            "expected_result": "User is logged in and sees dashboard",
                            "raw_text": "..."  # Original text from the cell
                        }
                    ]
                }
            ],
            "metadata": {
                "total_sections": 3,
                "total_test_cases": 25,
                "document_title": "Application Test Suite v2.1"
            }
        }
    """
```

**Parsing Strategy**:
1. Iterate through document paragraphs to find headings (section markers)
2. For each section, find tables that follow the heading
3. Parse table rows: first row is typically headers, subsequent rows are test cases
4. Handle common table structures:
   - 2-column: Test Title | Steps/Description
   - 3-column: Test ID | Test Title | Steps/Description
   - 4-column: Test ID | Test Title | Steps | Expected Result
5. Extract numbered lists from cells as step arrays
6. Handle merged cells and multi-paragraph cells

#### `list_sections`

Quick scan of document structure without full parsing.

```python
@mcp.tool()
async def list_sections(file_path: str) -> dict:
    """
    Quick scan returning section names and test case counts.

    Returns:
        {
            "sections": [
                {"name": "Progressive Tests", "test_case_count": 12},
                {"name": "Regression Tests", "test_case_count": 8},
                {"name": "Smoke Tests", "test_case_count": 5}
            ]
        }
    """
```

#### `extract_test_cases`

Extract test cases from a specific section only.

```python
@mcp.tool()
async def extract_test_cases(file_path: str, section_name: str) -> dict:
    """
    Extract test cases from a named section.

    Args:
        file_path: Path to .docx
        section_name: Exact section heading name

    Returns:
        {"section": "Progressive Tests", "test_cases": [...]}
    """
```

#### `generate_report`

Generate the final results .docx document.

```python
@mcp.tool()
async def generate_report(
    session_path: str,
    test_results: list[dict],
    tester_name: str = "GPT-4o",
    test_date: str | None = None,
) -> dict:
    """
    Generate a formatted results .docx with the 4-column table.

    Args:
        session_path: Path to session export folder
        test_results: List of test result objects, each containing:
            - test_title: str
            - steps: list[str]
            - screenshot_paths: list[str]
            - status: "passed" | "failed" | "skipped"
        tester_name: Name for "Verified By" column
        test_date: Date string (defaults to today)

    Returns:
        {"report_path": "/path/to/results_report.docx", "success": true}
    """
```

**Report Generation Details**:
- Creates a Word document with a large table
- Header row: Test Title | Steps | Screenshots | Verified By
- Header row repeats on each page
- Each test case gets one row
- Steps column: numbered list (1. Step one\n2. Step two...)
- Screenshots column: images embedded inline, stacked vertically with small spacing
  - Each image sized to fit column width (~3 inches) while maintaining aspect ratio
  - Uses `cell.paragraphs[0].add_run().add_picture()` for first image
  - Subsequent images: `cell.add_paragraph().add_run().add_picture()`
- Verified By column: `{tester_name}\n{date}`
- Page orientation: landscape (for wider table)
- Margins: 0.5 inches
- Font: Calibri 10pt for text, 8pt for "Verified By"

#### `append_test_result`

Incrementally add results (useful for streaming report generation as tests complete).

```python
@mcp.tool()
async def append_test_result(
    report_path: str,
    test_result: dict,
    tester_name: str = "GPT-4o",
) -> dict:
    """
    Add a single test result row to an existing report.
    Creates the report if it doesn't exist.
    """
```

---

## 2. Playwright MCP Server

**Purpose**: Browser automation for executing test steps.

**Location**: `backend/mcp_servers/playwright_browser/server.py`

**Dependencies**: `mcp`, `playwright`

### Server Lifecycle

```python
# Server initialization
@mcp.lifespan
async def lifespan(server):
    async with async_playwright() as playwright:
        server.state["playwright"] = playwright
        server.state["browser"] = None
        server.state["page"] = None
        server.state["screenshot_counter"] = 0
        yield
```

### Tools

#### `launch_browser`

```python
@mcp.tool()
async def launch_browser(
    headless: bool = True,
    video_dir: str | None = None,
    viewport_width: int = 1280,
    viewport_height: int = 720,
    screenshot_dir: str | None = None,
    download_dir: str | None = None,
) -> dict:
    """
    Launch a Chromium browser with optional video recording.

    Args:
        headless: Run in headless mode
        video_dir: Directory to save video recording (enables recording if set)
        viewport_width: Browser viewport width
        viewport_height: Browser viewport height
        screenshot_dir: Directory to auto-save screenshots
        download_dir: Directory to save downloaded files

    Returns:
        {"browser_id": "...", "status": "launched"}
    """
```

**Implementation Notes**:
- Uses `browser.new_context(record_video_dir=video_dir)` for video
- Sets `accept_downloads=True` on context
- Configures download path via `context.set_default_timeout(30000)`

#### `navigate`

```python
@mcp.tool()
async def navigate(
    url: str,
    wait_until: str = "networkidle",
    timeout_ms: int = 30000,
) -> dict:
    """
    Navigate to a URL and wait for the page to load.

    Args:
        url: Target URL
        wait_until: Load state to wait for ("load", "domcontentloaded", "networkidle")
        timeout_ms: Maximum wait time

    Returns: ScreenshotResult with page state after navigation
    """
```

#### `click`

```python
@mcp.tool()
async def click(
    selector: str,
    timeout_ms: int = 10000,
    force: bool = False,
) -> dict:
    """
    Click an element on the page.

    Args:
        selector: Playwright selector (CSS, text=, role=, etc.)
        timeout_ms: Max wait for element
        force: Force click even if element is not visible

    Returns: ScreenshotResult after click
    """
```

#### `type_text`

```python
@mcp.tool()
async def type_text(
    selector: str,
    text: str,
    clear_first: bool = True,
    delay_ms: int = 50,
) -> dict:
    """
    Type text into an input field.

    Args:
        selector: Input field selector
        text: Text to type
        clear_first: Clear existing text before typing
        delay_ms: Delay between keystrokes (more human-like)

    Returns: ScreenshotResult after typing
    """
```

#### `select_option`

```python
@mcp.tool()
async def select_option(selector: str, value: str) -> dict:
    """Select a dropdown option by value or label."""
```

#### `scroll`

```python
@mcp.tool()
async def scroll(
    direction: str = "down",
    amount: int = 500,
    selector: str | None = None,
) -> dict:
    """
    Scroll the page or a specific element.

    Args:
        direction: "up" or "down"
        amount: Pixels to scroll
        selector: If provided, scroll within this element
    """
```

#### `upload_file`

```python
@mcp.tool()
async def upload_file(
    selector: str,
    file_paths: list[str],
) -> dict:
    """
    Upload file(s) via a file input element.

    Args:
        selector: File input selector
        file_paths: List of absolute file paths to upload

    Returns: ScreenshotResult after upload
    """
```

**Implementation**: Uses `page.set_input_files(selector, file_paths)`

#### `download_file`

```python
@mcp.tool()
async def download_file(
    trigger_selector: str,
    save_dir: str,
) -> dict:
    """
    Click an element that triggers a download and save the file.

    Args:
        trigger_selector: Selector of the element to click (download button/link)
        save_dir: Directory to save the downloaded file

    Returns:
        {
            "file_path": "/path/to/downloaded/file.pdf",
            "filename": "file.pdf",
            "size_bytes": 12345,
            "screenshot_path": "...",
            "success": true
        }
    """
```

**Implementation**:
```python
async with page.expect_download() as download_info:
    await page.click(trigger_selector)
download = await download_info.value
save_path = os.path.join(save_dir, download.suggested_filename)
await download.save_as(save_path)
```

#### `take_screenshot`

```python
@mcp.tool()
async def take_screenshot(
    full_page: bool = False,
    selector: str | None = None,
    name: str | None = None,
) -> dict:
    """
    Capture a screenshot of the page or a specific element.

    Args:
        full_page: Capture entire scrollable page
        selector: If provided, screenshot only this element
        name: Optional name for the screenshot file

    Returns: ScreenshotResult
    """
```

#### `get_page_content`

```python
@mcp.tool()
async def get_page_content(
    mode: str = "accessibility",
) -> dict:
    """
    Get page content as text or accessibility tree.

    Args:
        mode: "text" for innerText, "accessibility" for accessibility tree snapshot

    Returns:
        {"content": "...", "mode": "accessibility", "url": "...", "title": "..."}
    """
```

**Accessibility Tree Implementation**:
```python
# Get accessibility snapshot
snapshot = await page.accessibility.snapshot()
# Format as readable text tree
formatted = format_accessibility_tree(snapshot)
```

#### `wait_for_selector`

```python
@mcp.tool()
async def wait_for_selector(
    selector: str,
    state: str = "visible",
    timeout_ms: int = 30000,
) -> dict:
    """
    Wait for an element to reach a specific state.

    Args:
        selector: Element selector
        state: "attached", "detached", "visible", "hidden"
        timeout_ms: Maximum wait time
    """
```

#### `wait_for_navigation`

```python
@mcp.tool()
async def wait_for_navigation(timeout_ms: int = 30000) -> dict:
    """Wait for a navigation event to complete."""
```

#### `go_back`

```python
@mcp.tool()
async def go_back() -> dict:
    """Navigate back in browser history. Returns ScreenshotResult."""
```

#### `reload`

```python
@mcp.tool()
async def reload() -> dict:
    """Reload the current page. Returns ScreenshotResult."""
```

#### `close_browser`

```python
@mcp.tool()
async def close_browser() -> dict:
    """
    Close the browser and finalize video recording.

    Returns:
        {"status": "closed", "video_path": "/path/to/recording.webm"}
    """
```

**Implementation Note**: The video file is only fully written after `context.close()`. The video path is obtained via `page.video.path()`.

#### `get_element_text`

```python
@mcp.tool()
async def get_element_text(selector: str) -> dict:
    """Get the text content of a specific element."""
```

#### `press_key`

```python
@mcp.tool()
async def press_key(key: str) -> dict:
    """
    Press a keyboard key.

    Args:
        key: Key name ("Enter", "Tab", "Escape", "ArrowDown", etc.)
    """
```

#### `hover`

```python
@mcp.tool()
async def hover(selector: str) -> dict:
    """Hover over an element. Returns ScreenshotResult."""
```

### Screenshot Auto-Save Logic

Every tool that returns a `ScreenshotResult` follows this pattern:

```python
async def _capture_and_save(page, screenshot_dir, counter, action_name):
    """Capture screenshot, save to disk, return result."""
    counter += 1
    filename = f"{counter:03d}_{action_name}.png"
    filepath = os.path.join(screenshot_dir, filename)

    screenshot_bytes = await page.screenshot()
    with open(filepath, "wb") as f:
        f.write(screenshot_bytes)

    screenshot_b64 = base64.b64encode(screenshot_bytes).decode()

    # Get accessibility snapshot for the agent
    try:
        a11y = await page.accessibility.snapshot()
        a11y_text = format_accessibility_tree(a11y)
    except Exception:
        a11y_text = await page.inner_text("body")

    return {
        "screenshot_path": filepath,
        "screenshot_base64": screenshot_b64,
        "page_url": page.url,
        "page_title": await page.title(),
        "accessibility_snapshot": a11y_text,
        "success": True,
        "error": None,
    }
```

---

## 3. MCP Client (Backend Side)

The backend communicates with MCP servers via stdio. Located at `backend/core/mcp_client.py`.

```python
class MCPStdioClient:
    """Wrapper for communicating with an MCP server over stdio."""

    def __init__(self, server_script: str, env: dict | None = None):
        self.server_script = server_script
        self.process = None

    async def start(self):
        """Spawn the MCP server subprocess."""
        self.process = await asyncio.create_subprocess_exec(
            "python", self.server_script,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        # Initialize MCP connection (handshake)
        await self._initialize()

    async def call_tool(self, name: str, arguments: dict) -> dict:
        """Call a tool on the MCP server and return the result."""
        request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
            "id": self._next_id(),
        }
        await self._send(request)
        response = await self._receive()
        return response["result"]

    async def list_tools(self) -> list[dict]:
        """Get available tools from the MCP server."""
        request = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "params": {},
            "id": self._next_id(),
        }
        await self._send(request)
        response = await self._receive()
        return response["result"]["tools"]

    async def stop(self):
        """Terminate the MCP server process."""
        if self.process:
            self.process.terminate()
            await self.process.wait()

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *args):
        await self.stop()
```

**Note**: In practice, we'll use the `mcp` SDK's client utilities (`StdioServerParameters`, `ClientSession`) rather than raw JSON-RPC. The above illustrates the concept; the actual implementation will use:

```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

server_params = StdioServerParameters(
    command="python",
    args=["backend/mcp_servers/document/server.py"],
)

async with stdio_client(server_params) as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()
        tools = await session.list_tools()
        result = await session.call_tool("parse_document", {"file_path": "..."})
```
