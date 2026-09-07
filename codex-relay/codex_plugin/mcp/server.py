"""Bifrost MCP server entry point.

The ``mcp`` package is an optional dependency of the Codex relay.  Importing
this module remains safe in the shared-core test environment; running the
server produces a focused installation error when the dependency is absent.
"""

from __future__ import annotations

from typing import Any

from .tools import register_all_tools

mcp: Any | None
_mcp_import_error: ImportError | None = None
try:
    from mcp.server import MCPServer
except ImportError as exc:  # pragma: no cover - exercised in minimal installs
    mcp = None
    _mcp_import_error = exc
else:
    mcp = MCPServer("bifrost-codex")
    register_all_tools(mcp)


def main() -> None:
    """Run the MCP server over its default stdio transport."""

    if mcp is None:
        detail = str(_mcp_import_error) if _mcp_import_error else "package unavailable"
        raise RuntimeError(
            "The Codex relay requires the optional 'mcp' dependency. "
            f"Install it with `pip install 'mcp>=2,<3'` ({detail})."
        )
    mcp.run()


if __name__ == "__main__":  # pragma: no cover - process entry point
    main()
