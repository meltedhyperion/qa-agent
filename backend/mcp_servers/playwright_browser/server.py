"""Playwright MCP Server — browser automation for QA test execution.

Run as: python -m mcp_servers.playwright_browser.server
Transport: stdio (one instance per test case for isolation)
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Annotated

from fastmcp import Context, FastMCP
from playwright.async_api import async_playwright
from pydantic import Field

from .browser_manager import BrowserState, capture_screenshot
from .browser_manager import close_browser as _close_browser
from .browser_manager import launch_browser as _launch_browser


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
    instructions=(
        "MCP server for browser automation. Provides tools to navigate, "
        "click, type, scroll, upload/download files, take screenshots, "
        "and record video of browser sessions."
    ),
    lifespan=lifespan,
)


def _state(ctx: Context) -> BrowserState:
    """Get browser state from the lifespan context."""
    return ctx.request_context.lifespan_context["browser_state"]


# ── Browser Lifecycle ────────────────────────────────────────────────────────


@mcp.tool()
async def launch_browser(
    ctx: Context,
    headless: Annotated[bool, Field(description="Run in headless mode")] = True,
    browser_type: Annotated[
        str, Field(description="Browser engine: 'chromium', 'firefox', 'webkit', 'chrome', 'msedge'")
    ] = "chromium",
    executable_path: Annotated[
        str, Field(description="Path to custom browser executable. For enterprise/custom Chromium-based browsers.")
    ] = "",
    video_dir: Annotated[
        str, Field(description="Directory to save video recording")
    ] = "",
    viewport_width: Annotated[int, Field(description="Browser viewport width")] = 1280,
    viewport_height: Annotated[int, Field(description="Browser viewport height")] = 720,
    screenshot_dir: Annotated[
        str, Field(description="Directory to auto-save screenshots")
    ] = "",
    download_dir: Annotated[
        str, Field(description="Directory to save downloaded files")
    ] = "",
) -> dict:
    """Launch a browser with optional video recording.

    Supported browser types:
      - chromium (default), firefox, webkit (Safari engine)
      - chrome, msedge (branded, must be installed on the system)
      - For custom/enterprise browsers (Brave, Arc, Island, etc.), set
        browser_type='chromium' and provide the executable_path.

    Must be called before any other browser action.
    """
    state = _state(ctx)
    return await _launch_browser(
        state,
        headless=headless,
        browser_type=browser_type,
        executable_path=executable_path,
        viewport_width=viewport_width,
        viewport_height=viewport_height,
        screenshot_dir=screenshot_dir,
        download_dir=download_dir,
        video_dir=video_dir,
    )


@mcp.tool()
async def close_browser(ctx: Context) -> dict:
    """Close the browser and finalize video recording.

    Returns the path to the recorded video if recording was enabled.
    """
    state = _state(ctx)
    return await _close_browser(state)


# ── Navigation ───────────────────────────────────────────────────────────────


@mcp.tool()
async def navigate(
    ctx: Context,
    url: Annotated[str, Field(description="Target URL to navigate to")],
    wait_until: Annotated[
        str,
        Field(description="Load state: 'load', 'domcontentloaded', or 'networkidle'"),
    ] = "domcontentloaded",
    timeout_ms: Annotated[int, Field(description="Maximum wait time in ms")] = 60000,
) -> dict:
    """Navigate to a URL and wait for the page to load.

    Returns a screenshot and accessibility snapshot of the loaded page.
    For slow-loading pages or sub-applications behind a reverse proxy, increase timeout_ms
    and use wait_until='networkidle' to ensure the page is fully ready.
    """
    state = _state(ctx)
    if not state.is_launched:
        return {"success": False, "error": "Browser not launched"}

    try:
        await state.page.goto(url, wait_until=wait_until, timeout=timeout_ms)
    except Exception as e:
        return {"success": False, "error": f"Navigation failed: {e}"}

    return await capture_screenshot(state, "navigate")


@mcp.tool()
async def go_back(ctx: Context) -> dict:
    """Navigate back in browser history."""
    state = _state(ctx)
    if not state.is_launched:
        return {"success": False, "error": "Browser not launched"}

    await state.page.go_back()
    return await capture_screenshot(state, "go_back")


@mcp.tool()
async def reload(ctx: Context) -> dict:
    """Reload the current page."""
    state = _state(ctx)
    if not state.is_launched:
        return {"success": False, "error": "Browser not launched"}

    await state.page.reload()
    return await capture_screenshot(state, "reload")


# ── Interaction ──────────────────────────────────────────────────────────────


@mcp.tool()
async def click(
    ctx: Context,
    selector: Annotated[
        str,
        Field(description="Playwright selector (CSS, text=, role=, etc.)"),
    ],
    timeout_ms: Annotated[int, Field(description="Max wait for element in ms")] = 30000,
    force: Annotated[
        bool, Field(description="Force click even if element is not visible")
    ] = False,
    wait_after: Annotated[
        str,
        Field(description="Wait strategy after click: 'none', 'domcontentloaded', 'load', 'networkidle'. Use 'load' or 'networkidle' if the click navigates to a new page or sub-application."),
    ] = "domcontentloaded",
) -> dict:
    """Click an element on the page.

    Use semantic selectors when possible: text='Login', role=button[name='Submit'].
    If the click triggers a page navigation (e.g. login, sub-app transition), set wait_after to 'load' or 'networkidle'.
    """
    state = _state(ctx)
    if not state.is_launched:
        return {"success": False, "error": "Browser not launched"}

    url_before = state.page.url
    try:
        await state.page.click(selector, timeout=timeout_ms, force=force)
    except Exception as e:
        result = await capture_screenshot(state, "click_failed")
        result["success"] = False
        result["error"] = f"Click failed: {e}"
        return result

    # Wait for page to settle after click — critical for multi-app setups
    # where clicks can trigger full navigation to a different sub-application
    if wait_after and wait_after != "none":
        try:
            await state.page.wait_for_load_state(wait_after, timeout=timeout_ms)
        except Exception:
            pass  # Page may not navigate; that's fine

    return await capture_screenshot(state, "click")


@mcp.tool()
async def type_text(
    ctx: Context,
    selector: Annotated[str, Field(description="Input field selector")],
    text: Annotated[str, Field(description="Text to type")],
    clear_first: Annotated[
        bool, Field(description="Clear existing text before typing")
    ] = True,
    delay_ms: Annotated[
        int, Field(description="Delay between keystrokes in ms (more human-like)")
    ] = 50,
) -> dict:
    """Type text into an input field."""
    state = _state(ctx)
    if not state.is_launched:
        return {"success": False, "error": "Browser not launched"}

    try:
        if clear_first:
            await state.page.fill(selector, "")
        await state.page.type(selector, text, delay=delay_ms)
    except Exception as e:
        result = await capture_screenshot(state, "type_failed")
        result["success"] = False
        result["error"] = f"Type failed: {e}"
        return result

    return await capture_screenshot(state, "type_text")


@mcp.tool()
async def select_option(
    ctx: Context,
    selector: Annotated[str, Field(description="Select element selector")],
    value: Annotated[str, Field(description="Option value or label to select")],
) -> dict:
    """Select a dropdown option by value or label."""
    state = _state(ctx)
    if not state.is_launched:
        return {"success": False, "error": "Browser not launched"}

    try:
        # Try by value first, then by label
        try:
            await state.page.select_option(selector, value=value)
        except Exception:
            await state.page.select_option(selector, label=value)
    except Exception as e:
        result = await capture_screenshot(state, "select_failed")
        result["success"] = False
        result["error"] = f"Select failed: {e}"
        return result

    return await capture_screenshot(state, "select_option")


@mcp.tool()
async def press_key(
    ctx: Context,
    key: Annotated[
        str,
        Field(description="Key name: 'Enter', 'Tab', 'Escape', 'ArrowDown', etc."),
    ],
) -> dict:
    """Press a keyboard key."""
    state = _state(ctx)
    if not state.is_launched:
        return {"success": False, "error": "Browser not launched"}

    try:
        await state.page.keyboard.press(key)
    except Exception as e:
        return {"success": False, "error": f"Key press failed: {e}"}

    return await capture_screenshot(state, f"press_{key}")


@mcp.tool()
async def hover(
    ctx: Context,
    selector: Annotated[str, Field(description="Element selector to hover over")],
) -> dict:
    """Hover over an element."""
    state = _state(ctx)
    if not state.is_launched:
        return {"success": False, "error": "Browser not launched"}

    try:
        await state.page.hover(selector)
    except Exception as e:
        return {"success": False, "error": f"Hover failed: {e}"}

    return await capture_screenshot(state, "hover")


@mcp.tool()
async def scroll(
    ctx: Context,
    direction: Annotated[str, Field(description="'up' or 'down'")] = "down",
    amount: Annotated[int, Field(description="Pixels to scroll")] = 500,
    selector: Annotated[
        str | None,
        Field(description="If provided, scroll within this element"),
    ] = None,
) -> dict:
    """Scroll the page or a specific element."""
    state = _state(ctx)
    if not state.is_launched:
        return {"success": False, "error": "Browser not launched"}

    delta = amount if direction == "down" else -amount

    try:
        if selector:
            await state.page.locator(selector).evaluate(
                f"el => el.scrollBy(0, {delta})"
            )
        else:
            await state.page.evaluate(f"window.scrollBy(0, {delta})")
    except Exception as e:
        return {"success": False, "error": f"Scroll failed: {e}"}

    return await capture_screenshot(state, f"scroll_{direction}")


# ── File Operations ──────────────────────────────────────────────────────────


@mcp.tool()
async def upload_file(
    ctx: Context,
    selector: Annotated[str, Field(description="File input element selector")],
    file_paths: Annotated[
        list[str], Field(description="List of absolute file paths to upload")
    ],
) -> dict:
    """Upload file(s) via a file input element."""
    state = _state(ctx)
    if not state.is_launched:
        return {"success": False, "error": "Browser not launched"}

    # Validate files exist
    for fp in file_paths:
        if not os.path.exists(fp):
            return {"success": False, "error": f"File not found: {fp}"}

    try:
        await state.page.set_input_files(selector, file_paths)
    except Exception as e:
        return {"success": False, "error": f"Upload failed: {e}"}

    return await capture_screenshot(state, "upload_file")


@mcp.tool()
async def download_file(
    ctx: Context,
    trigger_selector: Annotated[
        str, Field(description="Selector of the download trigger element")
    ],
    save_dir: Annotated[
        str, Field(description="Directory to save the downloaded file")
    ] = "",
) -> dict:
    """Click an element that triggers a download and save the file."""
    state = _state(ctx)
    if not state.is_launched:
        return {"success": False, "error": "Browser not launched"}

    save_dir = save_dir or state.download_dir
    if save_dir:
        os.makedirs(save_dir, exist_ok=True)

    try:
        async with state.page.expect_download() as download_info:
            await state.page.click(trigger_selector)
        download = await download_info.value

        filename = download.suggested_filename
        save_path = os.path.join(save_dir, filename) if save_dir else filename
        await download.save_as(save_path)

        result = await capture_screenshot(state, "download")
        result["downloaded_file"] = save_path
        result["filename"] = filename
        return result
    except Exception as e:
        return {"success": False, "error": f"Download failed: {e}"}


# ── Screenshot & Content ─────────────────────────────────────────────────────


@mcp.tool()
async def take_screenshot(
    ctx: Context,
    full_page: Annotated[
        bool, Field(description="Capture entire scrollable page")
    ] = False,
    selector: Annotated[
        str | None, Field(description="If provided, screenshot only this element")
    ] = None,
    name: Annotated[
        str | None, Field(description="Optional name for the screenshot file")
    ] = None,
) -> dict:
    """Capture a screenshot of the page or a specific element."""
    state = _state(ctx)
    return await capture_screenshot(
        state,
        name or "screenshot",
        full_page=full_page,
        selector=selector,
    )


@mcp.tool()
async def get_page_content(
    ctx: Context,
    mode: Annotated[
        str,
        Field(description="'text' for innerText, 'accessibility' for a11y tree"),
    ] = "accessibility",
) -> dict:
    """Get page content as plain text or accessibility tree snapshot."""
    state = _state(ctx)
    if not state.is_launched:
        return {"success": False, "error": "Browser not launched"}

    page = state.page
    try:
        if mode == "accessibility":
            snapshot = await page.accessibility.snapshot()
            from .browser_manager import _format_a11y_node

            content = _format_a11y_node(snapshot) if snapshot else ""
        else:
            content = await page.inner_text("body")
    except Exception as e:
        content = f"Error getting content: {e}"

    return {
        "content": content,
        "mode": mode,
        "url": page.url,
        "title": await page.title(),
        "success": True,
    }


@mcp.tool()
async def get_element_text(
    ctx: Context,
    selector: Annotated[str, Field(description="Element selector")],
) -> dict:
    """Get the text content of a specific element."""
    state = _state(ctx)
    if not state.is_launched:
        return {"success": False, "error": "Browser not launched"}

    try:
        text = await state.page.inner_text(selector)
        return {"text": text, "selector": selector, "success": True}
    except Exception as e:
        return {"success": False, "error": f"Failed to get text: {e}"}


# ── Waiting ──────────────────────────────────────────────────────────────────


@mcp.tool()
async def wait_for_selector(
    ctx: Context,
    selector: Annotated[str, Field(description="Element selector to wait for")],
    state_val: Annotated[
        str,
        Field(description="'attached', 'detached', 'visible', or 'hidden'"),
    ] = "visible",
    timeout_ms: Annotated[int, Field(description="Maximum wait time in ms")] = 30000,
) -> dict:
    """Wait for an element to reach a specific state."""
    browser_state = _state(ctx)
    if not browser_state.is_launched:
        return {"success": False, "error": "Browser not launched"}

    try:
        await browser_state.page.wait_for_selector(
            selector, state=state_val, timeout=timeout_ms
        )
        return {"success": True, "selector": selector, "state": state_val}
    except Exception as e:
        return {"success": False, "error": f"Wait failed: {e}"}


@mcp.tool()
async def wait_for_navigation(
    ctx: Context,
    timeout_ms: Annotated[int, Field(description="Maximum wait time in ms")] = 60000,
) -> dict:
    """Wait for a navigation event to complete."""
    state = _state(ctx)
    if not state.is_launched:
        return {"success": False, "error": "Browser not launched"}

    try:
        await state.page.wait_for_load_state("networkidle", timeout=timeout_ms)
        return await capture_screenshot(state, "wait_nav")
    except Exception as e:
        return {"success": False, "error": f"Wait for navigation failed: {e}"}


@mcp.tool()
async def wait_for_page_ready(
    ctx: Context,
    wait_until: Annotated[
        str,
        Field(description="Load state: 'domcontentloaded', 'load', or 'networkidle'"),
    ] = "networkidle",
    timeout_ms: Annotated[int, Field(description="Maximum wait time in ms")] = 60000,
    expected_url_pattern: Annotated[
        str | None,
        Field(description="Optional regex pattern the URL should match after the page is ready (e.g. '.*/dashboard.*')"),
    ] = None,
    expected_selector: Annotated[
        str | None,
        Field(description="Optional selector that must be visible before the page is considered ready (e.g. 'h1', '.main-content')"),
    ] = None,
) -> dict:
    """Wait for the page to fully load and stabilize. Use this after actions that trigger
    slow page transitions, sub-application loads, or server-side redirects.

    For complex multi-app systems behind a reverse proxy (e.g. Apache), pages may take
    longer to settle. Use expected_url_pattern or expected_selector to confirm the
    correct sub-application has loaded before proceeding.
    """
    state = _state(ctx)
    if not state.is_launched:
        return {"success": False, "error": "Browser not launched"}

    page = state.page

    try:
        await page.wait_for_load_state(wait_until, timeout=timeout_ms)
    except Exception as e:
        result = await capture_screenshot(state, "wait_ready_timeout")
        result["success"] = False
        result["error"] = f"Page did not reach '{wait_until}' state: {e}"
        return result

    # Optionally wait for URL to match
    if expected_url_pattern:
        import re
        try:
            await page.wait_for_url(re.compile(expected_url_pattern), timeout=timeout_ms)
        except Exception as e:
            result = await capture_screenshot(state, "wait_ready_url_mismatch")
            result["success"] = False
            result["error"] = f"URL did not match pattern '{expected_url_pattern}': current URL is {page.url}"
            return result

    # Optionally wait for a key element
    if expected_selector:
        try:
            await page.wait_for_selector(expected_selector, state="visible", timeout=timeout_ms)
        except Exception as e:
            result = await capture_screenshot(state, "wait_ready_selector_missing")
            result["success"] = False
            result["error"] = f"Expected element '{expected_selector}' not visible: {e}"
            return result

    return await capture_screenshot(state, "page_ready")


# ── DevTools: Console ────────────────────────────────────────────────────────


@mcp.tool()
async def get_console_logs(
    ctx: Context,
    level: Annotated[
        str | None,
        Field(description="Filter by level: 'log', 'warning', 'error', 'info', 'debug', or null for all"),
    ] = None,
    search: Annotated[
        str | None,
        Field(description="Filter logs containing this text (case-insensitive)"),
    ] = None,
    last_n: Annotated[
        int,
        Field(description="Return only the last N entries (0 = all)"),
    ] = 0,
) -> dict:
    """Get captured browser console logs. Logs are collected automatically since browser launch.

    Use this to check for JavaScript errors, warnings, or to verify specific console output.
    """
    state = _state(ctx)
    entries = list(state.console_logs)

    if level:
        entries = [e for e in entries if e.type == level]
    if search:
        search_lower = search.lower()
        entries = [e for e in entries if search_lower in e.text.lower()]
    if last_n > 0:
        entries = entries[-last_n:]

    return {
        "success": True,
        "total_captured": len(state.console_logs),
        "returned": len(entries),
        "logs": [
            {
                "type": e.type,
                "text": e.text[:2000],  # Truncate very long messages
                "url": e.url,
            }
            for e in entries
        ],
        "error_count": sum(1 for e in state.console_logs if e.type == "error"),
        "warning_count": sum(1 for e in state.console_logs if e.type == "warning"),
    }


# ── DevTools: Network ────────────────────────────────────────────────────────


@mcp.tool()
async def get_network_requests(
    ctx: Context,
    url_pattern: Annotated[
        str | None,
        Field(description="Filter by URL pattern (substring match, case-insensitive)"),
    ] = None,
    method: Annotated[
        str | None,
        Field(description="Filter by HTTP method: 'GET', 'POST', etc."),
    ] = None,
    resource_type: Annotated[
        str | None,
        Field(description="Filter by resource type: 'document', 'script', 'stylesheet', 'image', 'xhr', 'fetch', 'font', 'websocket', etc."),
    ] = None,
    status_code: Annotated[
        int | None,
        Field(description="Filter by exact HTTP status code (e.g. 200, 404, 500)"),
    ] = None,
    has_error: Annotated[
        bool,
        Field(description="If true, return only failed requests (status >= 400 or no response)"),
    ] = False,
    last_n: Annotated[
        int,
        Field(description="Return only the last N entries (0 = all)"),
    ] = 0,
) -> dict:
    """Get captured network requests and responses. Traffic is recorded automatically since browser launch.

    Use this to verify API calls, check response headers (e.g. cache-control, content-type),
    inspect request payloads, find failed requests, or verify that specific static files were loaded.
    """
    state = _state(ctx)
    entries = list(state.network_entries)

    if url_pattern:
        pat = url_pattern.lower()
        entries = [e for e in entries if pat in e.url.lower()]
    if method:
        m = method.upper()
        entries = [e for e in entries if e.method == m]
    if resource_type:
        rt = resource_type.lower()
        entries = [e for e in entries if e.resource_type == rt]
    if status_code is not None:
        entries = [e for e in entries if e.status == status_code]
    if has_error:
        entries = [e for e in entries if e.status is None or e.status >= 400]
    if last_n > 0:
        entries = entries[-last_n:]

    return {
        "success": True,
        "total_captured": len(state.network_entries),
        "returned": len(entries),
        "requests": [
            {
                "url": e.url[:500],
                "method": e.method,
                "resource_type": e.resource_type,
                "status": e.status,
                "status_text": e.status_text,
                "request_headers": e.request_headers,
                "response_headers": e.response_headers,
                "request_post_data": (e.request_post_data or "")[:1000],
                "duration_ms": round(e.duration_ms, 1),
            }
            for e in entries
        ],
        "failed_count": sum(
            1 for e in state.network_entries
            if e.status is not None and e.status >= 400
        ),
    }


@mcp.tool()
async def get_network_response_body(
    ctx: Context,
    url_pattern: Annotated[
        str,
        Field(description="URL substring to match the request whose response body to retrieve"),
    ],
    occurrence: Annotated[
        int,
        Field(description="Which matching request to get (0 = most recent, 1 = second most recent, etc.)"),
    ] = 0,
) -> dict:
    """Get the response body of a specific network request. Useful for inspecting API responses,
    JSON payloads, or verifying content of fetched resources.

    Note: Only works for requests that have completed and whose response is still in the browser's buffer.
    Large responses may not be available.
    """
    state = _state(ctx)
    if not state.is_launched:
        return {"success": False, "error": "Browser not launched"}

    # Find the matching response via Playwright's API
    pat = url_pattern.lower()
    try:
        # Use page.evaluate to read from performance API as a fallback
        # For fresh requests, Playwright can intercept — but for already-completed ones
        # we rely on the captured entries for metadata and try to re-fetch
        matching = [e for e in state.network_entries if pat in e.url.lower() and e.status is not None]
        if not matching:
            return {"success": False, "error": f"No completed request matching '{url_pattern}'"}

        target = matching[-(occurrence + 1)] if occurrence < len(matching) else matching[-1]

        return {
            "success": True,
            "url": target.url,
            "status": target.status,
            "response_headers": target.response_headers,
            "note": "Full response body capture requires route interception. Use get_network_requests for headers and metadata.",
        }
    except Exception as e:
        return {"success": False, "error": f"Failed to get response body: {e}"}


# ── DevTools: Storage & Cookies ──────────────────────────────────────────────


@mcp.tool()
async def get_local_storage(
    ctx: Context,
    key: Annotated[
        str | None,
        Field(description="Specific key to retrieve. If null, returns all localStorage entries."),
    ] = None,
) -> dict:
    """Get data from the browser's localStorage for the current page origin."""
    state = _state(ctx)
    if not state.is_launched:
        return {"success": False, "error": "Browser not launched"}

    try:
        if key:
            value = await state.page.evaluate(f"localStorage.getItem({repr(key)})")
            return {"success": True, "key": key, "value": value}
        else:
            data = await state.page.evaluate("""
                () => {
                    const items = {};
                    for (let i = 0; i < localStorage.length; i++) {
                        const k = localStorage.key(i);
                        items[k] = localStorage.getItem(k);
                    }
                    return items;
                }
            """)
            return {"success": True, "entries": data, "count": len(data)}
    except Exception as e:
        return {"success": False, "error": f"Failed to read localStorage: {e}"}


@mcp.tool()
async def get_session_storage(
    ctx: Context,
    key: Annotated[
        str | None,
        Field(description="Specific key to retrieve. If null, returns all sessionStorage entries."),
    ] = None,
) -> dict:
    """Get data from the browser's sessionStorage for the current page origin."""
    state = _state(ctx)
    if not state.is_launched:
        return {"success": False, "error": "Browser not launched"}

    try:
        if key:
            value = await state.page.evaluate(f"sessionStorage.getItem({repr(key)})")
            return {"success": True, "key": key, "value": value}
        else:
            data = await state.page.evaluate("""
                () => {
                    const items = {};
                    for (let i = 0; i < sessionStorage.length; i++) {
                        const k = sessionStorage.key(i);
                        items[k] = sessionStorage.getItem(k);
                    }
                    return items;
                }
            """)
            return {"success": True, "entries": data, "count": len(data)}
    except Exception as e:
        return {"success": False, "error": f"Failed to read sessionStorage: {e}"}


@mcp.tool()
async def get_cookies(
    ctx: Context,
    url: Annotated[
        str | None,
        Field(description="URL to get cookies for. If null, uses the current page URL."),
    ] = None,
    name: Annotated[
        str | None,
        Field(description="Filter cookies by name (exact match)."),
    ] = None,
) -> dict:
    """Get browser cookies for the current page or a specific URL."""
    state = _state(ctx)
    if not state.is_launched:
        return {"success": False, "error": "Browser not launched"}

    try:
        if url:
            cookies = await state.context.cookies(url)
        else:
            cookies = await state.context.cookies()

        if name:
            cookies = [c for c in cookies if c["name"] == name]

        return {
            "success": True,
            "cookies": [
                {
                    "name": c["name"],
                    "value": c["value"],
                    "domain": c["domain"],
                    "path": c["path"],
                    "expires": c.get("expires", -1),
                    "httpOnly": c.get("httpOnly", False),
                    "secure": c.get("secure", False),
                    "sameSite": c.get("sameSite", "None"),
                }
                for c in cookies
            ],
            "count": len(cookies),
        }
    except Exception as e:
        return {"success": False, "error": f"Failed to get cookies: {e}"}


@mcp.tool()
async def evaluate_javascript(
    ctx: Context,
    expression: Annotated[
        str,
        Field(description="JavaScript expression to evaluate in the browser page context. Must return a JSON-serializable value."),
    ],
) -> dict:
    """Execute arbitrary JavaScript in the browser and return the result.

    Use this for advanced checks like reading IndexedDB, checking performance entries,
    inspecting the DOM, reading window variables, or any other browser-side verification
    that isn't covered by the other tools.

    The expression runs in the page context and must return a JSON-serializable value.
    """
    state = _state(ctx)
    if not state.is_launched:
        return {"success": False, "error": "Browser not launched"}

    try:
        result = await state.page.evaluate(expression)
        return {"success": True, "result": result}
    except Exception as e:
        return {"success": False, "error": f"JavaScript evaluation failed: {e}"}


if __name__ == "__main__":
    mcp.run(transport="stdio")
