"""Browser lifecycle and state management for the Playwright MCP server."""

from __future__ import annotations

import base64
import os
import time
from dataclasses import dataclass, field

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
)


@dataclass
class ConsoleEntry:
    """A captured browser console message."""
    type: str          # 'log', 'warning', 'error', 'info', 'debug'
    text: str
    url: str
    timestamp: float   # time.time()


@dataclass
class NetworkEntry:
    """A captured network request/response pair."""
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


@dataclass
class BrowserState:
    """Holds all browser state for a single MCP server session."""

    playwright: Playwright | None = None
    browser: Browser | None = None
    context: BrowserContext | None = None
    page: Page | None = None

    screenshot_dir: str = ""
    download_dir: str = ""
    video_dir: str = ""
    screenshot_counter: int = 0

    # Captured devtools data
    console_logs: list[ConsoleEntry] = field(default_factory=list)
    network_entries: list[NetworkEntry] = field(default_factory=list)
    _request_start_times: dict = field(default_factory=dict)

    @property
    def is_launched(self) -> bool:
        return self.page is not None and not self.page.is_closed()


def _setup_console_listener(state: BrowserState, page: Page) -> None:
    """Attach a console listener that captures all console messages."""
    def on_console(msg):
        state.console_logs.append(ConsoleEntry(
            type=msg.type,
            text=msg.text,
            url=page.url,
            timestamp=time.time(),
        ))
    page.on("console", on_console)


def _setup_network_listeners(state: BrowserState, page: Page) -> None:
    """Attach request/response listeners that capture all network traffic."""
    def on_request(request):
        state._request_start_times[request.url + str(id(request))] = time.time()
        try:
            req_headers = dict(request.headers)
        except Exception:
            req_headers = {}

        state.network_entries.append(NetworkEntry(
            url=request.url,
            method=request.method,
            resource_type=request.resource_type,
            request_headers=req_headers,
            request_post_data=request.post_data,
            status=None,
            status_text="",
            response_headers={},
            response_body_size=-1,
            timestamp=time.time(),
            duration_ms=0,
        ))

    def on_response(response):
        start = state._request_start_times.pop(
            response.url + str(id(response.request)), None
        )
        duration = (time.time() - start) * 1000 if start else 0

        try:
            resp_headers = dict(response.headers)
        except Exception:
            resp_headers = {}

        # Find matching entry and update it
        for entry in reversed(state.network_entries):
            if entry.url == response.url and entry.status is None:
                entry.status = response.status
                entry.status_text = response.status_text
                entry.response_headers = resp_headers
                entry.duration_ms = duration
                try:
                    body = response.headers.get("content-length", "-1")
                    entry.response_body_size = int(body)
                except (ValueError, TypeError):
                    pass
                break

    page.on("request", on_request)
    page.on("response", on_response)


async def launch_browser(
    state: BrowserState,
    *,
    headless: bool = True,
    browser_type: str = "chromium",
    executable_path: str = "",
    viewport_width: int = 1280,
    viewport_height: int = 720,
    screenshot_dir: str = "",
    download_dir: str = "",
    video_dir: str = "",
) -> dict:
    """Launch a browser with optional video recording.

    Supported browser_type values:
      - 'chromium' (default) — Chromium-based browser
      - 'firefox' — Mozilla Firefox
      - 'webkit' — WebKit (Safari engine)
      - 'chrome' — Google Chrome (branded, must be installed)
      - 'msedge' — Microsoft Edge (branded, must be installed)

    For custom/enterprise Chromium-based browsers (Brave, Arc, Island, etc.),
    set browser_type='chromium' and pass the executable_path to the browser binary.
    """
    if state.playwright is None:
        raise RuntimeError("Playwright not initialized")

    state.screenshot_dir = screenshot_dir
    state.download_dir = download_dir
    state.video_dir = video_dir

    # Reset captured data
    state.console_logs.clear()
    state.network_entries.clear()
    state._request_start_times.clear()

    # Create directories
    for d in (screenshot_dir, download_dir, video_dir):
        if d:
            os.makedirs(d, exist_ok=True)

    # Select browser engine and optional channel for branded browsers
    launch_kwargs: dict = {"headless": headless}
    bt = browser_type.lower()

    if executable_path:
        # Custom browser — always use chromium engine with explicit executable
        engine = state.playwright.chromium
        launch_kwargs["executable_path"] = executable_path
    elif bt in ("chrome", "msedge"):
        # Branded browsers use Chromium engine with a channel
        engine = state.playwright.chromium
        launch_kwargs["channel"] = bt
    elif bt == "firefox":
        engine = state.playwright.firefox
    elif bt == "webkit":
        engine = state.playwright.webkit
    else:
        engine = state.playwright.chromium

    state.browser = await engine.launch(**launch_kwargs)

    context_kwargs: dict = {
        "viewport": {"width": viewport_width, "height": viewport_height},
        "accept_downloads": True,
    }
    if video_dir:
        context_kwargs["record_video_dir"] = video_dir
        context_kwargs["record_video_size"] = {
            "width": viewport_width,
            "height": viewport_height,
        }

    state.context = await state.browser.new_context(**context_kwargs)
    # Default timeout covers slow enterprise apps behind reverse proxies
    timeout = 60000
    state.context.set_default_timeout(timeout)
    state.context.set_default_navigation_timeout(timeout)
    state.page = await state.context.new_page()
    state.screenshot_counter = 0

    # Attach console + network listeners
    _setup_console_listener(state, state.page)
    _setup_network_listeners(state, state.page)

    return {"status": "launched", "headless": headless, "browser": bt}


async def close_browser(state: BrowserState) -> dict:
    """Close the browser and finalize video recording."""
    video_path = None

    if state.page and not state.page.is_closed():
        try:
            video = state.page.video
            if video:
                video_path = await video.path()
        except Exception:
            pass

    if state.context:
        await state.context.close()
        state.context = None
    if state.browser:
        await state.browser.close()
        state.browser = None

    state.page = None

    return {"status": "closed", "video_path": video_path}


async def capture_screenshot(
    state: BrowserState,
    action_name: str,
    *,
    full_page: bool = False,
    selector: str | None = None,
) -> dict:
    """Capture a screenshot and accessibility snapshot, save to disk."""
    if not state.is_launched:
        return _error_result("Browser not launched")

    page = state.page
    state.screenshot_counter += 1
    filename = f"{state.screenshot_counter:03d}_{_sanitize(action_name)}.png"

    # Take screenshot
    ss_kwargs: dict = {"full_page": full_page}
    if selector:
        try:
            element = page.locator(selector)
            screenshot_bytes = await element.screenshot()
        except Exception as e:
            return _error_result(f"Screenshot of selector failed: {e}")
    else:
        screenshot_bytes = await page.screenshot(**ss_kwargs)

    # Save to disk
    filepath = ""
    if state.screenshot_dir:
        filepath = os.path.join(state.screenshot_dir, filename)
        with open(filepath, "wb") as f:
            f.write(screenshot_bytes)

    screenshot_b64 = base64.b64encode(screenshot_bytes).decode()

    # Accessibility snapshot
    a11y_text = await _get_accessibility_snapshot(page)

    return {
        "screenshot_path": filepath,
        "screenshot_base64": screenshot_b64,
        "page_url": page.url,
        "page_title": await page.title(),
        "accessibility_snapshot": a11y_text,
        "success": True,
        "error": None,
    }


async def _get_accessibility_snapshot(page: Page) -> str:
    """Get a text representation of the page's accessibility tree."""
    try:
        snapshot = await page.accessibility.snapshot()
        if snapshot:
            return _format_a11y_node(snapshot, indent=0)
        return await page.inner_text("body")
    except Exception:
        try:
            return await page.inner_text("body")
        except Exception:
            return "(could not read page content)"


def _format_a11y_node(node: dict, indent: int = 0) -> str:
    """Recursively format an accessibility tree node into readable text."""
    prefix = "  " * indent
    role = node.get("role", "")
    name = node.get("name", "")
    value = node.get("value", "")

    parts = [role]
    if name:
        parts.append(f"'{name}'")
    if value:
        parts.append(f"value='{value}'")

    # Add relevant states
    for key in ("checked", "pressed", "selected", "expanded", "disabled"):
        if node.get(key):
            parts.append(key)

    line = f"{prefix}{' '.join(parts)}"
    lines = [line]

    for child in node.get("children", []):
        lines.append(_format_a11y_node(child, indent + 1))

    return "\n".join(lines)


def _sanitize(name: str) -> str:
    """Sanitize a string for use in filenames."""
    return "".join(c if c.isalnum() or c in "_-" else "_" for c in name)[:50]


def _error_result(msg: str) -> dict:
    return {
        "screenshot_path": "",
        "screenshot_base64": "",
        "page_url": "",
        "page_title": "",
        "accessibility_snapshot": "",
        "success": False,
        "error": msg,
    }
