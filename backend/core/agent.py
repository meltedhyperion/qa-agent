"""AI Agent loop — interprets test steps and drives browser automation via MCP tools."""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from typing import Any, Callable

from loguru import logger

from core.models import StepResult, TestResult
from core.mcp_client import MCPClient
from core.prompt_builder import build_initial_user_message, build_system_prompt


async def execute_test_case(
    test_case: dict,
    config: dict[str, Any],
    model: str,
    playwright_mcp: MCPClient,
    export_dir: str,
    custom_prompt: str = "",
    upload_folder: str | None = None,
    status_callback: Callable | None = None,
    browser_type: str = "chromium",
    executable_path: str = "",
) -> TestResult:
    """Execute a single test case using the LLM agent loop.

    Args:
        test_case: Dict with id, title, steps, etc.
        config: Merged config dict for this test case.
        model: LiteLLM model identifier (e.g., 'gpt-4o').
        playwright_mcp: Started MCP client for playwright browser.
        export_dir: Path to this test case's export directory.
        custom_prompt: User-provided system prompt addition.
        upload_folder: Path to folder with files for upload.
        status_callback: Async callable for WebSocket status updates.
        browser_type: Browser engine — 'chromium', 'firefox', 'webkit', 'chrome', 'msedge'.
        executable_path: Path to custom browser executable (for enterprise browsers).

    Returns:
        TestResult with pass/fail status, step results, and summary.
    """
    from core.llm_client import acompletion

    start_time = time.time()
    test_id = test_case.get("id", "unknown")
    test_title = test_case.get("title", "Untitled")
    test_steps = test_case.get("steps", [])

    # ── Setup directories ────────────────────────────────────────────────
    screenshot_dir = os.path.join(export_dir, "screenshots")
    recording_dir = os.path.join(export_dir, "recording")
    download_dir = os.path.join(export_dir, "downloads")
    for d in (screenshot_dir, recording_dir, download_dir):
        os.makedirs(d, exist_ok=True)

    # ── Launch browser ───────────────────────────────────────────────────
    try:
        launch_args = {
            "headless": True,
            "browser_type": browser_type,
            "screenshot_dir": screenshot_dir,
            "video_dir": recording_dir,
            "download_dir": download_dir,
        }
        if executable_path:
            launch_args["executable_path"] = executable_path
        await playwright_mcp.call_tool("launch_browser", launch_args)
    except Exception as e:
        logger.error(f"[{test_id}] Failed to launch browser: {e}")
        return TestResult(
            test_id=test_id,
            test_title=test_title,
            status="error",
            summary=f"Failed to launch browser: {e}",
            duration_ms=int((time.time() - start_time) * 1000),
            browser=browser_type,
        )

    # ── Build tools list for LLM ─────────────────────────────────────────
    # Filter out lifecycle tools — the agent manages launch/close directly
    LIFECYCLE_TOOLS = {"launch_browser", "close_browser"}
    mcp_tools = [t for t in await playwright_mcp.list_tools() if t["name"] not in LIFECYCLE_TOOLS]
    llm_tools = _convert_mcp_tools_to_openai_format(mcp_tools)

    # ── Build prompt & messages ──────────────────────────────────────────
    system_prompt = build_system_prompt(test_case, config, custom_prompt, upload_folder)
    user_message = build_initial_user_message(test_case, config)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    step_results: list[StepResult] = []
    step_counter = 0
    max_iterations = 75  # Safety limit — higher for complex multi-app systems with waits

    # ── Helper: broadcast a step_update message ─────────────────────────
    async def _broadcast_step(
        action: str,
        detail: str,
        status: str,
        step_idx: int = 0,
        error: str | None = None,
    ):
        if not status_callback:
            return
        try:
            await status_callback({
                "type": "step_update",
                "test_id": test_id,
                "step_index": step_idx,
                "action": action,
                "action_detail": detail,
                "status": status,
                "step_description": f"{action}: {detail}" if detail else action,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": error,
            })
        except Exception:
            pass

    # ── Agent loop ───────────────────────────────────────────────────────
    for iteration in range(max_iterations):
        try:
            response = await acompletion(
                model=model,
                messages=messages,
                tools=llm_tools if llm_tools else None,
                max_tokens=4096,
            )
        except Exception as e:
            logger.error(f"[{test_id}] LLM API error: {e}")
            await _broadcast_step("llm_error", str(e)[:200], "failed", error=str(e))
            break

        choice = response.choices[0]

        if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
            # Capture any assistant text (reasoning/thinking) before tool calls
            assistant_text = choice.message.content or ""
            if assistant_text.strip():
                await _broadcast_step(
                    "thinking", assistant_text.strip()[:300], "info"
                )

            # Append assistant message
            messages.append(choice.message.model_dump())

            for tool_call in choice.message.tool_calls:
                fn_name = tool_call.function.name
                try:
                    fn_args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    fn_args = {}

                logger.info(f"[{test_id}] Tool call: {fn_name}({fn_args})")

                args_summary = _summarize_args(fn_args)

                # Broadcast: executing
                await _broadcast_step(fn_name, args_summary, "executing", step_counter + 1)

                # Execute via MCP
                try:
                    result = await playwright_mcp.call_tool(fn_name, fn_args)
                except Exception as e:
                    result = {"success": False, "error": str(e)}

                if not isinstance(result, dict):
                    result = {"result": str(result), "success": True}

                # Track step
                step_counter += 1
                screenshot_path = result.get("screenshot_path", "")
                step_ok = result.get("success", True)
                step_error = result.get("error")
                step_results.append(StepResult(
                    step_index=step_counter,
                    step_description=f"{fn_name}: {args_summary}",
                    action=fn_name,
                    status="passed" if step_ok else "failed",
                    screenshot_path=screenshot_path if screenshot_path else None,
                    error=step_error,
                    duration_ms=0,
                ))

                # Broadcast: step result
                await _broadcast_step(
                    fn_name, args_summary,
                    "passed" if step_ok else "failed",
                    step_counter,
                    error=step_error,
                )

                # Also broadcast test-level status
                if status_callback:
                    try:
                        await status_callback({
                            "type": "test_status",
                            "test_id": test_id,
                            "test_title": test_title,
                            "status": "running",
                            "current_step": step_counter,
                            "total_steps": len(test_steps),
                            "last_action": f"{fn_name}: {args_summary}",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        })
                    except Exception:
                        pass

                # Build tool result for LLM
                tool_result_content = _build_tool_result_content(
                    result,
                    include_image=_should_include_image(fn_name, step_counter),
                )

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_result_content,
                })

        elif choice.finish_reason == "stop" or not choice.message.tool_calls:
            # Agent is done
            final_text = choice.message.content or ""
            logger.info(f"[{test_id}] Agent finished: {final_text[:200]}")

            status = _parse_test_status(final_text)
            duration_ms = int((time.time() - start_time) * 1000)

            # Close browser to finalize video
            try:
                close_result = await playwright_mcp.call_tool("close_browser", {})
                video_path = (
                    close_result.get("video_path")
                    if isinstance(close_result, dict)
                    else None
                )
            except Exception:
                video_path = None

            return TestResult(
                test_id=test_id,
                test_title=test_title,
                status=status,
                steps=step_results,
                summary=final_text,
                duration_ms=duration_ms,
                video_path=video_path,
                browser=browser_type,
            )

        else:
            # Unexpected finish reason
            logger.warning(f"[{test_id}] Unexpected finish_reason: {choice.finish_reason}")
            break

    # ── Fallback: max iterations reached ─────────────────────────────────
    try:
        await playwright_mcp.call_tool("close_browser", {})
    except Exception:
        pass

    return TestResult(
        test_id=test_id,
        test_title=test_title,
        status="error",
        steps=step_results,
        summary="Agent loop exceeded maximum iterations",
        duration_ms=int((time.time() - start_time) * 1000),
        browser=browser_type,
    )


# ── Helpers ──────────────────────────────────────────────────────────────────


def _convert_mcp_tools_to_openai_format(mcp_tools: list[dict]) -> list[dict]:
    """Convert MCP tool definitions to OpenAI function-calling format."""
    tools = []
    for tool in mcp_tools:
        schema = tool.get("input_schema", {})
        # Remove the 'ctx' parameter if present (it's injected by FastMCP)
        properties = schema.get("properties", {})
        properties.pop("ctx", None)
        required = schema.get("required", [])
        required = [r for r in required if r != "ctx"]

        tools.append({
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        })
    return tools


def _build_tool_result_content(result: dict, include_image: bool = False) -> str:
    """Build the content string for a tool result message sent back to the LLM."""
    parts = []

    success = result.get("success", True)
    if success:
        parts.append("Action completed successfully.")
    else:
        parts.append(f"Action FAILED: {result.get('error', 'Unknown error')}")

    url = result.get("page_url", "")
    title = result.get("page_title", "")
    if url:
        parts.append(f"Current URL: {url}")
    if title:
        parts.append(f"Page title: {title}")

    a11y = result.get("accessibility_snapshot", "")
    if a11y:
        # Truncate if very long to save tokens
        if len(a11y) > 8000:
            a11y = a11y[:8000] + "\n... (truncated)"
        parts.append(f"\nPage accessibility snapshot:\n{a11y}")

    # For now, we include images as text references.
    # Vision-capable models would receive base64 images via content blocks,
    # but for simplicity and token efficiency, we use the accessibility snapshot.
    if include_image and result.get("screenshot_path"):
        parts.append(f"\n[Screenshot saved to: {result['screenshot_path']}]")

    return "\n".join(parts)


def _should_include_image(tool_name: str, step_counter: int) -> bool:
    """Decide whether to note the screenshot in the LLM's context."""
    if tool_name == "take_screenshot":
        return True
    if tool_name == "navigate" and step_counter <= 2:
        return True
    if step_counter % 5 == 0:
        return True
    return False


def _parse_test_status(final_text: str) -> str:
    """Extract PASSED/FAILED from the agent's final output."""
    text_upper = final_text.upper()
    if "TEST RESULT: PASSED" in text_upper:
        return "passed"
    if "TEST RESULT: FAILED" in text_upper:
        return "failed"
    # Fallback heuristics
    if "PASSED" in text_upper and "FAILED" not in text_upper:
        return "passed"
    if "FAILED" in text_upper:
        return "failed"
    return "error"


def _summarize_args(args: dict) -> str:
    """Create a short summary of tool call arguments."""
    parts = []
    for k, v in args.items():
        val_str = str(v)
        if len(val_str) > 50:
            val_str = val_str[:50] + "..."
        parts.append(f"{k}={val_str}")
    return ", ".join(parts) if parts else ""
