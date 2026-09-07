"""MCP SDK integration tests for the Codex relay server."""

from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("mcp")

from codex_plugin.mcp.server import mcp
from codex_plugin.mcp.tools import reset_runtime


def test_server_registers_and_calls_all_tools() -> None:
    assert mcp is not None
    reset_runtime()

    tools = asyncio.run(mcp.list_tools())
    tools_by_name = {tool.name: tool for tool in tools}
    assert set(tools_by_name) == {
        "list_adapters",
        "run_action",
        "validate_result",
        "collect_logs",
        "confirm_action",
        "preview_action",
    }

    run_action_tool = tools_by_name["run_action"]
    assert "always require confirm_action" in (run_action_tool.description or "")
    assert run_action_tool.input_schema["properties"]["mode"]["enum"] == [
        "dry_run",
        "normal",
        "force",
    ]
    assert run_action_tool.input_schema["properties"]["risk_level"]["enum"] == [
        "low",
        "medium",
        "high",
        "critical",
    ]

    result = asyncio.run(mcp.call_tool("list_adapters", {}))
    assert result.structured_content is not None
    assert result.structured_content["success"] is True
    assert result.structured_content["count"] == 2
