"""Prepare a machine-local plugin copy with a deterministic Python runtime.

Marketplace registration is deliberately separate. This command only writes
the selected plugin directory; it never edits Codex or marketplace settings.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path


def prepare_plugin(
    source: Path,
    destination: Path,
    python_executable: Path,
    kicad_bin: Path | None,
) -> Path:
    source = source.expanduser().resolve()
    destination = destination.expanduser().resolve()
    python_executable = python_executable.expanduser().resolve()
    manifest_path = source / ".codex-plugin" / "plugin.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if destination == source or destination.name != manifest["name"]:
        raise ValueError("Use a separate destination directory named after the plugin.")
    existing_manifest = destination / ".codex-plugin" / "plugin.json"
    if existing_manifest.exists():
        existing = json.loads(existing_manifest.read_text(encoding="utf-8"))
        if existing.get("name") != manifest["name"]:
            raise ValueError("Refusing to replace a different plugin.")
    if not python_executable.is_file():
        raise FileNotFoundError(f"Python runtime not found: {python_executable}")

    config = json.loads((source / ".mcp.json").read_text(encoding="utf-8"))
    server = config["mcpServers"]["bifrost-codex"]
    server["command"] = str(python_executable)
    if kicad_bin is not None:
        kicad_bin = kicad_bin.expanduser().resolve()
        cli = kicad_bin / ("kicad-cli.exe" if os.name == "nt" else "kicad-cli")
        if not cli.is_file():
            raise FileNotFoundError(f"KiCad CLI not found: {cli}")
        server["env"]["BIFROST_KICAD_CLI"] = str(cli)
        server["env"]["PATH"] = str(kicad_bin) + os.pathsep + os.environ.get("PATH", "")

    existing_manifest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(manifest_path, existing_manifest)
    # Only actual skills are distributed, not placeholder folders or build files.
    for skill in (source / "skills").glob("*/SKILL.md"):
        shutil.copytree(
            skill.parent, destination / "skills" / skill.parent.name, dirs_exist_ok=True
        )
    (destination / ".mcp.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--kicad-bin", type=Path)
    args = parser.parse_args()
    print(prepare_plugin(args.source, args.destination, args.python, args.kicad_bin))


if __name__ == "__main__":
    main()
