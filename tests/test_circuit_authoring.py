"""Shared authoring contracts and native revision publishing."""

import pytest

from core.circuits import Circuit, apply_changes, publish_revision


def divider():
    return Circuit.model_validate(
        {
            "components": [
                {"reference": "V1", "kind": "VDC", "value": 5, "pins": {"1": "VIN", "2": "0"}},
                {"reference": "R1", "kind": "R", "value": 10000, "pins": {"1": "VIN", "2": "OUT"}},
                {"reference": "R2", "kind": "R", "value": 10000, "pins": {"1": "OUT", "2": "0"}},
            ]
        }
    )


def test_edit_operations_preserve_source_model():
    original = divider()
    revised = apply_changes(
        original,
        [
            {"op": "set_value", "reference": "R2", "value": 20000},
            {
                "op": "add",
                "component": {
                    "reference": "C1",
                    "kind": "C",
                    "value": 1e-6,
                    "pins": {"1": "OUT", "2": "0"},
                },
            },
            {"op": "move", "reference": "C1", "x_mm": 80, "y_mm": 40},
            {"op": "rotate", "reference": "R2", "rotation": 90},
        ],
    )
    assert original.components[2].value == 10000
    assert revised.components[2].value == 20000
    assert revised.components[-1].x_mm == 80
    assert revised.components[2].rotation == 90
    revised = apply_changes(
        revised,
        [
            {"op": "disconnect", "reference": "C1", "pin": "1"},
            {"op": "connect", "reference": "C1", "pin": "1", "net": "VIN"},
            {"op": "remove", "reference": "C1"},
        ],
    )
    assert len(revised.components) == 3


@pytest.mark.parametrize(
    "change",
    [
        {"op": "remove", "reference": "missing"},
        {"op": "set_value", "reference": "R1", "value": -1},
        {"op": "rotate", "reference": "R1", "rotation": 37},
        {"op": "connect", "reference": "R1", "pin": "5", "net": "OUT"},
        {"op": "move", "reference": "R1", "x_mm": float("nan"), "y_mm": 10},
        {"op": "remove", "reference": "R1", "ignore_errors": True},
    ],
)
def test_invalid_edits_fail_before_publication(change):
    with pytest.raises(ValueError):
        apply_changes(divider(), [change])


def test_duplicate_references_are_rejected():
    source = divider().model_dump()
    source["components"].append(source["components"][0])
    with pytest.raises(ValueError):
        Circuit.model_validate(source)


def test_publish_does_not_overwrite_without_confirmation(tmp_path):
    target = tmp_path / "native.ms14"
    target.write_bytes(b"original")
    with pytest.raises(FileExistsError):
        publish_revision(target, b"changed", overwrite=False)
    assert target.read_bytes() == b"original"
    publish_revision(target, b"changed", overwrite=True)
    assert target.read_bytes() == b"changed"


def test_publish_creates_new_revision(tmp_path):
    target = tmp_path / "revisions" / "native.kicad_sch"
    publish_revision(target, b"native", overwrite=False)
    assert target.read_bytes() == b"native"
    assert list(target.parent.iterdir()) == [target]


def test_divider_routing_has_no_shared_points_between_nets():
    from core.circuit_geometry import route_nets

    terminals = {
        "VIN": [(20, 24.92), (60, 26.19)],
        "0": [(20, 35.08), (100, 33.81)],
        "OUT": [(60, 33.81), (100, 26.19)],
    }
    boxes = [(17, 24.92, 23, 35.08), (57, 26.19, 63, 33.81), (97, 26.19, 103, 33.81)]
    wires, _ = route_nets(terminals, boxes)
    owners = {}
    assert {wire.net for wire in wires} == set(terminals)
    for wire in wires:
        for point in (wire.start, wire.end):
            assert owners.get(point, wire.net) == wire.net
            owners[point] = wire.net


def test_pin_on_rounded_obstacle_boundary_remains_reachable():
    from core.circuit_geometry import route_nets

    wires, _ = route_nets(
        {"OUT": [(10, 66.04), (30, 66.04)]},
        [(6.19, 69.85 - 3.81, 13.81, 73.66), (26.19, 69.85 - 3.81, 33.81, 73.66)],
    )
    assert wires
