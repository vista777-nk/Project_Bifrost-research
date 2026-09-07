"""Supervised non-GUI generation proof using an external, reviewed MIT builder.

The upstream code is not vendored. All extracted NI objects and generated
designs stay in the explicitly selected, local-only output directory.
"""

import argparse
import json
import os
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    pack = args.output / "component-pack"
    sys.path.insert(0, str(args.upstream.resolve() / "tools"))
    sys.path.insert(0, str(args.upstream.resolve() / "mcp_server"))
    from extract_native_component_templates import extract_structural_templates, extract_templates
    from multisim_mcp.schematic_builder import build_schematic

    rlc = args.data / "rlc-roundtrip.ms14.xml"
    lowpass = args.data / "filter-roundtrip.ms14.xml"
    extract_templates(rlc, "R1", "R", pack)
    extract_templates(lowpass, "C9", "C", pack)
    extract_templates(lowpass, "V1", "V", pack)
    extract_templates(lowpass, "0", "GND", pack)
    extract_structural_templates(rlc, pack, minimal_source=args.data / "blank-roundtrip.ms14.xml")
    os.environ["MULTISIM_MCP_TEMPLATE_DIR"] = str(pack.resolve())
    os.environ["MULTISIM_MCP_TEMPLATE_ONLY"] = "1"
    base = "* Bifrost no-GUI native creation proof\nV1 1 0 DC 5\nR1 1 2 10000\nR2 2 0 10000\n"
    cases = {
        "divider": base + ".END\n",
        "divider-with-capacitor": base + "C1 2 0 1u\n.END\n",
    }
    results = []
    for name, netlist in cases.items():
        result = build_schematic(netlist, args.output / f"{name}.xml", probe_nets=[])
        assert not result.get("unsupported"), result
        assert not result.get("model_warnings"), result
        results.append(result)
    (args.output / "evidence.json").write_text(
        json.dumps({"local_only": True, "upstream_license": "MIT", "results": results}, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
