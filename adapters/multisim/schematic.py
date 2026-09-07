"""Version-scoped native XML authoring; never drives desktop input.

Native object-link conventions were cross-checked against the MIT-licensed
Multisim MCP builder; see THIRD_PARTY_NOTICES.md. No vendor templates are shipped.
"""

from __future__ import annotations

import copy
import csv
import io
import math
from collections import defaultdict
from pathlib import Path
from typing import Any
from uuid import uuid4

import networkx as nx
from lxml import etree

from core.circuit_geometry import route_nets
from core.circuits import Circuit, Component

from .codec import NativeCodec
from .native_probes import add_voltage_probes

MM = 25.4 / 90
ID_FIELDS = {
    "ID",
    "CiID",
    "Circuit",
    "Component",
    "PortID",
    "CiComponent",
    "SymCompID",
    "Connect1",
    "Connect2",
    "Node",
    "NodeText",
    "CiProbeExtComp",
}


def text(value: str) -> str:
    if not value.isascii():
        raise ValueError(
            "This native writer currently requires ASCII references, net names, and titles."
        )
    return "&ASC" + value


def plain(value: str | None) -> str:
    if value is None or not value.startswith("&ASC"):
        raise ValueError("Unsupported native text encoding in an editable field.")
    return value[4:]


def main_diagram(tree: etree._ElementTree):
    candidates = [
        node
        for node in tree.iter("CIITDiagram")
        if node.find("./Elements/Item/CiCircuit") is not None
    ]
    if len(candidates) != 1:
        raise ValueError("Only single-sheet native circuits are supported for authoring.")
    diagram = candidates[0]
    elements = diagram.find("Elements")
    composite = diagram.find("./Components/CODComposite")
    circuit_item = next(item for item in elements if item.find("CiCircuit") is not None)
    return diagram, elements, composite, circuit_item


def transform(element, point: tuple[float, float]) -> tuple[float, float]:
    x, y = point
    return (
        x * float(element.get("Transformer-M00", 1))
        + y * float(element.get("Transformer-M10", 0))
        + float(element.get("Transformer-M20", 0)),
        x * float(element.get("Transformer-M01", 0))
        + y * float(element.get("Transformer-M11", 1))
        + float(element.get("Transformer-M21", 0)),
    )


def pin_info(
    symbol, include_root: bool = True, port_names: dict[str, str] | None = None
) -> dict[str, dict[str, Any]]:
    result = {}
    for pin in symbol.iter("CIITPinSymbolComp"):
        connector = next(pin.iter("CIITPinConnectorComp"), None)
        if connector is None:
            continue
        point = float(connector.get("ptCenterX")), float(connector.get("ptCenterY"))
        element = connector
        while element is not None:
            if element is symbol and not include_root:
                break
            point = transform(element, point)
            if element is symbol:
                break
            element = element.getparent()
        number = (port_names or {}).get(pin.get("PortID"))
        if number is None:
            if port_names is not None:
                continue
            number = plain(pin.get("PinNumber"))
        result[number] = {
            "point": tuple(round(v, 6) for v in point),
            "connector": connector,
            "connector_id": connector.getparent().get("ID"),
            "port_id": pin.get("PortID"),
        }
    return result


def kind_of(component) -> str:
    expression = component.find(".//CiaSpiceTmpltExprt")
    source = plain(expression.get("String")).lower() if expression is not None else ""
    if plain(component.get("LocalName")) == "0":
        return "GND"
    for kind in "rcl":
        if source.startswith(f"{kind}%p %t1 %t2 #1"):
            return kind.upper()
    if source.startswith("v%p %t1 %t2 dc #1") and "sin(" not in source:
        return "VDC"
    raise ValueError(
        f"Unsupported native component {component.get('LocalName')}; no content was discarded."
    )


def set_value(component, symbol, kind: str, value: float, reference: str) -> None:
    parameters = component.find(".//CiaParamList")
    parameters.findall("./doubles/Item")[1].set("Value", format(value, ".17e"))
    parameters.findall("./parameters/Item")[1].set("Value", text(format(value, ".15g")))
    slots = component.findall("./Attributes/Item")
    unit = {"R": "ohm", "C": "F", "L": "H", "VDC": "V"}[kind]
    display = f"&UNI{value:g}_uc103a9" if kind == "R" else text(f"{value:g}{unit}")
    if kind in {"R", "C", "L"}:
        for index in (41, 42):
            if index < len(slots) and slots[index].find("CiaCString") is not None:
                slots[index].find("CiaCString").set(
                    "String", text(f"{value:g}") if index == 41 else display
                )
    component.set("LocalName", text(reference))
    symbol.set("InstanceRefDes", text(reference))
    for label in symbol.iter("CIITSymTextCompName"):
        label.set("Output", text(reference))
    for label in symbol.iter("CIITSymTextCompValue"):
        label.set("Output", display)


class MultisimSchematicEditor:
    suffix = ".ms14"

    def __init__(self, adapter, home: Path | None = None) -> None:
        self.adapter = adapter
        self.codec = NativeCodec(home)
        self.pack = self.codec.home / "components"
        if not (self.pack / "blank.xml").is_file():
            raise ValueError("Native component pack is missing; run authoring setup.")

    def catalog(self) -> list[dict[str, Any]]:
        return [
            {
                "kind": kind,
                "library_id": kind,
                "pins": ["1", "2"],
                "value_unit": {"R": "ohm", "C": "F", "L": "H", "VDC": "V"}[kind],
            }
            for kind in ("R", "C", "L", "VDC")
        ]

    def _template(self, name: str):
        return etree.parse(
            str(self.pack / f"{name}.xml"), etree.XMLParser(resolve_entities=False, no_network=True)
        ).getroot()

    def _basis(self, kind: str) -> tuple[float, tuple[float, float]]:
        bundle = self._template(kind)
        symbol = bundle.find("./Item/CIITSymbolComp")
        names = {
            item.get("CiID"): plain(item.find("CiPort").get("LocalName"))
            for item in bundle.findall("./Ports/Item")
        }
        pins = pin_info(symbol, False, names)
        p1 = pins["1"]["point"]
        if kind == "GND":
            return 0.0, p1
        p2 = pins["2"]["point"]
        angle = math.pi / 2 - math.atan2(p2[1] - p1[1], p2[0] - p1[0])
        return angle, ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)

    def normalize(self, circuit: Circuit) -> Circuit:
        data = circuit.model_dump()
        text(circuit.title)
        for item in data["components"]:
            angle, center = self._basis(item["kind"])
            angle -= math.radians(item["rotation"])
            cx = center[0] * math.cos(angle) - center[1] * math.sin(angle)
            cy = center[0] * math.sin(angle) + center[1] * math.cos(angle)
            item["x_mm"] = round((round(item["x_mm"] / MM - cx) + cx) * MM, 6)
            item["y_mm"] = round((round(item["y_mm"] / MM - cy) + cy) * MM, 6)
        return Circuit.model_validate(data)

    def load(self, path: Path) -> tuple[Circuit, Any]:
        tree = self.codec.decode(path)
        return self._model(tree, path.stem), tree

    def _model(self, tree, title="Bifrost Circuit") -> Circuit:
        _, elements, composite, _ = main_diagram(tree)
        ports = {
            item.get("CiID"): item.find("CiPort")
            for item in elements
            if item.find("CiPort") is not None
        }
        nodes = {
            item.get("CiID"): plain(item.find("CiNode").get("LocalName"))
            for item in elements
            if item.find("CiNode") is not None
        }
        symbols = {node.get("CiComponent"): node for node in composite.iter("CIITSymbolComp")}
        components = []
        for item in elements:
            component = item.find("CiComponent")
            if component is None:
                continue
            kind = kind_of(component)
            if kind == "GND":
                continue
            symbol = symbols[item.get("CiID")]
            pins = pin_info(
                symbol,
                port_names={key: plain(port.get("LocalName")) for key, port in ports.items()},
            )
            if set(pins) != {"1", "2"}:
                raise ValueError("Unsupported native pin layout.")
            net_map = {}
            for number, pin in pins.items():
                connections = ports[pin["port_id"]].findall("./Nodes/Item")
                if len(connections) > 1:
                    raise ValueError("Ambiguous native port-to-net mapping.")
                net_map[number] = nodes[connections[0].get("CiID")] if connections else None
            first, second = pins["1"]["point"], pins["2"]["point"]
            axis = math.atan2(second[1] - first[1], second[0] - first[0])
            rotation = round(math.degrees(math.pi / 2 - axis) / 90) * 90 % 360
            value = float(component.find(".//CiaParamList/doubles/Item[2]").get("Value"))
            components.append(
                Component(
                    reference=plain(component.get("LocalName")),
                    kind=kind,
                    value=value,
                    x_mm=round((first[0] + second[0]) / 2 * MM, 6),
                    y_mm=round((first[1] + second[1]) / 2 * MM, 6),
                    rotation=rotation,
                    pins=net_map,
                )
            )
        return Circuit(title=title, components=components)

    @staticmethod
    def _topology(circuit: Circuit):
        return {c.reference: c.model_dump(exclude={"value"}) for c in circuit.components}

    def preflight(self, circuit, original, previous):
        if original is None or previous is None:
            return
        if self._topology(circuit) == self._topology(previous):
            return
        _, elements, _, circuit_item = main_diagram(original)
        if circuit_item.find("CiCircuit").get("BifrostAuthoring") != "1":
            raise ValueError(
                "Imported Multisim designs support value edits only; topology editing currently "
                "requires a Bifrost-authored design. No content was discarded."
            )
        allowed = {"CiComponent", "CiPort", "CiNode", "CiProbeExtComp", "CiCircuit"}
        if any(child.tag not in allowed for item in elements for child in item):
            raise ValueError("Unsupported native circuit elements; no content was discarded.")
        probes = {p.get("FileDataPackageID") for p in original.iter("CIITProbeExtComponent")}
        if any(
            n.get("CompLongName") not in probes for n in original.iter("CSourceSymbolCollectNode")
        ):
            raise ValueError("Topology edits cannot preserve these instruments yet.")

    def render(self, circuit: Circuit, original: Any | None, path: Path) -> None:
        tree = (
            copy.deepcopy(original)
            if original is not None
            else etree.ElementTree(self._template("blank"))
        )
        diagram, elements, composite, circuit_item = main_diagram(tree)
        native_circuit = circuit_item.find("CiCircuit")
        circuit_id = circuit_item.get("CiID")
        existing = {
            plain(item.find("CiComponent").get("LocalName")): item
            for item in elements
            if item.find("CiComponent") is not None
        }
        existing_symbols = {
            node.get("CiComponent"): node.getparent() for node in composite.iter("CIITSymbolComp")
        }
        existing_ports = defaultdict(list)
        for item in elements:
            port = item.find("CiPort")
            if port is not None:
                existing_ports[port.get("Component")].append(item)
        if original is not None:
            # Values can be edited without touching probe, wire, or instrument state.
            old = self._model(tree)
            self.preflight(circuit, tree, old)
            changed = [
                c
                for c in circuit.components
                if next((p for p in old.components if p.reference == c.reference), None) != c
            ]
            topology_changed = len(circuit.components) != len(old.components) or any(
                not any(
                    p.reference == c.reference
                    and p.kind == c.kind
                    and p.pins == c.pins
                    and abs(p.x_mm - c.x_mm) < 1e-4
                    and abs(p.y_mm - c.y_mm) < 1e-4
                    and p.rotation == c.rotation
                    for p in old.components
                )
                for c in changed
            )
            if not topology_changed:
                for c in changed:
                    item = existing[c.reference]
                    set_value(
                        item.find("CiComponent"),
                        existing_symbols[item.get("CiID")].find("CIITSymbolComp"),
                        c.kind,
                        c.value,
                        c.reference,
                    )
                self.codec.encode(tree, path)
                return
        native_circuit.set("BifrostAuthoring", "1")
        used = {node.get(key) for node in tree.iter() for key in ("ID", "CiID") if node.get(key)}
        sequence = 900000000

        def next_id() -> str:
            nonlocal sequence
            while str(sequence) in used:
                sequence += 1
            value = str(sequence)
            used.add(value)
            return value

        def clone(item):
            result = copy.deepcopy(item)
            mapping = {}
            for node in result.iter():
                for key in ("ID", "CiID"):
                    if node.get(key):
                        mapping.setdefault(node.get(key), next_id())
            for node in result.iter():
                for key, value in list(node.attrib.items()):
                    if key in ID_FIELDS and value in mapping:
                        node.set(key, mapping[value])
                    if key in {"Guid", "InstanceID"} and value:
                        node.set(key, "{" + str(uuid4()).upper() + "}")
            return result

        objects = composite.find("Objects")
        references = composite.find("ReferencedComponents")
        for item in list(objects):
            if item.get("Class") in {
                "CIITSymbolComp",
                "CIITLinkComp",
                "CODNodeTextComp",
                "CIITProbeExtComponent",
            }:
                objects.remove(item)
        references.clear()
        for item in objects:
            references.append(etree.Element("Item", ID=item.get("ID"), Class=item.get("Class")))
        for item in list(elements):
            if item is not circuit_item:
                elements.remove(item)
        elements.remove(circuit_item)
        for tag in ("Nodes", "Components", "ProbeExts"):
            container = native_circuit.find(tag)
            if container is not None:
                container.clear()
        for tag in ("InstrumentsData", "CIRToInfoMap", "TriggerSet", "RefDesPrefixUsageMap"):
            for container in tree.iter(tag):
                container.clear()

        def add_object(item):
            objects.append(item)
            references.append(etree.Element("Item", ID=item.get("ID"), Class=item.get("Class")))

        nodes = {}
        terminals = defaultdict(list)
        connections = defaultdict(list)
        rectangles = []
        component_items = []
        port_items = []
        specs = [c.model_dump() for c in circuit.components]
        if any("0" in c.pins.values() for c in circuit.components):
            specs.append(
                {
                    "reference": "0",
                    "kind": "GND",
                    "value": 0,
                    "rotation": 0,
                    "x_mm": min(c.x_mm for c in circuit.components),
                    "y_mm": max(c.y_mm for c in circuit.components) + 25.4,
                    "pins": {"1": "0"},
                }
            )
        for spec in specs:
            previous_item = existing.get(spec["reference"])
            if (
                previous_item is not None
                and kind_of(previous_item.find("CiComponent")) == spec["kind"]
            ):
                bundle = etree.Element("ComponentTemplate", kind=spec["kind"])
                bundle.append(copy.deepcopy(previous_item))
                bundle.append(copy.deepcopy(existing_symbols[previous_item.get("CiID")]))
                ports = etree.SubElement(bundle, "Ports")
                ports.extend(copy.deepcopy(existing_ports[previous_item.get("CiID")]))
            else:
                bundle = clone(self._template(spec["kind"]))
            item = next(i for i in bundle.findall("Item") if i.find("CiComponent") is not None)
            symbol_item = next(
                i for i in bundle.findall("Item") if i.find("CIITSymbolComp") is not None
            )
            component, symbol = item.find("CiComponent"), symbol_item.find("CIITSymbolComp")
            component.set("Circuit", circuit_id)
            component.set("LocalName", text(spec["reference"]))
            component.set("SymCompID", symbol_item.get("ID"))
            symbol.set("CiComponent", item.get("CiID"))
            if spec["kind"] != "GND":
                set_value(component, symbol, spec["kind"], spec["value"], spec["reference"])
            angle, center = self._basis(spec["kind"])
            angle -= math.radians(spec["rotation"])
            cosine, sine = round(math.cos(angle)), round(math.sin(angle))
            cx, cy = center[0] * cosine - center[1] * sine, center[0] * sine + center[1] * cosine
            for key, value in {
                "M00": cosine,
                "M01": sine,
                "M10": -sine,
                "M11": cosine,
                "M20": round(spec["x_mm"] / MM - cx),
                "M21": round(spec["y_mm"] / MM - cy),
            }.items():
                symbol.set("Transformer-" + key, str(value))
            symbol.set("OrientationFlip", "0")
            symbol.set("UserDefinedLabelPos", "1")
            if spec["kind"] != "GND":
                for index, tag in enumerate(("CIITSymTextCompName", "CIITSymTextCompValue")):
                    for label in symbol.iter(tag):
                        desired = (spec["x_mm"] / MM + 15, spec["y_mm"] / MM - 9 + 15 * index)
                        dx = desired[0] - float(symbol.get("Transformer-M20"))
                        dy = desired[1] - float(symbol.get("Transformer-M21"))
                        for key, value in {
                            "M00": cosine,
                            "M01": -sine,
                            "M10": sine,
                            "M11": cosine,
                            "M20": dx * cosine + dy * sine,
                            "M21": -dx * sine + dy * cosine,
                        }.items():
                            label.set("Transformer-" + key, format(value, ".12g"))
                        label.set("Font-Escapement", "0")
                        label.set("Font-Orientation", "0")
                        label.set("HorizontalAlign", "0")
            pins = pin_info(
                symbol,
                port_names={
                    item.get("CiID"): plain(item.find("CiPort").get("LocalName"))
                    for item in bundle.findall("./Ports/Item")
                },
            )
            for p in pins.values():
                p["point"] = tuple(round(v) for v in p["point"])
            xs, ys = zip(*(p["point"] for p in pins.values()), strict=False)
            center_x, center_y = sum(xs) / len(xs), sum(ys) / len(ys)
            if spec["kind"] == "GND":
                rectangles.append((center_x - 12, center_y, center_x + 12, center_y + 27))
            else:
                rectangles.append(
                    (
                        math.floor(min(min(xs), center_x - 12)),
                        math.floor(min(min(ys), center_y - 12)),
                        math.ceil(max(max(xs), center_x + 12)),
                        math.ceil(max(max(ys), center_y + 12)),
                    )
                )
            component.find("Ports").clear()
            for port_item in bundle.findall("./Ports/Item"):
                port = port_item.find("CiPort")
                number = plain(port.get("LocalName"))
                port.set("Component", item.get("CiID"))
                component.find("Ports").append(etree.Element("Item", CiID=port_item.get("CiID")))
                port.find("Nodes").clear()
                net = spec["pins"].get(number)
                pin = pins[number]
                pin["connector"].find("ConnectList").clear()
                point = pin["point"]
                terminals[net or f"__floating_{spec['reference']}_{number}"].append(point)
                if net is not None:
                    if net not in nodes:
                        node_item = clone(self._template("ground_node" if net == "0" else "node"))
                        node = node_item.find("CiNode")
                        node.set("LocalName", text(net))
                        node.set("Circuit", circuit_id)
                        node.find("Ports").clear()
                        nodes[net] = node_item
                    node_item = nodes[net]
                    port.find("Nodes").append(etree.Element("Item", CiID=node_item.get("CiID")))
                    node_item.find("./CiNode/Ports").append(
                        etree.Element("Item", CiID=port_item.get("CiID"))
                    )
                    external = clone(self._template("external_pin"))
                    external.find("CODPinComp").set("CenterX", str(point[0]))
                    external.find("CODPinComp").set("CenterY", str(point[1]))
                    external.find("./CODPinComp/ConnectList/Item").set("ID", pin["connector_id"])
                    references.append(external)
                    pin["connector"].find("ConnectList").append(
                        etree.Element("Item", ID=external.get("ID"), Class="CODPinComp")
                    )
                    connections[net].append((point, external.get("ID")))
                port_items.append(port_item)
            component_items.append(item)
            native_circuit.find("Components").append(etree.Element("Item", CiID=item.get("CiID")))
            add_object(symbol_item)
        for item in nodes.values():
            native_circuit.find("Nodes").append(etree.Element("Item", CiID=item.get("CiID")))
        elements.extend(component_items)
        elements.extend(port_items)
        elements.extend(nodes.values())
        elements.append(circuit_item)
        routed, _ = route_nets(terminals, rectangles, clearance=9)
        for net, attached in connections.items():
            if len(attached) < 2:
                continue
            graph = nx.Graph()
            for wire in routed:
                if wire.net == net:
                    graph.add_edge(wire.start, wire.end)
            label = clone(self._template("node_text"))
            label.find("CODNodeTextComp").set("Output", text(net))
            label.find("CODNodeTextComp").set("Transformer-M20", str(attached[0][0][0] + 3))
            label.find("CODNodeTextComp").set("Transformer-M21", str(attached[0][0][1] - 6))
            label.find("./CODNodeTextComp/Links").clear()
            for endpoint, endpoint_id in attached[1:]:
                # Reintroduce collinear terminal points removed by route simplification.
                for point in (attached[0][0], endpoint):
                    if point not in graph:
                        for a, b in list(graph.edges):
                            if (
                                a[0] == b[0] == point[0]
                                and min(a[1], b[1]) < point[1] < max(a[1], b[1])
                            ) or (
                                a[1] == b[1] == point[1]
                                and min(a[0], b[0]) < point[0] < max(a[0], b[0])
                            ):
                                graph.remove_edge(a, b)
                                graph.add_edges_from([(a, point), (point, b)])
                points = nx.shortest_path(graph, attached[0][0], endpoint)
                wire_item = clone(self._template("wire"))
                wire = wire_item.find("CIITLinkComp")
                for key, value in {
                    "Connect1": attached[0][1],
                    "Connect2": endpoint_id,
                    "Node": nodes[net].get("CiID"),
                    "NodeText": label.get("ID"),
                }.items():
                    wire.set(key, value)
                wire.find("Points").clear()
                for x, y in points:
                    wire.find("Points").append(
                        etree.Element("Item", X=str(round(x)), Y=str(round(y)))
                    )
                wire.find("./ElectricalObject/ModifierInfo/Element/Item").set("Value", text(net))
                label.find("./CODNodeTextComp/Links").append(
                    etree.Element("Item", ID=wire_item.get("ID"), Class="CIITLinkComp")
                )
                add_object(wire_item)
            add_object(label)
        diagram.set(
            "PageWidth",
            str(max(10, max((p[0] for ps in terminals.values() for p in ps), default=0) / 90 + 1)),
        )
        diagram.set(
            "PageHeight",
            str(max(8, max((p[1] for ps in terminals.values() for p in ps), default=0) / 90 + 1)),
        )
        add_voltage_probes(
            tree,
            objects,
            elements,
            circuit_item,
            routed,
            self._template,
            clone,
            str(path.resolve()),
        )
        elements.remove(circuit_item)
        elements.append(circuit_item)
        self.codec.encode(tree, path)

    def verify(self, path: Path, circuit: Circuit) -> dict[str, Any]:
        loaded, native = self.load(path)
        expected = {c.reference: c for c in circuit.components}
        actual = {c.reference: c for c in loaded.components}
        if set(actual) != set(expected):
            raise ValueError("Native component identity verification failed.")
        for reference, component in expected.items():
            candidate = actual[reference]
            if (
                candidate.kind != component.kind
                or candidate.pins != component.pins
                or candidate.rotation != component.rotation
            ):
                raise ValueError(f"Native properties or connectivity mismatch: {reference}")
            if not all(
                math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-4)
                for a, b in (
                    (candidate.value, component.value),
                    (candidate.x_mm, component.x_mm),
                    (candidate.y_mm, component.y_mm),
                )
            ):
                raise ValueError(f"Native value or placement mismatch: {reference}")
        result = self.adapter._run_worker(
            "verify_schematic",
            {
                "file_path": str(path.resolve()),
                "value_references": [c.reference for c in circuit.components if c.kind != "VDC"],
            },
            60,
        )
        if not result.get("success"):
            raise ValueError(
                f"Multisim could not reopen the native revision: {result.get('error')}"
            )
        data = result["data"]
        if set(data["components"]) != set(expected):
            raise ValueError("Multisim omitted or changed native components.")
        observed = {}
        for row in csv.reader(io.StringIO(data["report"])):
            if len(row) == 4 and row[2] in expected:
                observed[row[2], row[3]] = row[0]
        for component in circuit.components:
            for pin, net in component.pins.items():
                if net is not None and observed.get((component.reference, pin)) != net:
                    raise ValueError(
                        f"Multisim connectivity mismatch at {component.reference}.{pin}"
                    )
            if component.kind != "VDC" and not math.isclose(
                data["values"][component.reference], component.value, rel_tol=1e-8, abs_tol=1e-12
            ):
                raise ValueError(f"Multisim did not preserve the value of {component.reference}")
        return {
            "native_reopen": True,
            "native_connections_verified": True,
            "software_version": data["software_version"],
            "components": len(expected),
            "probe_outputs": {
                plain(probe.get("BifrostNet")): plain(probe.get("BifrostOutput"))
                for probe in native.iter("CiProbeExtComp")
                if probe.get("BifrostNet")
            },
        }
