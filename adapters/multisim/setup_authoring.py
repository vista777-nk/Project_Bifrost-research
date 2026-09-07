"""Derive a local-only native component pack from the licensed installation."""

from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from lxml import etree

from .adapter import MultisimAdapter
from .codec import NativeCodec


def component_template(document, reference: str, kind: str):
    component = next(
        node for node in document.iter("CiComponent") if node.get("LocalName") == "&ASC" + reference
    )
    item = component.getparent()
    symbol = next(
        node
        for node in document.iter("CIITSymbolComp")
        if node.get("CiComponent") == item.get("CiID")
    )
    bundle = etree.Element("ComponentTemplate", kind=kind)
    bundle.append(copy.deepcopy(item))
    bundle.append(copy.deepcopy(symbol.getparent()))
    ports = etree.SubElement(bundle, "Ports")
    for port in document.iter("CiPort"):
        if port.get("Component") == item.get("CiID"):
            ports.append(copy.deepcopy(port.getparent()))
    return bundle


def create_pack(home: Path, samples: Path) -> None:
    codec = NativeCodec(home)
    pack = home / "components"
    if pack.exists():
        raise FileExistsError(
            "Choose a new authoring directory; existing component packs are preserved."
        )
    source = samples / "LabVIEW Multisim API Toolkit" / "Using Analyses" / "Using Analyses.ms14"
    tree = codec.decode(source)
    pack.mkdir(parents=True)
    l_tree = codec.decode(samples / "Analyses" / "Monte Carlo - RLC Circuit.ms14")
    r_tree = codec.decode(samples / "LabVIEW Multisim API Toolkit/RLC Values/RLC Values.ms14")
    for kind, reference, document in [
        ("R", "R1", r_tree),
        ("C", "C1", tree),
        ("VDC", "V2", tree),
        ("GND", "0", tree),
        ("L", "L1", l_tree),
    ]:
        bundle = component_template(document, reference, kind)
        etree.ElementTree(bundle).write(
            str(pack / f"{kind}.xml"), encoding="ASCII", xml_declaration=True
        )
    structures = {
        "node": next(
            node for node in tree.iter("CiNode") if node.get("LocalName") != "&ASC0"
        ).getparent(),
        "ground_node": next(
            node for node in tree.iter("CiNode") if node.get("LocalName") == "&ASC0"
        ).getparent(),
        "wire": next(
            node
            for node in tree.iter("CIITLinkComp")
            if node.find("./ElectricalObject/ModifierInfo/Element") is not None
            and node.find("./ElectricalObject/ModifierInfo/Element").get("NetModifier")
            == "&ASCNI_EWB_NET_NAME"
        ).getparent(),
        "node_text": next(tree.iter("CODNodeTextComp")).getparent(),
        "external_pin": next(
            node
            for node in tree.iter("CODPinComp")
            if node.get("Mobility") == "1"
            and node.find("./ConnectList/Item") is not None
            and node.find("./ConnectList/Item").get("Class") == "CIITPinConnectorComp"
        ).getparent(),
    }
    for name, item in structures.items():
        etree.ElementTree(copy.deepcopy(item)).write(
            str(pack / f"{name}.xml"), encoding="ASCII", xml_declaration=True
        )
    adapter = MultisimAdapter()
    with TemporaryDirectory(prefix="bifrost-empty-native-") as directory:
        native = Path(directory) / "blank.ms14"
        result = adapter._run_worker("new_blank", {"output_file": str(native)}, 60)
        if not result.get("success") or not native.is_file():
            raise ValueError(f"Multisim could not create a version-matched blank design: {result}")
        codec.decode(native).write(str(pack / "blank.xml"), encoding="ASCII", xml_declaration=True)
    (home / "manifest.json").write_text(
        json.dumps(
            {
                "schema": 67,
                "local_only": True,
                "source": str(source),
                "catalog": ["R", "C", "L", "VDC"],
                "notice": (
                    "Derived from the local licensed installation; not redistributed with Bifrost."
                ),
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def add_probes(home: Path, samples: Path) -> None:
    codec = NativeCodec(home)
    tree = codec.decode(samples / "LabVIEW Multisim API Toolkit/Using Analyses/Using Analyses.ms14")
    element = next(tree.iter("CiProbeExtComp"))
    symbol = next(
        node
        for node in tree.iter("CIITProbeExtComponent")
        if node.get("CiProbeExtComp") == element.getparent().get("CiID")
    )
    instrument = next(
        node
        for node in tree.iter("CSourceSymbolCollectNode")
        if node.get("CompLongName") == symbol.get("FileDataPackageID")
    )
    for name, item in (
        ("probe_element", element.getparent()),
        ("probe_symbol", symbol.getparent()),
        ("probe_instrument", instrument),
    ):
        target = home / "components" / f"{name}.xml"
        with target.open("xb") as handle:
            etree.ElementTree(copy.deepcopy(item)).write(
                handle, encoding="ASCII", xml_declaration=True
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, required=True)
    parser.add_argument("--probes-only", action="store_true")
    parser.add_argument("--refresh-resistor", action="store_true")
    parser.add_argument(
        "--samples",
        type=Path,
        default=Path(os.environ.get("PUBLIC", r"C:\Users\Public"))
        / "Documents/National Instruments/Circuit Design Suite 14.3/samples",
    )
    args = parser.parse_args()
    if args.refresh_resistor:
        from core.circuits import publish_revision

        codec = NativeCodec(args.home.resolve())
        source = args.samples / "LabVIEW Multisim API Toolkit/RLC Values/RLC Values.ms14"
        bundle = component_template(codec.decode(source), "R1", "R")
        publish_revision(
            args.home / "components/R.xml",
            etree.tostring(bundle, encoding="ASCII", xml_declaration=True),
            overwrite=True,
        )
        print("Refreshed the generated resistor profile from the licensed automation sample.")
        return
    if not args.probes_only:
        create_pack(args.home.resolve(), args.samples.resolve())
    add_probes(args.home.resolve(), args.samples.resolve())
    print(args.home.resolve())


if __name__ == "__main__":
    main()
