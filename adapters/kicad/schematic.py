"""KiCad 8 native schematic authoring through a structured S-expression parser."""

from __future__ import annotations

import copy
import math
import os
import shutil
import subprocess
import xml.etree.ElementTree as ET
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from uuid import uuid4

import sexpdata

from core.circuit_geometry import route_nets
from core.circuits import Circuit, Component


def s(name: str, *values: Any) -> list[Any]:
    return [sexpdata.Symbol(name), *values]


def children(node: list[Any], name: str) -> list[list[Any]]:
    return [item for item in node if isinstance(item, list) and item and str(item[0]) == name]


def one(node: list[Any], name: str) -> list[Any]:
    found = children(node, name)
    if len(found) != 1:
        raise ValueError(f"Expected one {name} field, found {len(found)}.")
    return found[0]


def uid() -> str:
    return str(uuid4())


CATALOG = {"R": "Device:R", "C": "Device:C", "L": "Device:L", "VDC": "Simulation_SPICE:VDC"}


@lru_cache(maxsize=16)
def library_symbol(directory: str, identifier: str) -> list[Any]:
    library, name = identifier.split(":", 1)
    tree = sexpdata.loads((Path(directory) / f"{library}.kicad_sym").read_text(encoding="utf-8"))
    symbol = next((item for item in children(tree, "symbol") if item[1] == name), None)
    if symbol is None or children(symbol, "extends"):
        raise ValueError(f"Unsupported or missing symbol definition: {identifier}")
    result = copy.deepcopy(symbol)
    result[1] = identifier
    return result


def pin_locations(
    definition: list[Any], x: float, y: float, rotation: int
) -> dict[str, tuple[float, float]]:
    angle = math.radians(rotation)
    result = {}
    for unit in children(definition, "symbol"):
        for pin in children(unit, "pin"):
            px, py = map(float, one(pin, "at")[1:3])
            result[str(one(pin, "number")[1])] = (
                round(x + px * math.cos(angle) - py * math.sin(angle), 6),
                round(y - px * math.sin(angle) - py * math.cos(angle), 6),
            )
    return result


class KiCadSchematicEditor:
    suffix = ".kicad_sch"

    def __init__(self, cli: str | None = None, symbols: str | None = None) -> None:
        self.cli = cli or os.environ.get("BIFROST_KICAD_CLI") or shutil.which("kicad-cli")
        if not self.cli:
            raise ValueError("Configure BIFROST_KICAD_CLI before schematic authoring.")
        default = Path(self.cli).resolve().parent.parent / "share" / "kicad" / "symbols"
        self.symbols = str(symbols or os.environ.get("KICAD8_SYMBOL_DIR", str(default)))

    def catalog(self) -> list[dict[str, Any]]:
        return [
            {
                "kind": kind,
                "library_id": identifier,
                "pins": ["1", "2"],
                "value_unit": {"R": "ohm", "C": "F", "L": "H", "VDC": "V"}[kind],
            }
            for kind, identifier in CATALOG.items()
        ]

    def normalize(self, circuit: Circuit) -> Circuit:
        data = circuit.model_dump()
        for item in data["components"]:
            item["x_mm"] = round(round(item["x_mm"] / 1.27) * 1.27, 6)
            item["y_mm"] = round(round(item["y_mm"] / 1.27) * 1.27, 6)
        return Circuit.model_validate(data)

    def _netlist(self, path: Path) -> ET.Element:
        with TemporaryDirectory(prefix="bifrost-kicad-netlist-") as directory:
            output = Path(directory) / "netlist.xml"
            result = subprocess.run(
                [
                    self.cli,
                    "sch",
                    "export",
                    "netlist",
                    "--format",
                    "kicadxml",
                    "-o",
                    str(output),
                    str(path),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=60,
            )
            if result.returncode or not output.is_file():
                raise ValueError(f"KiCad could not reopen the schematic: {result.stderr}")
            return ET.parse(output).getroot()

    def load(self, path: Path) -> tuple[Circuit, Any]:
        if path.suffix.lower() != self.suffix or path.stat().st_size > 32 * 1024 * 1024:
            raise ValueError("Use a KiCad schematic smaller than 32 MiB.")
        tree = sexpdata.loads(path.read_text(encoding="utf-8"))
        if str(tree[0]) != "kicad_sch" or one(tree, "version")[1] != 20231120:
            raise ValueError("This editor currently supports the KiCad 8 schematic schema only.")
        if children(tree, "sheet") or children(tree, "bus") or children(tree, "bus_entry"):
            raise ValueError("Hierarchical sheets and buses are not supported for authoring yet.")
        netlist = self._netlist(path)
        pins: dict[str, dict[str, str | None]] = defaultdict(dict)
        for net in netlist.findall("./nets/net"):
            name = str(net.get("name", "")).lstrip("/")
            if name == "GND":
                name = "0"
            for pin in net.findall("node"):
                pins[str(pin.get("ref"))][str(pin.get("pin"))] = (
                    None if name.startswith("unconnected-") else name
                )
        components = []
        for symbol in children(tree, "symbol"):
            if children(symbol, "mirror"):
                raise ValueError("Mirrored native symbols are not supported for authoring yet.")
            properties = {item[1]: item[2] for item in children(symbol, "property")}
            reference = str(properties.get("Reference", ""))
            identifier = str(one(symbol, "lib_id")[1])
            if reference.startswith("#") and identifier in {"power:GND", "power:PWR_FLAG"}:
                continue
            kind = next((key for key, value in CATALOG.items() if value == identifier), None)
            if kind is None:
                raise ValueError(
                    f"Unsupported symbol {identifier}; refusing to discard its content."
                )
            at = one(symbol, "at")
            components.append(
                Component(
                    reference=reference,
                    kind=kind,
                    value=float(properties["Value"]),
                    x_mm=float(at[1]),
                    y_mm=float(at[2]),
                    rotation=int(at[3]),
                    pins=pins[reference],
                )
            )
        titles = children(tree, "title_block")
        title = (
            str(one(titles[0], "title")[1])
            if titles and children(titles[0], "title")
            else path.stem
        )
        return Circuit(title=title, components=components), tree

    @staticmethod
    def _topology(circuit: Circuit):
        return {c.reference: c.model_dump(exclude={"value"}) for c in circuit.components}

    def preflight(self, circuit, original, previous):
        if original is None or previous is None:
            return
        if self._topology(circuit) != self._topology(previous):
            if str(one(original, "generator")[1]) != "bifrost":
                raise ValueError(
                    "Imported KiCad schematics support value edits only; topology editing "
                    "currently requires a Bifrost-authored schematic. No content was discarded."
                )
            if any(children(original, tag) for tag in ("global_label", "hierarchical_label")):
                raise ValueError("Topology edits cannot preserve these labels yet.")

    def _instance(
        self,
        definition: list[Any],
        reference: str,
        value: str,
        x: float,
        y: float,
        rotation: int,
        root_id: str,
        project: str,
        previous: list[Any] | None = None,
    ) -> list[Any]:
        if previous is not None and one(previous, "lib_id")[1] != definition[1]:
            previous = None
        instance = (
            copy.deepcopy(previous)
            if previous is not None
            else s(
                "symbol",
                s("lib_id", definition[1]),
                s("at", x, y, rotation),
                s("unit", 1),
                s("in_bom", sexpdata.Symbol("yes")),
                s("on_board", sexpdata.Symbol("yes")),
                s("dnp", sexpdata.Symbol("no")),
                s("uuid", uid()),
            )
        )
        one(instance, "at")[1:] = [x, y, rotation]
        one(instance, "lib_id")[1] = definition[1]
        properties = {item[1]: item for item in children(instance, "property")}
        for item in children(definition, "property"):
            if str(item[1]).startswith("ki_"):
                continue
            if item[1] not in properties:
                prop = copy.deepcopy(item)
                instance.append(prop)
                properties[prop[1]] = prop
        for index, (name, text) in enumerate((("Reference", reference), ("Value", value))):
            prop = properties[name]
            prop[2] = text
            one(prop, "at")[1:] = [x + 3.81, y - 1.27 + index * 2.54, 0]
        for prop in properties.values():
            if prop[1] not in {"Reference", "Value"}:
                one(prop, "at")[1:] = [x, y, 0]
        old_pins = {str(item[1]): item for item in children(instance, "pin")}
        for item in children(instance, "pin") + children(instance, "instances"):
            instance.remove(item)
        for pin in pin_locations(definition, x, y, rotation):
            instance.append(old_pins.get(pin, s("pin", pin, s("uuid", uid()))))
        instance.append(
            s(
                "instances",
                s(
                    "project",
                    project,
                    s("path", "/" + root_id, s("reference", reference), s("unit", 1)),
                ),
            )
        )
        return instance

    def render(self, circuit: Circuit, original: Any | None, path: Path) -> None:
        if original is not None:
            with TemporaryDirectory(prefix="bifrost-kicad-source-") as directory:
                snapshot = Path(directory) / "source.kicad_sch"
                snapshot.write_text(sexpdata.dumps(original), encoding="utf-8")
                previous, _ = self.load(snapshot)
            self.preflight(circuit, original, previous)
            if self._topology(circuit) == self._topology(previous):
                tree = copy.deepcopy(original)
                values = {c.reference: c.value for c in circuit.components}
                for symbol in children(tree, "symbol"):
                    properties = {item[1]: item for item in children(symbol, "property")}
                    reference = properties["Reference"][2]
                    if reference in values:
                        properties["Value"][2] = format(values[reference], ".15g")
                    for instances in children(symbol, "instances"):
                        for project in children(instances, "project"):
                            project[1] = path.stem
                path.write_text(sexpdata.dumps(tree) + "\n", encoding="utf-8")
                return
        tree = (
            copy.deepcopy(original)
            if original
            else s(
                "kicad_sch",
                s("version", 20231120),
                s("generator", sexpdata.Symbol("bifrost")),
                s("uuid", uid()),
                s("paper", "A4"),
                s("title_block", s("title", circuit.title)),
                s("lib_symbols"),
                s("sheet_instances", s("path", "/", s("page", "1"))),
            )
        )
        root_id = str(one(tree, "uuid")[1])
        library = one(tree, "lib_symbols")
        definitions = {str(item[1]): item for item in children(library, "symbol")}
        previous = {}
        old_wires = {}
        for wire in children(tree, "wire"):
            points = children(one(wire, "pts"), "xy")
            key = tuple(sorted(tuple(map(float, point[1:3])) for point in points))
            old_wires[key] = wire
        for symbol in children(tree, "symbol"):
            reference = next(
                item[2] for item in children(symbol, "property") if item[1] == "Reference"
            )
            previous[reference] = symbol
        for tag in ("symbol", "wire", "junction", "label", "no_connect"):
            for item in children(tree, tag):
                tree.remove(item)
        terminals: dict[str, list[tuple[float, float]]] = defaultdict(list)
        rectangles = []
        for component in circuit.components:
            identifier = CATALOG[component.kind]
            if identifier not in definitions:
                definitions[identifier] = library_symbol(self.symbols, identifier)
                library.append(copy.deepcopy(definitions[identifier]))
            definition = definitions[identifier]
            x, y = float(component.x_mm), float(component.y_mm)
            instance = self._instance(
                definition,
                component.reference,
                format(component.value, ".15g"),
                x,
                y,
                component.rotation,
                root_id,
                path.stem,
                previous.get(component.reference),
            )
            tree.append(instance)
            points = pin_locations(definition, x, y, component.rotation)
            xs, ys = zip(*points.values(), strict=False)
            rectangles.append(
                (
                    min(min(xs), x - 3.81),
                    min(min(ys), y - 3.81),
                    max(max(xs), x + 3.81),
                    max(max(ys), y + 3.81),
                )
            )
            for number, point in points.items():
                net = component.pins.get(number)
                terminals[net or f"__floating_{component.reference}_{number}"].append(point)
                if net is None:
                    tree.append(s("no_connect", s("at", *point), s("uuid", uid())))
        wires, junctions = route_nets(terminals, rectangles)
        for wire in wires:
            key = tuple(sorted((wire.start, wire.end)))
            tree.append(
                copy.deepcopy(old_wires[key])
                if key in old_wires
                else s(
                    "wire",
                    s("pts", s("xy", *wire.start), s("xy", *wire.end)),
                    s("stroke", s("width", 0), s("type", sexpdata.Symbol("default"))),
                    s("uuid", uid()),
                )
            )
        for point in junctions:
            tree.append(
                s(
                    "junction",
                    s("at", *point),
                    s("diameter", 0),
                    s("color", 0, 0, 0, 0),
                    s("uuid", uid()),
                )
            )
        for name, points in terminals.items():
            if name.startswith("__floating_"):
                continue
            point = points[0]
            tree.append(
                s(
                    "label",
                    "GND" if name == "0" else name,
                    s("at", *point, 0),
                    s(
                        "effects",
                        s("font", s("size", 1.27, 1.27)),
                        s("justify", sexpdata.Symbol("left"), sexpdata.Symbol("bottom")),
                    ),
                    s("uuid", uid()),
                )
            )
        max_x = max((float(c.x_mm) for c in circuit.components), default=100)
        max_y = max((float(c.y_mm) for c in circuit.components), default=100)
        one(tree, "paper")[1:] = ["User", max(297, max_x + 30), max(210, max_y + 30)]
        path.write_text(sexpdata.dumps(tree) + "\n", encoding="utf-8")

    def verify(self, path: Path, circuit: Circuit) -> dict[str, Any]:
        loaded, _ = self.load(path)
        if loaded.components != circuit.components:
            raise ValueError(
                "Native KiCad component, value, placement, or pin/net verification failed."
            )
        report = path.with_suffix(".erc.json")
        table = s("sym_lib_table", s("version", 7))
        for library in {value.split(":")[0] for value in CATALOG.values()}:
            table.append(
                s(
                    "lib",
                    s("name", library),
                    s("type", "KiCad"),
                    s("uri", (Path(self.symbols) / f"{library}.kicad_sym").as_posix()),
                    s("options", ""),
                    s("descr", ""),
                )
            )
        (path.parent / "sym-lib-table").write_text(sexpdata.dumps(table), encoding="utf-8")
        import json

        template = (
            Path(self.cli).resolve().parent.parent
            / "share"
            / "kicad"
            / "template"
            / "kicad.kicad_pro"
        )
        project = json.loads(template.read_text(encoding="utf-8")) if template.exists() else {}
        project.setdefault("meta", {})["filename"] = path.with_suffix(".kicad_pro").name
        path.with_suffix(".kicad_pro").write_text(json.dumps(project), encoding="utf-8")
        result = subprocess.run(
            [
                self.cli,
                "sch",
                "erc",
                "--format",
                "json",
                "--exit-code-violations",
                "-o",
                str(report),
                str(path),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
        )
        if result.returncode not in {0, 1, 5} or not report.exists():
            raise ValueError(f"KiCad ERC could not run: {result.stderr or result.stdout}")
        erc = json.loads(report.read_text(encoding="utf-8"))
        violations = [v for sheet in erc.get("sheets", []) for v in sheet.get("violations", [])]
        return {
            "native_reopen": True,
            "components": len(circuit.components),
            "erc_passed": not violations,
            "erc": erc,
        }
