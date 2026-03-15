"""LLM-powered document and configuration parsing.

Uses the configured LLM to intelligently extract test cases from any document
format, and to map arbitrary YAML configs to the required structure.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
from loguru import logger


# ── Document content extraction (raw) ────────────────────────────────────────


def extract_document_content(file_path: str) -> str:
    """Extract all text and table content from a .docx file as plain text.

    Preserves structure: headings, paragraphs, and tables are clearly marked
    so the LLM can understand the document layout.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Document not found: {file_path}")

    doc = Document(str(path))
    parts: list[str] = []

    from docx.oxml.ns import qn

    body = doc.element.body
    for child in body.iterchildren():
        if child.tag == qn("w:p"):
            para = Paragraph(child, doc)
            text = para.text.strip()
            if not text:
                continue

            style_name = para.style.name if para.style else ""
            if "Title" in style_name:
                parts.append(f"# {text}")
            elif "Heading" in style_name:
                level = _heading_level(style_name)
                parts.append(f"{'#' * level} {text}")
            else:
                parts.append(text)

        elif child.tag == qn("w:tbl"):
            table = Table(child, doc)
            parts.append(_table_to_markdown(table))

    return "\n\n".join(parts)


def _heading_level(style_name: str) -> int:
    match = re.search(r"(\d)", style_name)
    return int(match.group(1)) if match else 1


def _table_to_markdown(table: Table) -> str:
    """Convert a docx table to a markdown table string."""
    rows_text: list[list[str]] = []
    for row in table.rows:
        cells = []
        for cell in row.cells:
            text = " ".join(p.text.strip() for p in cell.paragraphs if p.text.strip())
            cells.append(text.replace("|", "/").replace("\n", " "))
        rows_text.append(cells)

    if not rows_text:
        return ""

    # Normalize column count
    max_cols = max(len(r) for r in rows_text)
    for r in rows_text:
        while len(r) < max_cols:
            r.append("")

    lines = []
    for i, row in enumerate(rows_text):
        lines.append("| " + " | ".join(row) + " |")
        if i == 0:
            lines.append("| " + " | ".join("---" for _ in row) + " |")

    return "\n".join(lines)


# ── LLM-powered document parsing ─────────────────────────────────────────────


DOCUMENT_PARSE_PROMPT = """\
You are a test case extraction assistant. You are given the content of a QA test document.

The document may contain business context, application details, requirements, and other non-test content. Your job is to find and extract ONLY the test cases.

Test cases may appear as:
- Rows in tables
- Numbered lists
- Sections with steps
- Any other format

{parsing_hint}

Extract all test cases and return them in EXACTLY this JSON format (no markdown, no code fences):
{{
  "document_title": "Title of the document",
  "sections": [
    {{
      "name": "Section name or category",
      "test_cases": [
        {{
          "id": "TC-001",
          "title": "Short descriptive title of the test case",
          "description": "Optional longer description",
          "steps": ["Step 1 description", "Step 2 description", "..."],
          "expected_result": "What should happen when all steps pass"
        }}
      ]
    }}
  ]
}}

Rules:
- If test cases don't have explicit IDs, generate them as TC-001, TC-002, etc.
- Each step should be a clear, actionable instruction the tester can follow.
- If steps are written as a paragraph, split them into individual steps.
- Group test cases into sections if the document has clear groupings, otherwise use a single section.
- Preserve the original intent and details of each test case.
- Do NOT invent test cases that aren't in the document.

DOCUMENT CONTENT:
{content}"""


async def parse_document_with_llm(
    file_path: str,
    model: str = "gpt-4o",
    parsing_hint: str = "",
) -> dict:
    """Parse a test document using an LLM to extract test cases.

    Args:
        file_path: Path to the .docx file.
        model: LiteLLM model identifier.
        parsing_hint: Optional user guidance on where/how to find test cases.
    """
    from litellm import acompletion

    # Extract raw content from the document
    content = extract_document_content(file_path)

    if not content.strip():
        raise ValueError("Document appears to be empty")

    # Truncate if very long (most models have ~128k context)
    max_chars = 100_000
    if len(content) > max_chars:
        content = content[:max_chars] + "\n\n... (document truncated due to length)"

    hint_block = ""
    if parsing_hint.strip():
        hint_block = f"USER GUIDANCE: {parsing_hint.strip()}\n"

    prompt = DOCUMENT_PARSE_PROMPT.format(
        content=content,
        parsing_hint=hint_block,
    )

    logger.info(f"Parsing document with LLM ({model}), content length: {len(content)} chars")

    response = await acompletion(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=8192,
        temperature=0,
    )

    raw_text = response.choices[0].message.content or ""

    # Extract JSON from response (handle markdown code fences)
    parsed = _extract_json(raw_text)

    if not parsed or "sections" not in parsed:
        raise ValueError(f"LLM did not return valid test case JSON. Raw response:\n{raw_text[:500]}")

    # Normalize into our expected format
    sections = parsed.get("sections", [])
    total_cases = sum(len(s.get("test_cases", [])) for s in sections)

    return {
        "filename": Path(file_path).name,
        "sections": sections,
        "total_sections": len(sections),
        "total_test_cases": total_cases,
        "document_title": parsed.get("document_title", ""),
    }


# ── LLM-powered config parsing ───────────────────────────────────────────────


CONFIG_PARSE_PROMPT = """\
You are a configuration parser. You are given the content of a YAML configuration file for a QA testing tool.

The file may use any structure or naming convention. Your job is to understand it and map it to the required format.

Return EXACTLY this JSON format (no markdown, no code fences):
{{
  "app_url": "URL of the application to test (empty string if not found)",
  "credentials": {{
    "username": "login username if found",
    "password": "login password if found"
  }},
  "timeout_ms": 30000,
  "model": "gpt-4o",
  "extra": {{}},
  "test_specific": {{
    "TC-001": {{
      "credentials": {{"username": "...", "password": "..."}},
      "inputs": {{"field_name": "value"}}
    }}
  }}
}}

Rules:
- Map any URL-like value to app_url (look for keys like url, app_url, base_url, host, target, etc.)
- Map any credential/auth data to credentials
- Map timeout values to timeout_ms (convert seconds to ms if needed)
- Map any LLM model name to model
- Put test-specific overrides in test_specific, keyed by test ID
- Put any remaining useful configuration in extra
- If a field is not found in the YAML, use the default value shown above

YAML CONTENT:
{content}"""


async def parse_config_with_llm(
    file_path: str,
    model: str = "gpt-4o",
) -> dict:
    """Parse a config file using an LLM to map it to the required structure.

    Args:
        file_path: Path to the YAML file.
        model: LiteLLM model identifier.
    """
    from litellm import acompletion

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {file_path}")

    content = path.read_text(encoding="utf-8")

    if not content.strip():
        raise ValueError("Config file is empty")

    # First try the rigid parser — if the YAML is already in the expected
    # format (global/tests), use it directly to save an LLM call.
    try:
        raw = yaml.safe_load(content)
        if isinstance(raw, dict) and "global" in raw:
            logger.info("Config file is in standard format, using rigid parser")
            return None  # Signal to caller to use the existing rigid parser
    except Exception:
        pass

    prompt = CONFIG_PARSE_PROMPT.format(content=content)

    logger.info(f"Parsing config with LLM ({model}), content length: {len(content)} chars")

    response = await acompletion(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=4096,
        temperature=0,
    )

    raw_text = response.choices[0].message.content or ""
    parsed = _extract_json(raw_text)

    if not parsed:
        raise ValueError(f"LLM did not return valid config JSON. Raw response:\n{raw_text[:500]}")

    return parsed


# ── Helpers ───────────────────────────────────────────────────────────────────


def _extract_json(text: str) -> dict | None:
    """Extract a JSON object from LLM output, handling code fences."""
    # Try direct parse first
    text = text.strip()
    if text.startswith("{"):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

    # Try extracting from code fences
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Try finding the first { ... } block
    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass

    return None
