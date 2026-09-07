"""Verify native circuit authoring through the installed plugin's MCP config."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
from pathlib import Path

from mcp.client import Client
from mcp.client.stdio import StdioServerParameters


async def verify(config: Path, output: Path, example: Path) -> None:
    settings = json.loads(config.read_text(encoding="utf-8"))["mcpServers"]["bifrost-codex"]
    output.mkdir(parents=True, exist_ok=False)
    server = StdioServerParameters(
        command=settings["command"], args=settings["args"], env=settings.get("env"), cwd=output
    )
    circuit = json.loads(example.read_text(encoding="utf-8"))
    evidence = {"applications": {}, "source_hashes_preserved": False}

    async with Client(server, read_timeout_seconds=180) as client:

        async def call(tool, **arguments):
            response = await client.call_tool(tool, arguments)
            result = response.structured_content
            if not result or not result.get("success"):
                raise RuntimeError(json.dumps(result, ensure_ascii=True))
            if (
                tool == "run_action"
                and arguments.get("app") == "kicad"
                and arguments.get("action_name")
                in {
                    "create_schematic",
                    "edit_schematic",
                }
                and not result["metadata"]["verification"]["erc_passed"]
            ):
                raise RuntimeError("The divider revision did not pass native ERC.")
            return result

        for app, suffix in (("kicad", ".kicad_sch"), ("multisim", ".ms14")):
            records = []
            hashes = {}
            parameters = {"output_file": str(output / f"{app}-divider{suffix}"), "circuit": circuit}
            await call(
                "preview_action", app=app, action_name="create_schematic", parameters=parameters
            )
            result = await call(
                "run_action",
                app=app,
                action_name="create_schematic",
                parameters=parameters,
                retry_on_failure=False,
            )
            records.append(result)
            previous = Path(parameters["output_file"])
            hashes[previous] = result["metadata"]["output_sha256"]

            async def dc(path, expected, app=app, records=records):
                simulation = await call(
                    "run_action",
                    app=app,
                    action_name="run_simulation",
                    parameters={
                        "file_path": str(path),
                        "analysis_type": "dc",
                        "output_names": ["V(OUT)"],
                    },
                    retry_on_failure=False,
                )
                data = await call(
                    "run_action",
                    app=app,
                    action_name="get_output_data",
                    parameters={
                        "simulation_action_id": simulation["action_id"],
                        "output_name": "V(OUT)",
                    },
                )
                measured = data["metadata"]["data"][1][0]
                if not math.isclose(measured, expected, rel_tol=1e-6):
                    raise RuntimeError(f"DC mismatch: {measured} != {expected}")
                records.append({"file": str(path), "dc_out_volts": measured})

            if app == "multisim":
                await dc(previous, 2.5)
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
                [{"op": "remove", "reference": "C1"}],
            ]
            for index, changes in enumerate(batches, 1):
                inspected = await call(
                    "run_action",
                    app=app,
                    action_name="inspect_schematic",
                    parameters={"input_file": str(previous)},
                )
                parameters = {
                    "input_file": str(previous),
                    "output_file": str(output / f"{app}-revision-{index}{suffix}"),
                    "expected_input_sha256": inspected["metadata"]["input_sha256"],
                    "changes": changes,
                }
                preview = await call(
                    "preview_action", app=app, action_name="edit_schematic", parameters=parameters
                )
                if "native_changes" not in preview["preview"]:
                    raise RuntimeError("Native semantic preview was not returned.")
                result = await call(
                    "run_action",
                    app=app,
                    action_name="edit_schematic",
                    parameters=parameters,
                    retry_on_failure=False,
                )
                await call("validate_result", action_id=result["action_id"])
                records.append(result)
                previous = Path(parameters["output_file"])
                hashes[previous] = result["metadata"]["output_sha256"]
                if app == "multisim":
                    await dc(previous, 10 / 3)
            for path, checksum in hashes.items():
                if hashlib.sha256(path.read_bytes()).hexdigest() != checksum:
                    raise RuntimeError(f"A prior revision changed: {path}")
            evidence["applications"][app] = records
            print(
                f"{app}: create/edit/add/remove, native validation, and revision hashes passed.",
                flush=True,
            )
    evidence["source_hashes_preserved"] = True
    (output / "verification.json").write_text(
        json.dumps(evidence, indent=2) + "\n", encoding="utf-8"
    )
    print(output / "verification.json")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--example",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "examples/circuits/voltage-divider.json",
    )
    args = parser.parse_args()
    asyncio.run(verify(args.config.resolve(), args.output_dir.resolve(), args.example.resolve()))


if __name__ == "__main__":
    main()
