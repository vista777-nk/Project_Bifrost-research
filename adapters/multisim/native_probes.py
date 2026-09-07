"""Native voltage-probe registration using local-only library definitions.

Reference-map structure adapted from Multisim MCP (MIT). See THIRD_PARTY_NOTICES.md.
"""

from __future__ import annotations

from lxml import etree


def add_voltage_probes(tree, objects, elements, circuit_item, routed, template, clone, output):
    circuit = circuit_item.find("CiCircuit")
    instruments = next(tree.iter("InstrumentsData"))
    container = next(tree.iter("RefDesInfoContainer"))
    names = container.find("CIRToInfoMap")
    prefixes = next(tree.iter("RefDesPrefixUsageMap"))
    total = next(tree.iter("TotalProbeTriggers"))
    triggers = total.find("TriggerSet")
    if triggers is None:
        triggers = etree.SubElement(total, "TriggerSet")
    circuit_name = circuit_item.get("LocalName", "&ASCnative").removeprefix("&ASC")
    nets = sorted({wire.net for wire in routed if wire.net != "0"})
    if len(nets) > 16:
        raise ValueError("The initial native authoring release supports at most 16 probed nets.")
    result = {}
    for index, net in enumerate(nets, 1):
        own = [wire for wire in routed if wire.net == net]
        point = None
        for wire in sorted(
            own, key=lambda w: -(abs(w.start[0] - w.end[0]) + abs(w.start[1] - w.end[1]))
        ):
            for fraction in (0.5, 0.25, 0.75):
                candidate = tuple(
                    round(a + fraction * (b - a)) for a, b in zip(wire.start, wire.end, strict=True)
                )
                if candidate in {wire.start, wire.end}:
                    continue
                crossing = any(
                    other.net != net
                    and (
                        (
                            other.start[0] == other.end[0] == candidate[0]
                            and min(other.start[1], other.end[1])
                            <= candidate[1]
                            <= max(other.start[1], other.end[1])
                        )
                        or (
                            other.start[1] == other.end[1] == candidate[1]
                            and min(other.start[0], other.end[0])
                            <= candidate[0]
                            <= max(other.start[0], other.end[0])
                        )
                    )
                    for other in routed
                )
                if not crossing:
                    point = candidate
                    break
            if point is not None:
                break
        if point is None:
            raise ValueError(f"No safe native probe position on net {net}.")
        ref = f"PR{index}"
        element_item = clone(template("probe_element"))
        symbol_item = clone(template("probe_symbol"))
        instrument = clone(template("probe_instrument"))
        element, symbol = (
            element_item.find("CiProbeExtComp"),
            symbol_item.find("CIITProbeExtComponent"),
        )
        element.set("LocalName", "&ASC" + ref)
        element.set("BifrostNet", "&ASC" + net)
        element.set("BifrostOutput", "&ASCV(" + net + ")")
        element.set("SymCompID", symbol_item.get("ID"))
        element.set("Circuit", circuit_item.get("CiID"))
        symbol.set("CiProbeExtComp", element_item.get("CiID"))
        symbol.set("Transformer-M20", str(point[0]))
        symbol.set("Transformer-M21", str(point[1]))
        symbol.set("UniqueID", str(index))
        symbol.set("ShowInfo", "0")
        package = "&ASCX_" + format(int(symbol_item.get("ID")), "x")
        symbol.set("FileDataPackageID", package)
        instrument.set("CompLongName", package)
        for root in (symbol, instrument):
            for mapping in root.iter("Element"):
                if mapping.get("Key") == "&ASCNI_EWB_COMPHANDLE_EXT":
                    mapping.find("CDataElement").set("Data", symbol_item.get("ID"))
        objects.append(symbol_item)
        elements.append(element_item)
        circuit.find("ProbeExts").append(etree.Element("Item", CiID=element_item.get("CiID")))
        instruments.append(instrument)
        entry = etree.SubElement(names, "CIRToInfoMapItem", CIRKey="&ASC" + ref)
        info = etree.SubElement(
            entry,
            "RefDesInfo",
            Class="CIITHierRefDesInfo",
            IRPrefix="&ASC" + net,
            IRNumber="-1",
            Locked="0",
            IRSection="",
            IRSectionID="0",
            SpiceTemplate="",
        )
        encoded = f"&ASC!0!0!0{ref}!0{output}!01!0{circuit_name}!0"
        etree.SubElement(
            info,
            "RefDesInfoData",
            Class="CIITHierRefDes",
            RefDesBufSize=str(max(260, len(encoded) + 1)),
            RefDesStrSize=str(len(encoded)),
            RefDesCount="2",
            RefDes=encoded,
            SectionBufSize="0",
            SectionStrSize="0",
            Section="&ASC(null)",
            Prefix="&ASCPR",
            Number=str(index),
        )
        for tag in (
            "RefDesData",
            "PinOrderCIR",
            "PinOrderIR",
            "PinNumbersCIR",
            "PinNumbersIR",
            "SharedPins",
        ):
            etree.SubElement(info, tag)
        usage = etree.SubElement(
            prefixes,
            "RefDesPrefixUsage",
            RefDes="&ASC" + net.upper(),
            Class="CIITRefDesPrefixUsage",
            Prefix="&ASC" + net,
            NextNumber="1",
        )
        etree.SubElement(
            etree.SubElement(usage, "RefDesPrefixUsage"), "NumbersUsedVTwo", NumberUsed="0"
        )
        etree.SubElement(usage, "MultisectionUsage")
        trigger = etree.SubElement(
            triggers,
            "InstProbeTriggers",
            TreeInstance=container.get("CIR", f"&ASC#1/{circuit_name}:"),
            ProbeID=str(index),
        )
        details = etree.SubElement(
            etree.SubElement(trigger, "Triggers"),
            "ProbeTriggers",
            Class="&ASCCProbeTriggers",
            NumTriggers="0",
        )
        etree.SubElement(details, "Triggers")
        result[net] = f"V({net})"
    total.set("NextProbeID", str(len(nets) + 1))
    return result
