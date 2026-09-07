"""Multisim automation through an isolated, 32-bit Windows COM worker."""

from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, ValidationError

from adapters.base import BaseAdapter
from core.domain import (
    Action,
    ActionResult,
    ActionStatus,
    Artifact,
    CheckResult,
    ErrorDetail,
    ErrorSeverity,
    ValidationReport,
    ValidationStatus,
)


class _Parameters(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _CircuitInput(_Parameters):
    file_path: str = Field(min_length=1)


class _ExportInput(_CircuitInput):
    output_file: str = Field(min_length=1)
    format: Literal["text", "csv"] = "text"


class _SimulationInput(_CircuitInput):
    analysis_type: Literal["dc", "transient", "ac"] = "dc"
    output_names: list[str] = Field(default_factory=list, max_length=16)
    stop_time: FiniteFloat = Field(default=0.01, ge=1e-9, le=60)
    sample_count: int = Field(default=128, ge=2, le=10000, strict=True)
    start_frequency: FiniteFloat = Field(default=1, ge=1e-3, le=1e9)
    stop_frequency: FiniteFloat = Field(default=1000, ge=1e-3, le=1e9)
    sweep_type: Literal["linear", "decade", "octave"] = "linear"


class _OutputInput(_Parameters):
    simulation_action_id: str = Field(min_length=1)
    output_name: str = Field(min_length=1)


_INPUTS: dict[str, type[_Parameters]] = {
    "probe": _Parameters,
    "read_circuit": _CircuitInput,
    "list_components": _CircuitInput,
    "export_netlist": _ExportInput,
    "run_simulation": _SimulationInput,
    "get_output_data": _OutputInput,
}


class MultisimAdapter(BaseAdapter):
    """Keep COM architecture, apartment state, and failures outside the MCP process.

    Discovery only checks registration and files. Actual operations connect on
    demand, open temporary circuit copies, and never save the original design.
    """

    def __init__(self) -> None:
        self._com_available = False
        self._status_message = "Multisim automation is not configured."
        self._software_version: str | None = None
        self._host: Path | None = None
        self._executable: Path | None = None
        self._worker = Path(__file__).with_name("worker.ps1")
        self._simulations: dict[str, dict[str, Any]] = {}
        self._detect()

    @property
    def name(self) -> str:
        return "multisim"

    @property
    def version(self) -> str:
        return "0.1.0"

    @property
    def software_version(self) -> str | None:
        return self._software_version

    @property
    def available_actions(self) -> list[str]:
        return list(_INPUTS)

    @property
    def status_message(self) -> str:
        return self._status_message

    def check_availability(self) -> bool:
        return self._com_available

    def _detect(self) -> None:
        if sys.platform != "win32":
            self._status_message = "Multisim automation requires Windows."
            return
        try:
            import winreg

            view = winreg.KEY_READ | winreg.KEY_WOW64_32KEY
            with winreg.OpenKey(
                winreg.HKEY_CLASSES_ROOT, r"MultisimInterface.MultisimApp\CLSID", 0, view
            ) as key:
                clsid = winreg.QueryValueEx(key, "")[0]
            with winreg.OpenKey(
                winreg.HKEY_CLASSES_ROOT, rf"CLSID\{clsid}\InprocServer32", 0, view
            ) as key:
                dll = Path(winreg.QueryValueEx(key, "")[0])
            root = Path(os.environ.get("SYSTEMROOT", r"C:\Windows"))
            system = "SysWOW64" if (root / "SysWOW64").is_dir() else "System32"
            self._host = root / system / "WindowsPowerShell" / "v1.0" / "powershell.exe"
            self._executable = Path(
                os.environ.get("BIFROST_MULTISIM_EXE", str(dll.with_name("Multisim.exe")))
            )
            for path in (dll, self._host, self._executable, self._worker):
                if not path.is_file():
                    raise FileNotFoundError(f"Required Multisim runtime file not found: {path}")
            self._com_available = True
            self._status_message = (
                "32-bit COM registered; use probe to verify connection and licensing."
            )
        except OSError as exc:
            self._status_message = f"Multisim automation unavailable: {exc}"

    def _run_worker(self, name: str, parameters: dict[str, Any], timeout: int) -> dict[str, Any]:
        request = {
            "action_name": name,
            "parameters": parameters,
            "executable": str(self._executable),
            "timeout_seconds": timeout,
        }
        completed = subprocess.run(
            [
                str(self._host),
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-STA",
                "-File",
                str(self._worker),
            ],
            input=json.dumps(request, allow_nan=False),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        try:
            body = json.loads(completed.stdout)
        except (ValueError, TypeError) as exc:
            raise RuntimeError(
                f"Multisim worker returned invalid JSON: {completed.stderr[:1500]}"
            ) from exc
        if not isinstance(body, dict) or (completed.returncode and body.get("success") is True):
            raise RuntimeError("Multisim worker failed without a valid error response.")
        return body

    def execute(self, action: Action) -> ActionResult:
        start = datetime.now()
        if action.action_name not in _INPUTS:
            return self._error(
                action, "ERR_ACTION_NOT_SUPPORTED", f"Unsupported action: {action.action_name}"
            )
        try:
            parameters = _INPUTS[action.action_name].model_validate(action.parameters).model_dump()
            if action.action_name == "get_output_data":
                return self._get_output(action, parameters, start)
            if not self.check_availability():
                return self._error(action, "ERR_SOFTWARE_NOT_FOUND", self._status_message)
            if action.action_name == "run_simulation":
                if parameters["stop_frequency"] <= parameters["start_frequency"]:
                    raise ValueError("stop_frequency must be greater than start_frequency.")
                if any(not name for name in parameters["output_names"]):
                    raise ValueError("Output names must not be empty.")
                if parameters["analysis_type"] == "ac" and parameters["sweep_type"] != "linear":
                    base = 10 if parameters["sweep_type"] == "decade" else 2
                    span = math.log(
                        parameters["stop_frequency"] / parameters["start_frequency"], base
                    )
                    if math.ceil(span * parameters["sample_count"]) + 1 > 10000:
                        raise ValueError(
                            "Reduce sweep density or range to at most 10000 AC points."
                        )
                self._simulations.pop(action.action_id, None)

            source: Path | None = None
            output: Path | None = None
            if "file_path" in parameters:
                source = Path(parameters["file_path"]).expanduser().resolve()
                if not source.is_file():
                    raise FileNotFoundError(f"Circuit file not found: {source}")
                if source.suffix.lower() not in {
                    ".ms14",
                    ".ms13",
                    ".ms12",
                    ".ms11",
                    ".ms10",
                    ".ms9",
                    ".ms8",
                }:
                    raise ValueError("Use a saved Multisim design (.ms8 through .ms14).")
            if action.action_name == "export_netlist":
                output = Path(parameters["output_file"]).expanduser().resolve()
                if output == source or output.suffix.lower() not in {".txt", ".csv"}:
                    raise ValueError(
                        "Export a connectivity report to a separate .txt or .csv file, "
                        "not a circuit."
                    )
                if output.exists() and not action.confirmation_granted:
                    return self._confirmation(action, output)

            with TemporaryDirectory(prefix="bifrost-multisim-") as directory:
                worker_parameters = dict(parameters)
                if source:
                    snapshot = Path(directory) / source.name
                    shutil.copy2(source, snapshot)
                    worker_parameters["file_path"] = str(snapshot)
                # The worker returns report text; only this adapter writes authorized outputs.
                worker_parameters.pop("output_file", None)
                body = self._run_worker(
                    action.action_name, worker_parameters, action.timeout_seconds
                )
                if body.get("worker_bits") != 32:
                    raise RuntimeError("Multisim worker must be a 32-bit process.")
                if body.get("success") is not True:
                    error = body.get("error", {})
                    return self._error(
                        action,
                        error.get("code", "ERR_MULTISIM_COM"),
                        error.get("message", "Multisim operation failed."),
                    )
                data = body.get("data")
                if not isinstance(data, dict):
                    raise RuntimeError("Multisim worker omitted structured result data.")

            data["worker_bits"] = 32
            if source:
                data["source_file"] = str(source)
                data["source_preserved"] = True
            if data.get("software_version"):
                self._software_version = str(data["software_version"])
            if action.action_name == "probe" and data.get("connected") is not True:
                raise RuntimeError("Multisim did not establish an automation connection.")
            result = self._success(action, data, start)
            if action.action_name == "export_netlist":
                report = data.pop("report", None)
                if not isinstance(report, str) or not report.strip():
                    raise RuntimeError("Multisim returned an empty netlist report.")
                assert output is not None
                output.parent.mkdir(parents=True, exist_ok=True)
                try:
                    self._write_report(output, report, action.confirmation_granted)
                except FileExistsError:
                    return self._confirmation(action, output)
                payload = output.read_bytes()
                result.artifacts = [
                    Artifact(
                        path=str(output),
                        size_bytes=len(payload),
                        checksum=hashlib.sha256(payload).hexdigest(),
                        description="Multisim connectivity report",
                    )
                ]
                result.metadata.pop("report", None)
                result.metadata["report_format"] = parameters["format"]
            if action.action_name == "run_simulation":
                outputs = data.pop("outputs", None)
                if not isinstance(outputs, dict) or not outputs:
                    raise RuntimeError("Simulation returned no output data.")
                for name, series in outputs.items():
                    if not isinstance(series, dict) or not self._finite_samples(series.get("data")):
                        raise RuntimeError(
                            f"Simulation returned empty or invalid samples for {name}."
                        )
                self._simulations[action.action_id] = outputs
                while len(self._simulations) > 16:
                    self._simulations.pop(next(iter(self._simulations)))
                result.metadata.pop("outputs", None)
                result.metadata.update(
                    simulation_action_id=action.action_id,
                    output_names=list(outputs),
                    analysis_type=parameters["analysis_type"],
                )
            return result
        except (ValidationError, ValueError) as exc:
            return self._error(action, "ERR_INVALID_ARGUMENT", str(exc))
        except FileNotFoundError as exc:
            return self._error(action, "ERR_FILE_NOT_FOUND", str(exc))
        except subprocess.TimeoutExpired:
            return self._error(
                action,
                "ERR_TIMEOUT",
                "Multisim worker timed out. Inspect the application before retrying.",
            )
        except Exception as exc:
            return self._error(action, "ERR_MULTISIM_EXECUTION", str(exc))

    @staticmethod
    def _finite_samples(value: Any) -> bool:
        if isinstance(value, list):
            return bool(value) and all(MultisimAdapter._finite_samples(item) for item in value)
        return (
            isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value)
        )

    @staticmethod
    def _write_report(path: Path, report: str, overwrite: bool) -> None:
        if not overwrite:
            with path.open("x", encoding="utf-8", newline="") as handle:
                handle.write(report)
            return
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=path.parent,
            prefix=".bifrost-",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            try:
                handle.write(report)
            except BaseException:
                handle.close()
                temporary.unlink(missing_ok=True)
                raise
        try:
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    def _get_output(
        self, action: Action, parameters: dict[str, Any], start: datetime
    ) -> ActionResult:
        outputs = self._simulations.get(parameters["simulation_action_id"], {})
        series = outputs.get(parameters["output_name"])
        if series is None:
            return self._error(
                action,
                "ERR_OUTPUT_NOT_FOUND",
                "No cached output for this simulation action ID and name.",
            )
        return self._success(action, {**series, **parameters}, start)

    @staticmethod
    def _success(action: Action, data: dict[str, Any], start: datetime) -> ActionResult:
        end = datetime.now()
        return ActionResult(
            success=True,
            action_id=action.action_id,
            task_id=action.task_id,
            action_name=action.action_name,
            status=ActionStatus.SUCCESS,
            start_time=start,
            end_time=end,
            duration_ms=int((end - start).total_seconds() * 1000),
            summary=f"Multisim {action.action_name} completed.",
            metadata=data,
            logs=[f"Multisim action: {action.action_name}"],
        )

    @staticmethod
    def _error(action: Action, code: str, message: str) -> ActionResult:
        now = datetime.now()
        return ActionResult(
            success=False,
            action_id=action.action_id,
            task_id=action.task_id,
            action_name=action.action_name,
            status=ActionStatus.FAILED,
            start_time=now,
            end_time=now,
            summary=message,
            errors=[
                ErrorDetail(
                    error_code=code,
                    message=message,
                    severity=ErrorSeverity.FATAL,
                    recoverable=False,
                )
            ],
        )

    def _confirmation(self, action: Action, output: Path) -> ActionResult:
        result = self._error(
            action,
            "ERR_CONFIRMATION_REQUIRED",
            f"Existing report requires overwrite approval: {output}",
        )
        result.status = ActionStatus.CONFIRMATION_REQUIRED
        result.errors[0].severity = ErrorSeverity.NEEDS_HUMAN
        return result

    def validate(self, result: ActionResult) -> ValidationReport:
        checks = [
            CheckResult(
                check_name="execution_success",
                status=ValidationStatus.PASSED if result.success else ValidationStatus.FAILED,
            )
        ]
        for artifact in result.artifacts:
            path = Path(artifact.path)
            valid = path.is_file() and path.stat().st_size > 0
            if valid and artifact.checksum:
                valid = hashlib.sha256(path.read_bytes()).hexdigest() == artifact.checksum
            checks.append(
                CheckResult(
                    check_name=f"artifact:{path}",
                    evidence=str(path),
                    status=ValidationStatus.PASSED if valid else ValidationStatus.FAILED,
                )
            )
        failed = [check for check in checks if check.status == ValidationStatus.FAILED]
        return ValidationReport(
            action_id=result.action_id, passed=not failed, checks=checks, failed_checks=failed
        )
