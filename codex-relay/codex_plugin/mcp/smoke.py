"""Check a configured MCP server over stdio without modifying engineering files."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from mcp.client import Client
from mcp.client.stdio import StdioServerParameters

from .schemas import TOOL_INPUT_MODELS


async def check_server(parameters: StdioServerParameters, mode: str = "auto") -> dict[str, Any]:
    async with asyncio.timeout(45):
        async with Client(parameters, mode=mode, read_timeout_seconds=30) as client:
            tools = await client.list_tools()
            names = {tool.name for tool in tools.tools}
            if names != set(TOOL_INPUT_MODELS):
                raise RuntimeError(f"Unexpected MCP tools: {sorted(names)}")
            result = await client.call_tool("list_adapters", {})
            payload = result.structured_content
            if not payload or not payload.get("success"):
                raise RuntimeError(f"Adapter discovery failed: {result}")
            missing = await client.call_tool(
                "run_action", {"app": "missing", "action_name": "read"}
            )
            failure = missing.structured_content
            if not failure or failure.get("success"):
                raise RuntimeError("Missing adapters must return a structured failure.")
            return {
                "success": True,
                "transport": "stdio",
                "mode": mode,
                "tools": sorted(names),
                "adapters": payload["adapters"],
            }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--mode", choices=["auto", "legacy"], default="auto")
    args = parser.parse_args()
    config = {
        "command": sys.executable,
        "args": ["-m", "codex_plugin.mcp.server"],
        "env": {"PYTHONUTF8": "1"},
    }
    if args.config:
        config = json.loads(args.config.read_text(encoding="utf-8"))["mcpServers"]["bifrost-codex"]
    with TemporaryDirectory(prefix="bifrost-stdio-") as directory:
        parameters = StdioServerParameters(
            command=config["command"],
            args=config.get("args", []),
            env=config.get("env"),
            cwd=directory,
        )
        print(json.dumps(asyncio.run(check_server(parameters, args.mode)), indent=2))


if __name__ == "__main__":
    main()
