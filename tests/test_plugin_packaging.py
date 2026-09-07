"""Portable plugin packaging and machine-local runtime configuration."""

import json
import os
import sys
from pathlib import Path

import pytest
from codex_plugin.local_setup import prepare_plugin

SOURCE = Path(__file__).resolve().parents[1] / "codex-relay"


def test_manifest_uses_current_codex_layout():
    manifest = json.loads((SOURCE / ".codex-plugin" / "plugin.json").read_text("utf-8"))
    assert manifest["name"] == SOURCE.name
    assert manifest["skills"] == "./skills/"
    assert manifest["mcpServers"] == "./.mcp.json"
    assert "extensions" not in manifest
    assert isinstance(manifest["interface"]["defaultPrompt"], list)
    assert not (SOURCE / "plugin.json").exists()


def test_prepare_plugin_uses_explicit_runtime_and_copies_skills(tmp_path):
    python = tmp_path / "runtime" / "python.exe"
    python.parent.mkdir()
    python.touch()
    kicad_bin = tmp_path / "KiCad 8" / "bin"
    kicad_bin.mkdir(parents=True)
    cli = kicad_bin / ("kicad-cli.exe" if os.name == "nt" else "kicad-cli")
    cli.touch()
    destination = tmp_path / "plugins" / "codex-relay"
    authoring = tmp_path / "authoring"
    authoring.mkdir()
    (authoring / "manifest.json").write_text('{"local_only": true}')

    prepare_plugin(SOURCE, destination, python, kicad_bin, authoring)

    config = json.loads((destination / ".mcp.json").read_text("utf-8"))
    server = config["mcpServers"]["bifrost-codex"]
    assert server["command"] == str(python.resolve())
    assert server["args"] == ["-m", "codex_plugin.mcp.server"]
    assert server["env"]["PYTHONUTF8"] == "1"
    assert server["env"]["BIFROST_KICAD_CLI"] == str(cli)
    assert server["env"]["BIFROST_AUTHORING_HOME"] == str(authoring)
    assert "BIFROST_HOME" not in server["env"]
    assert (destination / "skills" / "kicad-pcb" / "SKILL.md").is_file()
    assert (destination / "skills" / "multisim-reader" / "SKILL.md").is_file()
    assert (destination / ".codex-plugin" / "plugin.json").is_file()
    assert {path.name for path in (destination / "skills").iterdir()} == {
        "kicad-pcb",
        "multisim-reader",
        "relay-core",
    }


def test_prepare_plugin_rejects_missing_runtime_before_writing(tmp_path):
    destination = tmp_path / "codex-relay"
    with pytest.raises(FileNotFoundError):
        prepare_plugin(SOURCE, destination, tmp_path / "missing", None)
    assert not destination.exists()


def test_prepare_plugin_does_not_overwrite_an_unrelated_plugin(tmp_path):
    destination = tmp_path / "other-plugin"
    with pytest.raises(ValueError):
        prepare_plugin(SOURCE, destination, Path(sys.executable), None)
    assert not destination.exists()
