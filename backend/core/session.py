"""In-memory session store and lifecycle management."""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

from config import settings
from core.models import (
    ExecutionConfig,
    ParsedDocument,
    Session,
    SessionState,
    TestConfig,
    TestResult,
)


class SessionStore:
    """Simple in-memory session store. Replace with a DB for production."""

    def __init__(self):
        self._sessions: dict[str, Session] = {}

    def create(self) -> Session:
        session_id = uuid.uuid4().hex[:12]
        session = Session(id=session_id)

        # Create upload directory
        upload_dir = settings.uploads_dir / session_id
        upload_dir.mkdir(parents=True, exist_ok=True)

        self._sessions[session_id] = session
        return session

    def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def list_all(self) -> list[Session]:
        return list(self._sessions.values())

    def delete(self, session_id: str) -> bool:
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def update_state(self, session_id: str, state: SessionState) -> Session | None:
        session = self.get(session_id)
        if session:
            session.state = state
        return session

    def set_document(self, session_id: str, doc_path: str) -> Session | None:
        session = self.get(session_id)
        if session:
            session.document_path = doc_path
            session.state = SessionState.DOCUMENT_UPLOADED
        return session

    def set_config(self, session_id: str, config_path: str) -> Session | None:
        session = self.get(session_id)
        if session:
            session.config_path = config_path
        return session

    def set_parsed(
        self, session_id: str, parsed: ParsedDocument, config: TestConfig | None = None
    ) -> Session | None:
        session = self.get(session_id)
        if session:
            session.parsed_document = parsed
            if config:
                session.test_config = config
            session.state = SessionState.PARSED
        return session

    def set_execution_config(
        self, session_id: str, exec_config: ExecutionConfig
    ) -> Session | None:
        session = self.get(session_id)
        if session:
            session.execution_config = exec_config
            session.state = SessionState.CONFIGURED
        return session

    def set_export_dir(self, session_id: str) -> str:
        """Create and set the export directory for a session run."""
        session = self.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        export_dir = settings.exports_dir / f"session_{session_id}_{ts}"
        export_dir.mkdir(parents=True, exist_ok=True)
        session.export_dir = str(export_dir)
        return str(export_dir)

    def add_result(self, session_id: str, result: TestResult):
        session = self.get(session_id)
        if session:
            session.results.append(result)


# Singleton store
store = SessionStore()
