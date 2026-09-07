"""Opt-in native authoring acceptance against the locally licensed Multisim."""

import hashlib
import os
from pathlib import Path

import pytest

from adapters.authoring import execute_authoring
from adapters.multisim.adapter import MultisimAdapter
from adapters.multisim.schematic import MultisimSchematicEditor
from core.domain import Action

pytestmark = pytest.mark.hardware


def test_native_multisim_authoring_revisions(tmp_path):
    home = os.environ.get("BIFROST_MULTISIM_AUTHORING_TEST_HOME")
    if not home:
        pytest.skip("Set BIFROST_MULTISIM_AUTHORING_TEST_HOME to opt in.")
    adapter = MultisimAdapter()
    editor = MultisimSchematicEditor(adapter, Path(home).resolve())

    def run(name, **parameters):
        result = execute_authoring(
            Action(
                action_id=name,
                task_id="acceptance",
                app="multisim",
                action_name=name,
                action_type="write",
                parameters=parameters,
            ),
            editor,
        )
        assert result.success, result.summary
        return result

    def voltage(path, expected):
        body = adapter._run_worker(
            "run_simulation",
            {
                "file_path": str(path),
                "analysis_type": "dc",
                "output_names": ["V(OUT)", "V(VIN)"],
            },
            60,
        )
        assert body.get("success"), body
        outputs = body["data"]["outputs"]
        assert outputs["V(OUT)"]["data"][1][0] == pytest.approx(expected, rel=1e-6)
        assert outputs["V(VIN)"]["data"][1][0] == pytest.approx(5)

    first = tmp_path / "divider.ms14"
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
    assert created.metadata["verification"]["native_reopen"]
    voltage(first, 2.5)
    hashes = {first: hashlib.sha256(first.read_bytes()).hexdigest()}
    previous = first
    batches = [
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
        [{"op": "disconnect", "reference": "C1", "pin": "1"}],
        [{"op": "connect", "reference": "C1", "pin": "1", "net": "OUT"}],
        [{"op": "remove", "reference": "C1"}],
        [{"op": "replace", "reference": "R2", "kind": "L", "value": 0.01}],
    ]
    for index, changes in enumerate(batches):
        inspected = run("inspect_schematic", input_file=str(previous))
        output = tmp_path / f"revision-{index}.ms14"
        edited = run(
            "edit_schematic",
            input_file=str(previous),
            output_file=str(output),
            expected_input_sha256=inspected.metadata["input_sha256"],
            changes=changes,
        )
        assert edited.metadata["verification"]["native_connections_verified"]
        if index in {0, 1, 2, 4, 5}:
            voltage(output, 10 / 3)
        hashes[output] = hashlib.sha256(output.read_bytes()).hexdigest()
        previous = output
    for path, checksum in hashes.items():
        assert hashlib.sha256(path.read_bytes()).hexdigest() == checksum
