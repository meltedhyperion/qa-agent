"""Export and download endpoints."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from core.session import store

router = APIRouter(prefix="/api/sessions", tags=["export"])


@router.get("/{session_id}/report")
async def download_report(session_id: str):
    """Download the results report .docx."""
    session = store.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    if not session.export_dir:
        raise HTTPException(400, "No export available — run tests first")

    report_path = os.path.join(session.export_dir, "results_report.docx")
    if not os.path.exists(report_path):
        raise HTTPException(404, "Report not generated yet")

    return FileResponse(
        report_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename="results_report.docx",
    )


@router.get("/{session_id}/export")
async def download_full_export(session_id: str):
    """Download the full session export as a ZIP file."""
    session = store.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    if not session.export_dir or not os.path.exists(session.export_dir):
        raise HTTPException(400, "No export available — run tests first")

    # Create a temporary ZIP file
    zip_name = f"qa_session_{session_id}"
    tmp_dir = tempfile.mkdtemp()
    zip_path = shutil.make_archive(
        os.path.join(tmp_dir, zip_name),
        "zip",
        root_dir=os.path.dirname(session.export_dir),
        base_dir=os.path.basename(session.export_dir),
    )

    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=f"{zip_name}.zip",
    )


@router.get("/{session_id}/screenshots/{test_id}")
async def get_screenshots(session_id: str, test_id: str):
    """Get list of screenshots for a specific test case."""
    session = store.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    if not session.export_dir:
        raise HTTPException(400, "No export available")

    safe_id = test_id.replace("/", "_").replace(" ", "_")
    screenshots_dir = os.path.join(session.export_dir, safe_id, "screenshots")

    if not os.path.exists(screenshots_dir):
        return {"test_id": test_id, "screenshots": []}

    screenshots = []
    for fname in sorted(os.listdir(screenshots_dir)):
        if fname.endswith(".png"):
            screenshots.append({
                "filename": fname,
                "path": os.path.join(screenshots_dir, fname),
                "url": f"/api/sessions/{session_id}/screenshot-file/{safe_id}/{fname}",
            })

    return {"test_id": test_id, "screenshots": screenshots}


@router.get("/{session_id}/screenshot-file/{test_id}/{filename}")
async def get_screenshot_file(session_id: str, test_id: str, filename: str):
    """Serve a specific screenshot file."""
    session = store.get(session_id)
    if not session or not session.export_dir:
        raise HTTPException(404, "Not found")

    file_path = os.path.join(session.export_dir, test_id, "screenshots", filename)
    if not os.path.exists(file_path):
        raise HTTPException(404, "Screenshot not found")

    return FileResponse(file_path, media_type="image/png")


@router.get("/{session_id}/video/{test_id}")
async def get_video(session_id: str, test_id: str):
    """Stream the test recording video."""
    session = store.get(session_id)
    if not session or not session.export_dir:
        raise HTTPException(404, "Not found")

    safe_id = test_id.replace("/", "_").replace(" ", "_")
    recording_dir = os.path.join(session.export_dir, safe_id, "recording")

    if not os.path.exists(recording_dir):
        raise HTTPException(404, "Recording not found")

    # Find the video file
    for fname in os.listdir(recording_dir):
        if fname.endswith((".webm", ".mp4")):
            video_path = os.path.join(recording_dir, fname)
            media_type = "video/webm" if fname.endswith(".webm") else "video/mp4"
            return FileResponse(video_path, media_type=media_type)

    raise HTTPException(404, "No video file found")
