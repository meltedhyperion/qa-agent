from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


# ── Document Parsing Models ──────────────────────────────────────────────────


class ParsedTestCase(BaseModel):
    id: str
    title: str
    description: str | None = ""
    steps: list[str] = Field(default_factory=list)
    expected_result: str | None = ""
    raw_text: str = ""


class ParsedSection(BaseModel):
    name: str
    heading_level: int = 1
    test_cases: list[ParsedTestCase] = Field(default_factory=list)


class ParsedDocument(BaseModel):
    filename: str
    sections: list[ParsedSection] = Field(default_factory=list)
    total_sections: int = 0
    total_test_cases: int = 0
    document_title: str = ""


# ── Configuration Models ─────────────────────────────────────────────────────


class TestConfig(BaseModel):
    """Full resolved config for a session — global + per-test merged."""

    app_url: str = ""
    credentials: dict[str, str] = Field(default_factory=dict)
    timeout_ms: int = 30000
    model: str = "gpt-4o"
    extra: dict[str, Any] = Field(default_factory=dict)
    test_specific: dict[str, dict[str, Any]] = Field(default_factory=dict)


class CustomBrowser(BaseModel):
    """A custom/enterprise browser identified by display name and executable path."""

    name: str = Field(description="Display name, e.g. 'Brave', 'Island', 'Arc'")
    executable_path: str = Field(description="Absolute path to the browser executable")


class ExecutionConfig(BaseModel):
    selected_sections: list[str] = Field(default_factory=list)
    selected_test_ids: list[str] = Field(default_factory=list)
    execution_mode: Literal["parallel", "sequential"] = "sequential"
    concurrency: int = 3
    model: str = "gpt-4o"
    system_prompt: str = ""
    upload_folder: str | None = None
    max_retries: int = 0
    browsers: list[str] = Field(
        default_factory=lambda: ["chromium"],
        description="Standard browsers: 'chromium', 'firefox', 'webkit', 'chrome', 'msedge'",
    )
    custom_browsers: list[CustomBrowser] = Field(
        default_factory=list,
        description="Custom/enterprise Chromium-based browsers with executable paths",
    )


# ── Execution Models ─────────────────────────────────────────────────────────


class StepResult(BaseModel):
    step_index: int
    step_description: str = ""
    action: str = ""
    status: Literal["passed", "failed", "skipped"] = "passed"
    screenshot_path: str | None = None
    error: str | None = None
    duration_ms: int = 0


class TestResult(BaseModel):
    test_id: str
    test_title: str
    status: Literal["passed", "failed", "skipped", "error"] = "passed"
    steps: list[StepResult] = Field(default_factory=list)
    summary: str = ""
    duration_ms: int = 0
    video_path: str | None = None
    retry_count: int = 0
    browser: str = "chromium"


# ── Session Models ───────────────────────────────────────────────────────────


class SessionState(str, enum.Enum):
    CREATED = "created"
    DOCUMENT_UPLOADED = "document_uploaded"
    PARSED = "parsed"
    CONFIGURED = "configured"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"


class Session(BaseModel):
    id: str
    state: SessionState = SessionState.CREATED
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # File paths (populated as user uploads)
    document_path: str | None = None
    config_path: str | None = None

    # Parsed data
    parsed_document: ParsedDocument | None = None
    test_config: TestConfig | None = None
    execution_config: ExecutionConfig | None = None

    # Results
    results: list[TestResult] = Field(default_factory=list)

    # Runtime
    export_dir: str | None = None


# ── WebSocket Messages ───────────────────────────────────────────────────────


class WSExecutionStarted(BaseModel):
    type: Literal["execution_started"] = "execution_started"
    total_tests: int
    execution_mode: str
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class WSTestStatus(BaseModel):
    type: Literal["test_status"] = "test_status"
    test_id: str
    test_title: str
    status: str
    current_step: int = 0
    total_steps: int = 0
    last_action: str = ""
    screenshot_url: str | None = None
    error: str | None = None
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class WSStepUpdate(BaseModel):
    type: Literal["step_update"] = "step_update"
    test_id: str
    step_index: int
    step_description: str = ""
    action: str = ""
    action_detail: str = ""
    status: str = "executing"
    screenshot_url: str | None = None
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class WSExecutionComplete(BaseModel):
    type: Literal["execution_complete"] = "execution_complete"
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    report_url: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
