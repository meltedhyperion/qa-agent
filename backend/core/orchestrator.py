"""Test execution orchestrator — manages parallel/sequential test runs."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Any, Callable

from loguru import logger

from core.agent import execute_test_case
from core.browser_check import check_browser, check_custom_browser
from core.config_parser import get_test_config
from core.mcp_client import MCPClient
from core.models import (
    ExecutionConfig,
    ParsedTestCase,
    Session,
    SessionState,
    TestConfig,
    TestResult,
    WSExecutionComplete,
    WSExecutionStarted,
    WSTestStatus,
)
from core.session import store


@dataclass
class BrowserRun:
    """A browser to execute tests on."""

    name: str               # Display name (used in results and report)
    browser_type: str       # Playwright engine: 'chromium', 'firefox', 'webkit'
    executable_path: str    # Custom executable path (empty for standard browsers)


async def run_session(
    session: Session,
    ws_broadcast: Callable | None = None,
) -> list[TestResult]:
    """Run all selected test cases for a session across all configured browsers.

    If multiple browsers are configured, each browser gets its own subdirectory
    under the session export dir, and results are tagged with the browser name.
    """
    if not session.parsed_document or not session.execution_config or not session.test_config:
        raise ValueError("Session not fully configured")

    exec_config = session.execution_config
    test_config = session.test_config

    # Collect selected test cases
    selected = _get_selected_test_cases(session)
    if not selected:
        raise ValueError("No test cases selected")

    # Build list of browser runs (standard + custom)
    browser_runs = _build_browser_runs(exec_config)

    # ── Pre-flight browser availability check ─────────────────────────
    available_runs, skipped_results = _preflight_check(browser_runs, selected)

    if not available_runs:
        raise ValueError(
            "No browsers available to run tests. "
            "Check that selected browsers are installed on this system."
        )

    # Create export directory
    export_dir = store.set_export_dir(session.id)

    # Update state
    store.update_state(session.id, SessionState.RUNNING)

    total_tests = len(selected) * len(available_runs) + len(skipped_results)

    # Broadcast start
    if ws_broadcast:
        await ws_broadcast(WSExecutionStarted(
            total_tests=total_tests,
            execution_mode=exec_config.execution_mode,
        ).model_dump())

    model = exec_config.model or test_config.model or "gpt-4o"

    all_results: list[TestResult] = list(skipped_results)

    for run in available_runs:
        logger.info(f"Starting test run on browser: {run.name}")

        # When multiple browsers, each gets a subdirectory
        if len(available_runs) > 1 or skipped_results:
            browser_export_dir = os.path.join(export_dir, run.name)
            os.makedirs(browser_export_dir, exist_ok=True)
        else:
            browser_export_dir = export_dir

        if exec_config.execution_mode == "parallel":
            results = await _run_parallel(
                selected, test_config, exec_config, model,
                browser_export_dir, ws_broadcast,
                run.browser_type, run.executable_path, run.name,
            )
        else:
            results = await _run_sequential(
                selected, test_config, exec_config, model,
                browser_export_dir, ws_broadcast,
                run.browser_type, run.executable_path, run.name,
            )

        all_results.extend(results)

    # Store results
    for result in all_results:
        store.add_result(session.id, result)

    # Generate report
    await _generate_report(session, all_results, model)

    # Update state
    store.update_state(session.id, SessionState.COMPLETED)

    # Broadcast completion
    if ws_broadcast:
        await ws_broadcast(WSExecutionComplete(
            total=len(all_results),
            passed=sum(1 for r in all_results if r.status == "passed"),
            failed=sum(1 for r in all_results if r.status in ("failed", "error")),
            skipped=sum(1 for r in all_results if r.status == "skipped"),
        ).model_dump())

    return all_results


async def _run_sequential(
    test_cases: list[dict],
    test_config: TestConfig,
    exec_config: ExecutionConfig,
    model: str,
    export_dir: str,
    ws_broadcast: Callable | None,
    browser_type: str = "chromium",
    executable_path: str = "",
    browser_name: str = "",
) -> list[TestResult]:
    """Run test cases one after another."""
    results = []
    for tc in test_cases:
        result = await _run_single_test(
            tc, test_config, exec_config, model, export_dir, ws_broadcast,
            browser_type, executable_path, browser_name,
        )
        results.append(result)
    return results


async def _run_parallel(
    test_cases: list[dict],
    test_config: TestConfig,
    exec_config: ExecutionConfig,
    model: str,
    export_dir: str,
    ws_broadcast: Callable | None,
    browser_type: str = "chromium",
    executable_path: str = "",
    browser_name: str = "",
) -> list[TestResult]:
    """Run test cases in parallel with concurrency limit."""
    semaphore = asyncio.Semaphore(exec_config.concurrency)
    label = browser_name or browser_type

    async def run_with_sem(tc: dict) -> TestResult:
        async with semaphore:
            return await _run_single_test(
                tc, test_config, exec_config, model, export_dir, ws_broadcast,
                browser_type, executable_path, browser_name,
            )

    tasks = [asyncio.create_task(run_with_sem(tc)) for tc in test_cases]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Handle exceptions
    final_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            tc = test_cases[i]
            final_results.append(TestResult(
                test_id=tc.get("id", f"TC-{i}"),
                test_title=tc.get("title", "Unknown"),
                status="error",
                summary=f"Unexpected error: {result}",
                browser=label,
            ))
        else:
            final_results.append(result)

    return final_results


async def _run_single_test(
    test_case: dict,
    test_config: TestConfig,
    exec_config: ExecutionConfig,
    model: str,
    session_export_dir: str,
    ws_broadcast: Callable | None,
    browser_type: str = "chromium",
    executable_path: str = "",
    browser_name: str = "",
) -> TestResult:
    """Run a single test case with its own MCP server instance."""
    test_id = test_case.get("id", "unknown")
    test_title = test_case.get("title", "Untitled")
    label = browser_name or browser_type

    # Create test-specific export directory
    safe_id = test_id.replace("/", "_").replace(" ", "_")
    test_export_dir = os.path.join(session_export_dir, safe_id)
    os.makedirs(test_export_dir, exist_ok=True)

    # Merge config for this test case
    merged_config = get_test_config(test_config, test_id, test_title)

    # Broadcast status: queued → running
    if ws_broadcast:
        await ws_broadcast(WSTestStatus(
            test_id=test_id,
            test_title=test_title,
            status="running",
            total_steps=len(test_case.get("steps", [])),
        ).model_dump())

    # Retry logic
    max_retries = exec_config.max_retries
    last_result = None

    for attempt in range(max_retries + 1):
        try:
            async with MCPClient("mcp_servers.playwright_browser.server") as pw_mcp:
                result = await execute_test_case(
                    test_case=test_case,
                    config=merged_config,
                    model=model,
                    playwright_mcp=pw_mcp,
                    export_dir=test_export_dir,
                    custom_prompt=exec_config.system_prompt,
                    upload_folder=exec_config.upload_folder,
                    status_callback=ws_broadcast,
                    browser_type=browser_type,
                    executable_path=executable_path,
                )

            result.retry_count = attempt

            if result.status == "passed" or attempt >= max_retries:
                last_result = result
                break

            logger.info(f"[{test_id}] Attempt {attempt + 1} failed, retrying...")
            if ws_broadcast:
                await ws_broadcast(WSTestStatus(
                    test_id=test_id,
                    test_title=test_title,
                    status="retrying",
                ).model_dump())

            last_result = result

        except Exception as e:
            logger.error(f"[{test_id}] Attempt {attempt + 1} error: {e}")
            last_result = TestResult(
                test_id=test_id,
                test_title=test_title,
                status="error",
                summary=f"Error: {e}",
                browser=label,
            )
            if attempt >= max_retries:
                break

    # Broadcast final status
    if ws_broadcast and last_result:
        await ws_broadcast(WSTestStatus(
            test_id=test_id,
            test_title=test_title,
            status=last_result.status,
        ).model_dump())

    return last_result


async def _generate_report(
    session: Session,
    results: list[TestResult],
    model: str,
):
    """Generate the results .docx report using the Document MCP server."""
    if not session.export_dir:
        return

    try:
        async with MCPClient("mcp_servers.document.server") as doc_mcp:
            test_results_data = []
            for r in results:
                screenshot_paths = [
                    s.screenshot_path for s in r.steps
                    if s.screenshot_path and os.path.exists(s.screenshot_path)
                ]
                steps = [s.step_description for s in r.steps]

                test_results_data.append({
                    "test_title": f"[{r.browser}] {r.test_title}" if r.browser != "chromium" or len(set(x.browser for x in results)) > 1 else r.test_title,
                    "steps": steps,
                    "screenshot_paths": screenshot_paths,
                    "status": r.status,
                })

            await doc_mcp.call_tool("generate_report", {
                "session_path": session.export_dir,
                "test_results": test_results_data,
                "tester_name": model,
            })
    except Exception as e:
        logger.error(f"Report generation failed: {e}")


def _build_browser_runs(exec_config: ExecutionConfig) -> list[BrowserRun]:
    """Build the list of browser runs from standard + custom browsers."""
    runs = []

    for b in exec_config.browsers or ["chromium"]:
        runs.append(BrowserRun(name=b, browser_type=b, executable_path=""))

    for cb in exec_config.custom_browsers:
        # Custom browsers are always Chromium-based
        runs.append(BrowserRun(
            name=cb.name,
            browser_type="chromium",
            executable_path=cb.executable_path,
        ))

    return runs


def _preflight_check(
    browser_runs: list[BrowserRun],
    selected_tests: list[dict],
) -> tuple[list[BrowserRun], list[TestResult]]:
    """Check browser availability and split into available vs skipped.

    Returns:
        (available_runs, skipped_results) — skipped_results contains
        TestResult entries for every test that would have run on
        unavailable browsers.
    """
    available: list[BrowserRun] = []
    skipped_results: list[TestResult] = []

    for run in browser_runs:
        if run.executable_path:
            result = check_custom_browser(run.name, run.executable_path)
        else:
            result = check_browser(run.browser_type)

        if result.available:
            available.append(run)
        else:
            logger.warning(
                f"Browser '{run.name}' is not available: {result.message}. "
                f"Skipping {len(selected_tests)} tests for this browser."
            )
            for tc in selected_tests:
                skipped_results.append(TestResult(
                    test_id=tc.get("id", "unknown"),
                    test_title=tc.get("title", "Untitled"),
                    status="skipped",
                    summary=f"Browser '{run.name}' is not available: {result.message}",
                    browser=run.name,
                ))

    return available, skipped_results


def _get_selected_test_cases(session: Session) -> list[dict]:
    """Get the list of selected test cases as dicts."""
    if not session.parsed_document or not session.execution_config:
        return []

    selected_ids = set(session.execution_config.selected_test_ids)
    selected_sections = set(session.execution_config.selected_sections)

    cases = []
    for section in session.parsed_document.sections:
        if selected_sections and section.name not in selected_sections:
            continue
        for tc in section.test_cases:
            if selected_ids and tc.id not in selected_ids:
                continue
            cases.append(tc.model_dump())

    return cases
