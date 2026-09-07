"""Multisim contracts without starting installed software."""

import asyncio
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from adapters.multisim.adapter import MultisimAdapter
from core.actions import ActionExecutor
from core.domain import Action, ActionStatus


def action(name, **parameters):
    return Action(
        action_id="act-test",
        task_id="task-test",
        app="multisim",
        action_type="execute",
        action_name=name,
        parameters=parameters,
    )


@pytest.fixture
def adapter(monkeypatch, tmp_path):
    monkeypatch.setattr(MultisimAdapter, "_detect", lambda self: None)
    instance = MultisimAdapter()
    instance._com_available = True
    instance._host = tmp_path / "powershell.exe"
    instance._executable = tmp_path / "multisim.exe"
    return instance


@pytest.fixture
def circuit(tmp_path):
    path = tmp_path / "source.ms14"
    path.write_bytes(b"test circuit")
    return path


def success(**data):
    return {"success": True, "worker_bits": 32, "data": data}


def test_probe_returns_actual_connection_details(adapter, monkeypatch):
    monkeypatch.setattr(
        adapter,
        "_run_worker",
        Mock(return_value=success(connected=True, software_version="Multisim 14.3")),
    )
    result = adapter.execute(action("probe"))
    assert result.success
    assert adapter.software_version == "Multisim 14.3"
    assert result.metadata["worker_bits"] == 32


def test_read_uses_a_copy_and_preserves_source(adapter, circuit, monkeypatch):
    def inspect(_name, parameters, _timeout):
        snapshot = Path(parameters["file_path"])
        assert snapshot != circuit
        assert snapshot.read_bytes() == circuit.read_bytes()
        snapshot.write_bytes(b"in-memory application side effects")
        return success(components=["R1", "R2"], outputs=["1"])

    monkeypatch.setattr(adapter, "_run_worker", inspect)
    result = adapter.execute(action("read_circuit", file_path=str(circuit)))
    assert result.success
    assert result.metadata["components"] == ["R1", "R2"]
    assert circuit.read_bytes() == b"test circuit"


def test_export_writes_real_report_with_artifact(adapter, circuit, tmp_path, monkeypatch):
    monkeypatch.setattr(adapter, "_run_worker", Mock(return_value=success(report="R1 1 0\n")))
    output = tmp_path / "report.txt"
    result = adapter.execute(
        action("export_netlist", file_path=str(circuit), output_file=str(output))
    )
    assert result.success
    assert output.read_text() == "R1 1 0\n"
    assert result.artifacts[0].size_bytes > 0
    assert result.artifacts[0].checksum
    assert adapter.validate(result).passed
    output.write_text("")
    assert not adapter.validate(result).passed


def test_export_never_overwrites_a_circuit(adapter, circuit, monkeypatch):
    worker = Mock()
    monkeypatch.setattr(adapter, "_run_worker", worker)
    result = adapter.execute(
        action("export_netlist", file_path=str(circuit), output_file=str(circuit))
    )
    assert not result.success
    worker.assert_not_called()


def test_export_requires_explicit_output(adapter, circuit, monkeypatch):
    worker = Mock()
    monkeypatch.setattr(adapter, "_run_worker", worker)
    result = adapter.execute(action("export_netlist", file_path=str(circuit)))
    assert not result.success
    worker.assert_not_called()


def test_output_created_during_execution_is_not_overwritten(
    adapter, circuit, tmp_path, monkeypatch
):
    output = tmp_path / "report.txt"

    def race(*_args):
        output.write_text("another writer")
        return success(report="our report")

    monkeypatch.setattr(adapter, "_run_worker", race)
    result = adapter.execute(
        action("export_netlist", file_path=str(circuit), output_file=str(output))
    )
    assert result.status == ActionStatus.CONFIRMATION_REQUIRED
    assert output.read_text() == "another writer"


def test_relay_confirmation_allows_explicit_overwrite(adapter, circuit, tmp_path, monkeypatch):
    from codex_plugin.mcp.tools import configure_runtime, confirm_action, run_action

    worker = Mock(return_value=success(report="new report"))
    monkeypatch.setattr(adapter, "_run_worker", worker)
    executor = ActionExecutor()
    executor.register_adapter(adapter)
    configure_runtime(executor)
    output = tmp_path / "report.txt"
    output.write_text("old report")
    pending = asyncio.run(
        run_action(
            "multisim", "export_netlist", {"file_path": str(circuit), "output_file": str(output)}
        )
    )
    assert pending["status"] == "confirmation_required"
    worker.assert_not_called()
    result = asyncio.run(confirm_action(pending["action_id"], True))
    assert result["success"]
    assert output.read_text() == "new report"


def test_simulation_results_are_addressed_by_action_id(adapter, circuit, monkeypatch):
    worker = Mock(return_value=success(outputs={"1": {"data": [1.25], "interpolation": 0}}))
    monkeypatch.setattr(adapter, "_run_worker", worker)
    result = adapter.execute(action("run_simulation", file_path=str(circuit), analysis_type="dc"))
    assert result.success
    data = adapter.execute(
        action("get_output_data", simulation_action_id=result.action_id, output_name="1")
    )
    assert data.success
    assert data.metadata["data"] == [1.25]
    assert worker.call_count == 1
    missing = adapter.execute(
        action("get_output_data", simulation_action_id="missing", output_name="1")
    )
    assert not missing.success


@pytest.mark.parametrize(
    "parameters",
    [
        {"analysis_type": "not-supported"},
        {"stop_time": -1},
        {"sample_count": 10000001},
        {"output_names": "1"},
        {"stop_time": float("nan")},
        {"extra_command": "Save"},
    ],
)
def test_invalid_simulation_parameters_never_reach_com(adapter, circuit, monkeypatch, parameters):
    worker = Mock()
    monkeypatch.setattr(adapter, "_run_worker", worker)
    result = adapter.execute(action("run_simulation", file_path=str(circuit), **parameters))
    assert not result.success
    worker.assert_not_called()


@pytest.mark.parametrize(
    "payload",
    [
        {
            "success": False,
            "worker_bits": 32,
            "error": {"code": "ERR_MULTISIM_COM", "message": "failed"},
        },
        {"success": True, "worker_bits": 64, "data": {}},
    ],
)
def test_worker_failures_do_not_report_success(adapter, monkeypatch, payload):
    monkeypatch.setattr(adapter, "_run_worker", Mock(return_value=payload))
    result = adapter.execute(action("probe"))
    assert not result.success


def test_timeout_is_not_automatically_retryable(adapter, monkeypatch):
    monkeypatch.setattr(
        adapter, "_run_worker", Mock(side_effect=subprocess.TimeoutExpired("worker", 2))
    )
    result = adapter.execute(action("probe"))
    assert not result.success
    assert result.errors[0].error_code == "ERR_TIMEOUT"
    assert result.errors[0].recoverable is False


def test_worker_transport_passes_json_not_shell_code(adapter, monkeypatch):
    run = Mock(
        return_value=SimpleNamespace(
            returncode=0, stdout=json.dumps(success(connected=True)), stderr=""
        )
    )
    monkeypatch.setattr(subprocess, "run", run)
    path = 'C:/test/quote"; not-a-command.ms14'
    adapter._run_worker("read_circuit", {"file_path": path}, 30)
    args, kwargs = run.call_args
    assert args[0][0] == str(adapter._host)
    assert "-File" in args[0]
    assert "-STA" in args[0]
    assert "-ExecutionPolicy" not in args[0]
    assert not kwargs.get("shell", False)
    assert json.loads(kwargs["input"])["parameters"]["file_path"] == path


def test_missing_file_never_reaches_com(adapter, tmp_path, monkeypatch):
    worker = Mock()
    monkeypatch.setattr(adapter, "_run_worker", worker)
    result = adapter.execute(action("read_circuit", file_path=str(tmp_path / "missing.ms14")))
    assert not result.success
    worker.assert_not_called()


@pytest.mark.parametrize(
    "stdout,returncode", [("not json", 1), ("[]", 0), (json.dumps(success(connected=True)), 1)]
)
def test_malformed_worker_responses_fail_closed(adapter, monkeypatch, stdout, returncode):
    monkeypatch.setattr(
        subprocess,
        "run",
        Mock(
            return_value=SimpleNamespace(
                stdout=stdout, stderr="worker failure", returncode=returncode
            )
        ),
    )
    result = adapter.execute(action("probe"))
    assert not result.success
    assert result.errors[0].error_code == "ERR_MULTISIM_EXECUTION"


@pytest.mark.parametrize("samples", [[], [float("nan")], [float("inf")], [True], ["0.5"]])
def test_invalid_samples_are_not_cached(adapter, circuit, monkeypatch, samples):
    monkeypatch.setattr(
        adapter, "_run_worker", Mock(return_value=success(outputs={"1": {"data": samples}}))
    )
    result = adapter.execute(action("run_simulation", file_path=str(circuit)))
    assert not result.success
    assert not adapter._simulations


def test_output_parameters_cannot_claim_confirmation(adapter, circuit, monkeypatch):
    worker = Mock()
    monkeypatch.setattr(adapter, "_run_worker", worker)
    result = adapter.execute(
        action(
            "export_netlist",
            file_path=str(circuit),
            output_file="report.txt",
            confirmation_granted=True,
        )
    )
    assert not result.success
    worker.assert_not_called()


def test_ac_density_is_bounded(adapter, circuit, monkeypatch):
    worker = Mock()
    monkeypatch.setattr(adapter, "_run_worker", worker)
    result = adapter.execute(
        action(
            "run_simulation",
            file_path=str(circuit),
            analysis_type="ac",
            sweep_type="decade",
            sample_count=10000,
            start_frequency=0.001,
            stop_frequency=1e9,
        )
    )
    assert not result.success
    worker.assert_not_called()


def test_discovery_does_not_start_the_application(monkeypatch):
    run = Mock()
    monkeypatch.setattr(subprocess, "run", run)
    instance = MultisimAdapter()
    assert isinstance(instance.check_availability(), bool)
    run.assert_not_called()
