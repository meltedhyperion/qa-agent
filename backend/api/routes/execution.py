"""Test execution endpoints."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException

from core.models import SessionState
from core.orchestrator import run_session
from core.session import store
from api.websocket import broadcast_to_session

router = APIRouter(prefix="/api/sessions", tags=["execution"])

# Track running tasks so they can be aborted
_running_tasks: dict[str, asyncio.Task] = {}


@router.post("/{session_id}/run")
async def start_execution(session_id: str):
    """Start test execution for a configured session."""
    session = store.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    if session.state == SessionState.RUNNING:
        raise HTTPException(400, "Session is already running")

    if session.state != SessionState.CONFIGURED:
        raise HTTPException(
            400,
            f"Session must be configured first. Current state: {session.state.value}",
        )

    # Create WebSocket broadcast callback
    async def ws_callback(data: dict):
        await broadcast_to_session(session_id, data)

    # Run in background task
    task = asyncio.create_task(_run_and_cleanup(session_id, ws_callback))
    _running_tasks[session_id] = task

    return {
        "session_id": session_id,
        "status": "started",
        "execution_mode": session.execution_config.execution_mode,
        "total_tests": len(session.execution_config.selected_test_ids),
    }


@router.get("/{session_id}/status")
async def get_execution_status(session_id: str):
    """Get current execution status (polling fallback for WebSocket)."""
    session = store.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    results = session.results
    return {
        "session_id": session_id,
        "state": session.state.value,
        "total": len(session.execution_config.selected_test_ids) if session.execution_config else 0,
        "completed": len(results),
        "passed": sum(1 for r in results if r.status == "passed"),
        "failed": sum(1 for r in results if r.status in ("failed", "error")),
        "skipped": sum(1 for r in results if r.status == "skipped"),
        "is_running": session_id in _running_tasks,
    }


@router.post("/{session_id}/abort")
async def abort_execution(session_id: str):
    """Abort a running execution."""
    task = _running_tasks.get(session_id)
    if not task:
        raise HTTPException(400, "No running execution to abort")

    task.cancel()
    store.update_state(session_id, SessionState.ABORTED)

    return {"session_id": session_id, "status": "aborted"}


async def _run_and_cleanup(session_id: str, ws_callback):
    """Run the session and clean up the task reference when done."""
    try:
        session = store.get(session_id)
        if session:
            await run_session(session, ws_broadcast=ws_callback)
    except asyncio.CancelledError:
        store.update_state(session_id, SessionState.ABORTED)
    except Exception as e:
        store.update_state(session_id, SessionState.FAILED)
        from loguru import logger
        logger.error(f"Session {session_id} failed: {e}")
    finally:
        _running_tasks.pop(session_id, None)
