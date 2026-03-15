"""Session management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.browser_check import check_all_browsers
from core.config_parser import parse_config
from core.llm_parser import parse_config_with_llm, parse_document_with_llm
from core.models import ExecutionConfig, ParsedDocument, TestConfig, SessionState
from core.session import store

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


class BrowserCheckRequest(BaseModel):
    browsers: list[str] = ["chromium"]
    custom_browsers: list[dict] = []


@router.post("/check-browsers")
async def check_browsers_endpoint(req: BrowserCheckRequest):
    """Check which browsers are available on this system.

    Returns availability status for each standard and custom browser.
    """
    results = check_all_browsers(req.browsers, req.custom_browsers)
    return {
        "results": [
            {
                "name": r.name,
                "available": r.available,
                "message": r.message,
                "path": r.path,
            }
            for r in results
        ],
    }


@router.get("")
async def list_sessions():
    """List all sessions."""
    sessions = store.list_all()
    return [
        {
            "id": s.id,
            "state": s.state.value,
            "created_at": s.created_at.isoformat(),
            "document": s.document_path,
            "has_config": s.config_path is not None,
            "test_case_count": (
                s.parsed_document.total_test_cases if s.parsed_document else 0
            ),
        }
        for s in sessions
    ]


@router.get("/{session_id}")
async def get_session(session_id: str):
    """Get full session details."""
    session = store.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    return session.model_dump(mode="json")


class ParseRequest(BaseModel):
    parsing_hint: str = ""
    model: str = "gpt-4o"


@router.post("/{session_id}/parse")
async def parse_document(session_id: str, body: ParseRequest | None = None):
    """Parse the uploaded test document and config file using an LLM.

    Accepts an optional parsing_hint to guide the LLM on where to find
    test cases in the document (e.g. 'Test cases are in Section 3 tables').
    """
    session = store.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    if not session.document_path:
        raise HTTPException(400, "No document uploaded")

    parsing_hint = body.parsing_hint if body else ""
    model = body.model if body and body.model else "gpt-4o"

    # ── Parse document with LLM ────────────────────────────────────────
    try:
        result = await parse_document_with_llm(
            session.document_path,
            model=model,
            parsing_hint=parsing_hint,
        )
    except Exception as e:
        raise HTTPException(400, f"Failed to parse document: {e}")

    parsed = ParsedDocument(**result)

    # ── Parse config ───────────────────────────────────────────────────
    test_config = None
    if session.config_path:
        try:
            # Try LLM parser first — it falls back to None for standard format
            llm_config = await parse_config_with_llm(session.config_path, model=model)
            if llm_config is not None:
                # LLM parsed a non-standard config
                test_config = TestConfig(
                    app_url=str(llm_config.get("app_url", "")),
                    credentials=llm_config.get("credentials", {}),
                    timeout_ms=int(llm_config.get("timeout_ms", 30000)),
                    model=str(llm_config.get("model", "gpt-4o")),
                    extra=llm_config.get("extra", {}),
                    test_specific=llm_config.get("test_specific", {}),
                )
            else:
                # Standard format — use the rigid parser
                test_config = parse_config(session.config_path)
        except Exception as e:
            raise HTTPException(400, f"Failed to parse config: {e}")

    store.set_parsed(session_id, parsed, test_config)

    return {
        "session_id": session_id,
        "document_title": parsed.document_title,
        "total_sections": parsed.total_sections,
        "total_test_cases": parsed.total_test_cases,
        "sections": [
            {
                "name": s.name,
                "test_case_count": len(s.test_cases),
                "test_cases": [tc.model_dump() for tc in s.test_cases],
            }
            for s in parsed.sections
        ],
        "config": test_config.model_dump() if test_config else None,
    }


@router.post("/{session_id}/configure")
async def configure_session(session_id: str, config: ExecutionConfig):
    """Set execution configuration for a session."""
    session = store.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    if session.state not in (SessionState.PARSED, SessionState.CONFIGURED):
        raise HTTPException(400, f"Session must be parsed first. Current state: {session.state.value}")

    # If no test IDs selected, select all from selected sections
    if not config.selected_test_ids and session.parsed_document:
        selected_sections = set(config.selected_sections)
        all_ids = []
        for section in session.parsed_document.sections:
            if not selected_sections or section.name in selected_sections:
                for tc in section.test_cases:
                    all_ids.append(tc.id)
        config.selected_test_ids = all_ids

    store.set_execution_config(session_id, config)

    return {
        "session_id": session_id,
        "state": "configured",
        "selected_test_count": len(config.selected_test_ids),
        "execution_mode": config.execution_mode,
        "concurrency": config.concurrency,
        "model": config.model,
    }


@router.delete("/{session_id}")
async def delete_session(session_id: str):
    """Delete a session and its data."""
    if not store.delete(session_id):
        raise HTTPException(404, "Session not found")
    return {"deleted": True}
