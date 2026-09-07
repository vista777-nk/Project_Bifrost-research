"""Real subprocess transport tests, isolated from local software installations."""

import asyncio
import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("mcp")

from codex_plugin.mcp.smoke import check_server
from mcp.client.stdio import StdioServerParameters


@pytest.mark.parametrize("mode", ["auto", "legacy"])
def test_server_stdio_from_another_directory(tmp_path, mode):
    root = Path(__file__).resolve().parents[1]
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "codex_plugin.mcp.server"],
        cwd=tmp_path,
        env={
            "PYTHONPATH": os.pathsep.join([str(root), str(root / "codex-relay")]),
            "PYTHONUTF8": "1",
        },
    )

    result = asyncio.run(check_server(parameters, mode))

    assert result["success"] is True
    assert result["transport"] == "stdio"
    assert len(result["tools"]) == 6
    assert {adapter["name"] for adapter in result["adapters"]} == {"kicad", "multisim"}
