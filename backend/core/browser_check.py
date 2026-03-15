"""Browser availability checks — pre-flight validation before test runs."""

from __future__ import annotations

import os
import platform
import shutil
from dataclasses import dataclass


# Browsers bundled and managed by Playwright — always available.
BUNDLED_BROWSERS = {"chromium", "firefox", "webkit"}

# Branded browsers that require system installation.
BRANDED_BROWSERS = {"chrome", "msedge"}


@dataclass
class BrowserCheckResult:
    name: str
    available: bool
    message: str
    path: str = ""


def _get_branded_browser_paths() -> dict[str, list[str]]:
    """Return candidate executable paths for branded browsers per platform."""
    system = platform.system()

    if system == "Darwin":
        return {
            "chrome": [
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            ],
            "msedge": [
                "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            ],
        }

    if system == "Windows":
        prog = os.environ.get("PROGRAMFILES", r"C:\Program Files")
        prog86 = os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")
        local = os.environ.get("LOCALAPPDATA", "")
        paths: dict[str, list[str]] = {
            "chrome": [
                os.path.join(prog, "Google", "Chrome", "Application", "chrome.exe"),
                os.path.join(prog86, "Google", "Chrome", "Application", "chrome.exe"),
            ],
            "msedge": [
                os.path.join(prog86, "Microsoft", "Edge", "Application", "msedge.exe"),
                os.path.join(prog, "Microsoft", "Edge", "Application", "msedge.exe"),
            ],
        }
        if local:
            paths["chrome"].append(
                os.path.join(local, "Google", "Chrome", "Application", "chrome.exe")
            )
        return paths

    # Linux / other
    return {
        "chrome": [
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
        ],
        "msedge": [
            "/usr/bin/microsoft-edge",
            "/usr/bin/microsoft-edge-stable",
        ],
    }


def check_browser(browser: str) -> BrowserCheckResult:
    """Check whether a standard browser is available on this system."""
    if browser in BUNDLED_BROWSERS:
        return BrowserCheckResult(
            name=browser,
            available=True,
            message=f"{browser} is bundled with Playwright — always available",
        )

    if browser in BRANDED_BROWSERS:
        # Also check PATH (works on all platforms)
        which_path = shutil.which(browser)
        if which_path:
            return BrowserCheckResult(
                name=browser,
                available=True,
                message=f"Found on PATH: {which_path}",
                path=which_path,
            )

        for p in _get_branded_browser_paths().get(browser, []):
            if p and os.path.isfile(p):
                return BrowserCheckResult(
                    name=browser,
                    available=True,
                    message=f"Found at {p}",
                    path=p,
                )

        return BrowserCheckResult(
            name=browser,
            available=False,
            message=(
                f"{browser} is not installed. "
                f"Install it or use 'npx playwright install {browser}' for branded browsers."
            ),
        )

    return BrowserCheckResult(
        name=browser,
        available=False,
        message=f"Unknown browser type: {browser}",
    )


def check_custom_browser(name: str, executable_path: str) -> BrowserCheckResult:
    """Check whether a custom browser executable exists."""
    if not executable_path:
        return BrowserCheckResult(
            name=name,
            available=False,
            message="No executable path provided",
        )

    if os.path.isfile(executable_path):
        return BrowserCheckResult(
            name=name,
            available=True,
            message=f"Found at {executable_path}",
            path=executable_path,
        )

    return BrowserCheckResult(
        name=name,
        available=False,
        message=f"Executable not found: {executable_path}",
    )


def check_all_browsers(
    browsers: list[str],
    custom_browsers: list[dict] | None = None,
) -> list[BrowserCheckResult]:
    """Check availability of all requested browsers."""
    results = [check_browser(b) for b in browsers]

    for cb in custom_browsers or []:
        results.append(
            check_custom_browser(cb.get("name", "custom"), cb.get("executable_path", ""))
        )

    return results
