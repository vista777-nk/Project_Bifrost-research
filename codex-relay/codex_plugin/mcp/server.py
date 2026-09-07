"""Bifrost MCP server entry point.

The ``mcp`` package is an optional dependency of the Codex relay.  Importing
this module remains safe in the shared-core test environment; running the
server produces a focused installation error when the dependency is absent.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any


def _add_monorepo_root() -> None:
    """Make sibling core/adapters importable for local plugin installs."""

    plugin_root = Path(
        os.environ.get("BIFROST_HOME", Path(__file__).resolve().parents[2])
    ).resolve()
    repository_root = plugin_root.parent
    if (repository_root / "core").is_dir() and str(repository_root) not in sys.path:
        sys.path.insert(0, str(repository_root))


_add_monorepo_root()

from .tools import register_all_tools  # noqa: E402

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
