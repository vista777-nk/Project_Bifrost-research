"""Exercise publication failure, concurrency, and MCP confirmation boundaries."""

import hashlib

from adapters.authoring import execute_authoring
from core.circuits import Circuit
from core.domain import Action


class Editor:
    suffix = ".native"

    def load(self, path):
        return Circuit.model_validate_json(path.read_bytes()), None

    def render(self, circuit, original, path):
        path.write_text(circuit.model_dump_json(), encoding="utf-8")

    def verify(self, path, circuit):
        return {"native_reopen": True}


def action(name="create_schematic", **parameters):
    return Action(
        action_id="test",
        task_id="test",
        app="kicad",
        action_type="write",
        action_name=name,
        parameters=parameters,
    )


def test_failed_native_validation_preserves_existing_output(tmp_path):
    class Reject(Editor):
        def verify(self, path, circuit):
            raise ValueError("Native connectivity mismatch")

    output = tmp_path / "revision.native"
    output.write_bytes(b"existing output")
    request = action(output_file=str(output), circuit={})
    request.confirmation_granted = True
    result = execute_authoring(request, Reject())
    assert not result.success and "connectivity mismatch" in result.summary
    assert output.read_bytes() == b"existing output"


def test_source_change_during_validation_cannot_publish(tmp_path):
    source, output = tmp_path / "original.native", tmp_path / "revision.native"
    source.write_text(
        Circuit(components=[{"reference": "R1", "kind": "R", "value": 10}]).model_dump_json()
    )

    class Concurrent(Editor):
        def verify(self, path, circuit):
            source.write_bytes(b"external change")
            return {}

    result = execute_authoring(
        action(
            "edit_schematic",
            input_file=str(source),
            output_file=str(output),
            expected_input_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            changes=[{"op": "set_value", "reference": "R1", "value": 20}],
        ),
        Concurrent(),
    )
    assert not result.success and "source changed" in result.summary
    assert not output.exists()
    assert source.read_bytes() == b"external change"


def test_preview_never_renders_or_publishes(tmp_path):
    class NoRender(Editor):
        def render(self, *args):
            raise AssertionError("Preview must not render")

    output = tmp_path / "new.native"
    result = execute_authoring(
        action(output_file=str(output), circuit={}), NoRender(), preview=True
    )
    assert result.success
    assert result.metadata["preview"]["native_validation_pending"]
    assert not output.exists()


def test_constructor_failure_is_structured(tmp_path):
    def missing_runtime():
        raise ValueError("Missing native runtime")

    result = execute_authoring(
        action(output_file=str(tmp_path / "new.native"), circuit={}), missing_runtime
    )
    assert not result.success and "Missing native runtime" in result.summary


def test_explicit_confirmation_cannot_overwrite_source(tmp_path):
    source = tmp_path / "original.native"
    original = Circuit(components=[{"reference": "R1", "kind": "R", "value": 10}])
    source.write_text(original.model_dump_json())
    checksum = hashlib.sha256(source.read_bytes()).hexdigest()
    request = action(
        "edit_schematic",
        input_file=str(source),
        output_file=str(source),
        expected_input_sha256=checksum,
        changes=[{"op": "set_value", "reference": "R1", "value": 20}],
    )
    request.confirmation_granted = True
    result = execute_authoring(request, Editor())
    assert not result.success and "distinct revision" in result.summary
    assert hashlib.sha256(source.read_bytes()).hexdigest() == checksum


def test_value_edit_does_not_snap_an_unchanged_imported_position(tmp_path):
    source, output = tmp_path / "original.native", tmp_path / "revision.native"
    original = Circuit(
        components=[{"reference": "R1", "kind": "R", "value": 10, "x_mm": 20.123, "y_mm": 30.456}]
    )
    source.write_text(original.model_dump_json())

    class GridEditor(Editor):
        def normalize(self, circuit):
            data = circuit.model_dump()
            for item in data["components"]:
                item.update(x_mm=round(item["x_mm"]), y_mm=round(item["y_mm"]))
            return Circuit.model_validate(data)

    result = execute_authoring(
        action(
            "edit_schematic",
            input_file=str(source),
            output_file=str(output),
            expected_input_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            changes=[{"op": "set_value", "reference": "R1", "value": 20}],
        ),
        GridEditor(),
    )
    assert result.success, result.summary
    revised, _ = Editor().load(output)
    assert revised.components[0].value == 20
    assert revised.components[0].x_mm == 20.123
    assert revised.components[0].y_mm == 30.456


def test_mcp_invalid_edit_fails_before_overwrite_confirmation(tmp_path, monkeypatch):
    from codex_plugin.mcp import tools

    from adapters.kicad.adapter import KiCadAdapter
    from core.actions import ActionExecutor

    adapter = KiCadAdapter()
    monkeypatch.setattr(adapter, "_schematic_editor", Editor)
    executor = ActionExecutor()
    executor.register_adapter(adapter)
    runtime = tools.RelayRuntime(executor, register_defaults=False)
    monkeypatch.setattr(tools, "_runtime", runtime)
    source, output = tmp_path / "original.native", tmp_path / "revision.native"
    source.write_text(Circuit().model_dump_json())
    output.write_bytes(b"existing output")
    result = tools._handle_run_action(
        {
            "app": "kicad",
            "action_name": "edit_schematic",
            "parameters": {
                "input_file": str(source),
                "output_file": str(output),
                "expected_input_sha256": "0" * 64,
                "changes": [{"op": "remove", "reference": "R1"}],
            },
        }
    )
    assert result["status"] == "failed"
    assert not runtime.pending
    assert output.read_bytes() == b"existing output"
    result = tools._handle_run_action(
        {
            "app": "kicad",
            "action_name": "create_schematic",
            "parameters": {
                "output_file": str(output),
                "circuit": {},
            },
        }
    )
    assert result["status"] == "confirmation_required"
    assert result["metadata"]["preview"]["circuit"]["components"] == []
    cancelled = tools._handle_confirm_action({"action_id": result["action_id"], "confirm": False})
    assert cancelled["success"]
    assert output.read_bytes() == b"existing output"
