"""File upload endpoints."""

from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile

from config import settings
from core.session import store

router = APIRouter(prefix="/api/upload", tags=["upload"])


@router.post("/document")
async def upload_document(file: UploadFile):
    """Upload a test document (.docx/.doc) and create a new session."""
    if not file.filename:
        raise HTTPException(400, "No file provided")

    ext = Path(file.filename).suffix.lower()
    if ext not in (".docx", ".doc"):
        raise HTTPException(400, f"Unsupported file type: {ext}. Use .docx or .doc")

    # Create session
    session = store.create()
    upload_dir = settings.uploads_dir / session.id
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Save file
    dest = upload_dir / file.filename
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    store.set_document(session.id, str(dest))

    return {"session_id": session.id, "filename": file.filename}


@router.post("/config/{session_id}")
async def upload_config(session_id: str, file: UploadFile):
    """Upload a YAML configuration file for an existing session."""
    session = store.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    if not file.filename:
        raise HTTPException(400, "No file provided")

    ext = Path(file.filename).suffix.lower()
    if ext not in (".yaml", ".yml"):
        raise HTTPException(400, f"Unsupported file type: {ext}. Use .yaml or .yml")

    upload_dir = settings.uploads_dir / session_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    dest = upload_dir / file.filename
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    store.set_config(session_id, str(dest))

    return {"session_id": session_id, "filename": file.filename}


@router.post("/files/{session_id}")
async def upload_test_files(session_id: str, files: list[UploadFile]):
    """Upload test files that may be needed during test execution (e.g., for file
    upload test cases)."""
    session = store.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    upload_dir = settings.uploads_dir / session_id / "test_files"
    upload_dir.mkdir(parents=True, exist_ok=True)

    filenames = []
    for file in files:
        if not file.filename:
            continue
        dest = upload_dir / file.filename
        with open(dest, "wb") as f:
            shutil.copyfileobj(file.file, f)
        filenames.append(file.filename)

    return {
        "session_id": session_id,
        "filenames": filenames,
        "upload_folder": str(upload_dir),
    }
