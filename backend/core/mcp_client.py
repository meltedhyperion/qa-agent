"""MCP stdio client wrapper for communicating with MCP servers."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class MCPClient:
    """Manages an MCP server subprocess over stdio."""

    def __init__(self, server_module: str, env: dict[str, str] | None = None):
        """
        Args:
            server_module: Python module path to run (e.g., 'mcp_servers.document.server')
            env: Optional environment variables for the subprocess.
        """
        self.server_module = server_module
        self.env = env
        self._session: ClientSession | None = None
        self._read = None
        self._write = None
        self._streams_cm = None
        self._session_cm = None

    async def start(self):
        """Spawn the MCP server subprocess and initialize the connection."""
        server_params = StdioServerParameters(
            command=sys.executable,
            args=["-m", self.server_module],
            env=self.env,
            cwd=str(Path(__file__).resolve().parent.parent),
        )

        self._streams_cm = stdio_client(server_params)
        self._read, self._write = await self._streams_cm.__aenter__()

        self._session_cm = ClientSession(self._read, self._write)
        self._session = await self._session_cm.__aenter__()
        await self._session.initialize()

    async def stop(self):
        """Close the MCP session and terminate the subprocess."""
        if self._session_cm:
            try:
                await self._session_cm.__aexit__(None, None, None)
            except Exception:
                pass
        if self._streams_cm:
            try:
                await self._streams_cm.__aexit__(None, None, None)
            except Exception:
                pass
        self._session = None

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        """Call a tool on the MCP server."""
        if not self._session:
            raise RuntimeError("MCP client not started")

        result = await self._session.call_tool(name, arguments or {})
        # Extract text content from the result
        if hasattr(result, "content") and result.content:
            # MCP returns content blocks; extract text
            texts = []
            for block in result.content:
                if hasattr(block, "text"):
                    texts.append(block.text)
            if len(texts) == 1:
                # Try to parse as JSON
                import json
                try:
                    return json.loads(texts[0])
                except (json.JSONDecodeError, TypeError):
                    return texts[0]
            return "\n".join(texts) if texts else result
        return result

    async def list_tools(self) -> list[dict]:
        """Get available tools from the MCP server."""
        if not self._session:
            raise RuntimeError("MCP client not started")

        result = await self._session.list_tools()
        tools = []
        for tool in result.tools:
            tools.append({
                "name": tool.name,
                "description": tool.description or "",
                "input_schema": tool.inputSchema if hasattr(tool, "inputSchema") else {},
            })
        return tools

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *args):
        await self.stop()
