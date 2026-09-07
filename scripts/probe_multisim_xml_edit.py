"""A narrowly scoped XML edit probe for the local Using Analyses sample."""

import argparse
import json
from pathlib import Path

from lxml import etree


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    tree = etree.parse(str(args.input), etree.XMLParser(resolve_entities=False, no_network=True))
    assert tree.getroot().get("Schema") == "67", "This probe is restricted to the inspected schema."
    components = tree.xpath("//CiComponent[@LocalName='&ASCR2']")
    assert len(components) == 1
    component = components[0]
    parameters = component.find("./Attributes/Item/CiaParamList")
    numbers = parameters.findall("./doubles/Item")
    strings = parameters.findall("./parameters/Item")
    assert float(numbers[1].get("Value")) == 3980, "Unexpected sample resistor value."
    before_count = sum(1 for _ in tree.iter())
    numbers[1].set("Value", "20000.")
    strings[1].set("Value", "&ASC20000")
    for cached in component.iter("CiaCString"):
        if cached.get("String") == "&ASC3.98k":
            cached.set("String", "&ASC20k")
        elif cached.get("String") == "&UNI3.98k_uc103a9":
            cached.set("String", "&UNI20k_uc103a9")
    symbols = tree.xpath("//CIITSymbolComp[@InstanceRefDes='&ASCR2']")
    assert len(symbols) == 1
    for label in symbols[0].iter("CIITSymTextCompValue"):
        label.set("Output", "&UNI20k_uc103a9")
    assert sum(1 for _ in tree.iter()) == before_count
    with args.output.open("xb") as handle:
        tree.write(handle, encoding="ASCII", xml_declaration=True)
    print(
        json.dumps(
            {
                "reference": "R2",
                "before_ohms": 3980,
                "after_ohms": 20000,
                "output": str(args.output),
                "object_count_preserved": before_count,
            }
        )
    )


if __name__ == "__main__":
    main()
