"""Opt-in live Multisim tests. The NI sample itself is never redistributed."""

import asyncio
import hashlib
import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("mcp")

from mcp.client import Client
from mcp.client.stdio import StdioServerParameters

pytestmark = pytest.mark.hardware


@pytest.fixture
def circuit():
    source = os.environ.get("BIFROST_MULTISIM_TEST_CIRCUIT")
    if not source:
        pytest.skip("Set BIFROST_MULTISIM_TEST_CIRCUIT to opt into live Multisim tests.")
    path = Path(source).resolve()
    assert path.is_file()
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    yield path
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def server(tmp_path):
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "codex_plugin.mcp.server"],
        cwd=tmp_path,
        env={"PYTHONUTF8": "1"},
    )


async def call(client, tool, arguments):
    response = await client.call_tool(tool, arguments)
    result = response.structured_content
    assert result and result.get("success"), (
        result.get("summary", "Missing result") if result else "Missing structured result"
    )
    return result


@pytest.mark.parametrize("format", ["text", "csv"])
def test_live_inspection_report_and_confirmation(circuit, tmp_path, format):
    async def workflow():
        async with Client(server(tmp_path), read_timeout_seconds=90) as client:
            probe = await call(client, "run_action", {"app": "multisim", "action_name": "probe"})
            assert probe["metadata"]["worker_bits"] == 32
            assert probe["metadata"]["connected"] is True
            info = await call(
                client,
                "run_action",
                {
                    "app": "multisim",
                    "action_name": "read_circuit",
                    "parameters": {"file_path": str(circuit)},
                },
            )
            assert info["metadata"]["components"]
            assert all(info["metadata"]["components"])
            output = tmp_path / ("connectivity.csv" if format == "csv" else "connectivity.txt")
            parameters = {"file_path": str(circuit), "output_file": str(output), "format": format}
            report = await call(
                client,
                "run_action",
                {"app": "multisim", "action_name": "export_netlist", "parameters": parameters},
            )
            assert output.stat().st_size > 0
            await call(client, "validate_result", {"action_id": report["action_id"]})
            pending = await client.call_tool(
                "run_action",
                {"app": "multisim", "action_name": "export_netlist", "parameters": parameters},
            )
            assert pending.structured_content["status"] == "confirmation_required"
            await call(
                client,
                "confirm_action",
                {"action_id": pending.structured_content["action_id"], "confirm": True},
            )

    asyncio.run(workflow())


@pytest.mark.parametrize(
    "analysis_type,sweep_type,output_names",
    [
        ("dc", "linear", []),
        ("dc", "linear", ["V(BPout)"]),
        ("ac", "linear", []),
        ("ac", "decade", []),
        ("ac", "octave", []),
        ("transient", "linear", []),
    ],
)
def test_live_simulation_outputs(circuit, tmp_path, analysis_type, sweep_type, output_names):
    async def workflow():
        async with Client(server(tmp_path), read_timeout_seconds=90) as client:
            simulation = await call(
                client,
                "run_action",
                {
                    "app": "multisim",
                    "action_name": "run_simulation",
                    "timeout_seconds": 60,
                    "retry_on_failure": False,
                    "parameters": {
                        "file_path": str(circuit),
                        "analysis_type": analysis_type,
                        "sample_count": 16,
                        "stop_time": 0.001,
                        "sweep_type": sweep_type,
                        "output_names": output_names,
                    },
                },
            )
            outputs = simulation["metadata"]["output_names"]
            assert outputs
            for name in outputs:
                data = await call(
                    client,
                    "run_action",
                    {
                        "app": "multisim",
                        "action_name": "get_output_data",
                        "parameters": {
                            "simulation_action_id": simulation["action_id"],
                            "output_name": name,
                        },
                    },
                )
                assert data["metadata"]["data"]

    asyncio.run(workflow())
