"""Opt-in native KiCad authoring acceptance, using the installed CLI."""

import hashlib
import os

import pytest

from adapters.authoring import execute_authoring
from adapters.kicad.schematic import KiCadSchematicEditor
from core.domain import Action

pytestmark = pytest.mark.hardware


def test_native_kicad_authoring_revisions(tmp_path):
    cli = os.environ.get("BIFROST_KICAD_TEST_CLI")
    if not cli:
        pytest.skip("Set BIFROST_KICAD_TEST_CLI to opt into native authoring tests.")
    editor = KiCadSchematicEditor(cli)

    def run(name, **parameters):
        result = execute_authoring(
            Action(
                action_id=name,
                task_id="acceptance",
                app="kicad",
                action_name=name,
                action_type="write",
                parameters=parameters,
            ),
            editor,
        )
        assert result.success, result.summary
        return result

    first = tmp_path / "divider.kicad_sch"
    created = run(
        "create_schematic",
        output_file=str(first),
        circuit={
            "components": [
                {
                    "reference": "V1",
                    "kind": "VDC",
                    "value": 5,
                    "x_mm": 20,
                    "y_mm": 30,
                    "pins": {"1": "VIN", "2": "0"},
                },
                {
                    "reference": "R1",
                    "kind": "R",
                    "value": 10000,
                    "x_mm": 60,
                    "y_mm": 30,
                    "pins": {"1": "VIN", "2": "OUT"},
                },
                {
                    "reference": "R2",
                    "kind": "R",
                    "value": 10000,
                    "x_mm": 100,
                    "y_mm": 30,
                    "pins": {"1": "OUT", "2": "0"},
                },
            ]
        },
    )
    assert created.metadata["verification"]["erc_passed"]
    original_hash = hashlib.sha256(first.read_bytes()).hexdigest()
    previous = first
    for index, changes in enumerate(
        [
            [{"op": "set_value", "reference": "R2", "value": 20000}],
            [
                {
                    "op": "add",
                    "component": {
                        "reference": "C1",
                        "kind": "C",
                        "value": 1e-6,
                        "x_mm": 100,
                        "y_mm": 70,
                        "pins": {"1": "OUT", "2": "0"},
                    },
                }
            ],
            [
                {"op": "move", "reference": "C1", "x_mm": 140, "y_mm": 70},
                {"op": "rotate", "reference": "C1", "rotation": 90},
            ],
            [{"op": "remove", "reference": "C1"}],
            [{"op": "disconnect", "reference": "R2", "pin": "1"}],
            [{"op": "connect", "reference": "R2", "pin": "1", "net": "OUT"}],
            [{"op": "replace", "reference": "R2", "kind": "L", "value": 0.01}],
        ]
    ):
        inspected = run("inspect_schematic", input_file=str(previous))
        output = tmp_path / f"revision-{index}.kicad_sch"
        result = run(
            "edit_schematic",
            input_file=str(previous),
            output_file=str(output),
            expected_input_sha256=inspected.metadata["input_sha256"],
            changes=changes,
        )
        verification = result.metadata["verification"]
        if changes[0]["op"] == "disconnect":
            violations = [v for sheet in verification["erc"]["sheets"] for v in sheet["violations"]]
            assert {v["type"] for v in violations} == {"label_dangling"}
        else:
            assert verification["erc_passed"], verification
        previous = output
    assert hashlib.sha256(first.read_bytes()).hexdigest() == original_hash
