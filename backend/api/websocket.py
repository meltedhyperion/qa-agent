"""WebSocket hub for real-time execution status streaming."""

from __future__ import annotations

import json
from collections import defaultdict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

router = APIRouter()

# Active WebSocket connections per session
_connections: dict[str, list[WebSocket]] = defaultdict(list)


@router.websocket("/ws/sessions/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for live test execution updates."""
    await websocket.accept()
    _connections[session_id].append(websocket)
    logger.info(f"WebSocket connected for session {session_id}")

    try:
        # Keep connection alive — client can send pings or commands
        while True:
            data = await websocket.receive_text()
            # Could handle client commands here (e.g., abort)
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session {session_id}")
    finally:
        _connections[session_id].remove(websocket)
        if not _connections[session_id]:
            del _connections[session_id]


async def broadcast_to_session(session_id: str, data: dict):
    """Broadcast a message to all WebSocket clients watching a session."""
    connections = _connections.get(session_id, [])
    if not connections:
        return

    message = json.dumps(data)
    dead = []
    for ws in connections:
        try:
            await ws.send_text(message)
        except Exception:
            dead.append(ws)

    # Clean up dead connections
    for ws in dead:
        try:
            _connections[session_id].remove(ws)
        except ValueError:
            pass
