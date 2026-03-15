"""Document MCP Server — parses .docx test documents and generates result reports.

Run as: python -m mcp_servers.document.server
Transport: stdio (session-based)
"""

from __future__ import annotations

from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from .parser import (
    extract_test_cases as _extract_test_cases,
    list_sections as _list_sections,
    parse_document as _parse_document,
)
from .report_generator import (
    append_test_result as _append_test_result,
    generate_report as _generate_report,
)

mcp = FastMCP(
    "document-server",
    instructions=(
        "MCP server for parsing .docx test documents and generating "
        "formatted test result reports."
    ),
)


@mcp.tool()
def parse_document(
    file_path: Annotated[
        str, Field(description="Absolute path to the .docx test document")
    ],
) -> dict:
    """Parse a .docx test document and extract all sections and test cases.

    Returns structured data with sections, each containing test cases with
    id, title, steps, description, and expected results.
    """
    return _parse_document(file_path)


@mcp.tool()
def list_sections(
    file_path: Annotated[
        str, Field(description="Absolute path to the .docx test document")
    ],
) -> dict:
    """Quick scan returning section names and test case counts without full parsing."""
    return _list_sections(file_path)


@mcp.tool()
def extract_test_cases(
    file_path: Annotated[
        str, Field(description="Absolute path to the .docx test document")
    ],
    section_name: Annotated[
        str, Field(description="Exact section heading name to extract from")
    ],
) -> dict:
    """Extract test cases from a specific named section of the document."""
    return _extract_test_cases(file_path, section_name)


@mcp.tool()
def generate_report(
    session_path: Annotated[
        str, Field(description="Path to the session export folder")
    ],
    test_results: Annotated[
        list[dict],
        Field(
            description=(
                "List of test result objects. Each must have: "
                "test_title (str), steps (list[str]), "
                "screenshot_paths (list[str]), status (str)"
            )
        ),
    ],
    tester_name: Annotated[
        str, Field(description="Name for the 'Verified By' column")
    ] = "GPT-4o",
    test_date: Annotated[
        str | None, Field(description="Date string (defaults to today)")
    ] = None,
) -> dict:
    """Generate a formatted results .docx report with a 4-column table.

    Columns: Test Title | Steps (numbered) | Screenshots (stacked) | Verified By
    """
    return _generate_report(session_path, test_results, tester_name, test_date)


@mcp.tool()
def append_test_result(
    report_path: Annotated[
        str, Field(description="Path to existing results_report.docx")
    ],
    test_result: Annotated[
        dict,
        Field(
            description=(
                "Single test result with: test_title, steps, "
                "screenshot_paths, status"
            )
        ),
    ],
    tester_name: Annotated[
        str, Field(description="Name for the 'Verified By' column")
    ] = "GPT-4o",
) -> dict:
    """Add a single test result row to an existing report.

    Creates the report if it doesn't exist yet.
    """
    return _append_test_result(report_path, test_result, tester_name)


if __name__ == "__main__":
    mcp.run(transport="stdio")
