"""Parse YAML configuration files for test suites."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from core.models import TestConfig


def parse_config(file_path: str) -> TestConfig:
    """Parse a YAML config file into a TestConfig object.

    The YAML structure is intentionally flexible. Expected top-level keys:
      global:
        app_url: "..."
        credentials: {username: ..., password: ...}
        timeout_ms: 30000
        model: "gpt-4o"
      tests:
        "TC-001":
          credentials: ...
          inputs: ...
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {file_path}")

    with open(path) as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict):
        raise ValueError("Config file must be a YAML mapping")

    global_cfg = raw.get("global", {})
    if not isinstance(global_cfg, dict):
        global_cfg = {}

    tests_cfg = raw.get("tests", {})
    if not isinstance(tests_cfg, dict):
        tests_cfg = {}

    return TestConfig(
        app_url=str(global_cfg.get("app_url", "")),
        credentials=_extract_dict(global_cfg, "credentials"),
        timeout_ms=int(global_cfg.get("timeout_ms", 30000)),
        model=str(global_cfg.get("model", "gpt-4o")),
        extra={k: v for k, v in global_cfg.items()
               if k not in ("app_url", "credentials", "timeout_ms", "model")},
        test_specific=tests_cfg,
    )


def get_test_config(config: TestConfig, test_id: str, test_title: str = "") -> dict[str, Any]:
    """Merge global config with test-specific overrides for a given test case.

    Looks up by test_id first, then by test_title.
    Returns a flat dict with all config values for the test.
    """
    # Start with global values
    merged: dict[str, Any] = {
        "app_url": config.app_url,
        "credentials": dict(config.credentials),
        "timeout_ms": config.timeout_ms,
        "model": config.model,
        **config.extra,
    }

    # Find test-specific overrides
    specific = config.test_specific.get(test_id) or config.test_specific.get(test_title) or {}

    if not isinstance(specific, dict):
        return merged

    # Override credentials if provided
    if "credentials" in specific and isinstance(specific["credentials"], dict):
        merged["credentials"].update(specific["credentials"])

    # Merge inputs
    if "inputs" in specific and isinstance(specific["inputs"], dict):
        merged["inputs"] = specific["inputs"]

    # Merge any other keys
    for k, v in specific.items():
        if k not in ("credentials", "inputs"):
            merged[k] = v

    return merged


def _extract_dict(source: dict, key: str) -> dict[str, str]:
    """Safely extract a dict value."""
    val = source.get(key, {})
    if isinstance(val, dict):
        return {str(k): str(v) for k, v in val.items()}
    return {}
