"""MCP-facing tool implementations for Bifrost.

The core executor deliberately does not own process-wide state.  This module
provides that state at the relay boundary so an action result can be validated,
logged, or explicitly confirmed by a later tool call.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from threading import RLock
from time import sleep
from typing import Any, Literal, Protocol, cast
from uuid import uuid4

from adapters.base import BaseAdapter
from core.actions import ActionExecutor
from core.domain import (
    Action,
    ActionResult,
    ActionStatus,
    ErrorDetail,
    ErrorSeverity,
    ExecutionMode,
    RiskLevel,
)
from core.validators import ResultValidator, builtin_rules

from .schemas import (
    CollectLogsInput,
    ConfirmActionInput,
    ListAdaptersInput,
    PreviewActionInput,
    RunActionInput,
    ValidateResultInput,
)

_DANGEROUS_ACTION_WORDS = (
    "flash",
    "erase",
    "burn",
    "program",
    "modify",
    "replace",
    "save",
    "write",
    "write_firmware",
)


@dataclass
class _PendingAction:
    action: Action
    retry_on_failure: bool = True
    created_at: datetime = field(default_factory=datetime.now)


class _ToolRegistrar(Protocol):
    def tool(
        self,
        name: str | None = None,
        *,
        description: str | None = None,
        **kwargs: Any,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]: ...


class RelayRuntime:
    """Runtime registry shared by tool calls in one MCP server process."""

    def __init__(self, executor: ActionExecutor | None = None, register_defaults: bool = True):
        self.executor = executor or ActionExecutor()
        self.results: dict[str, ActionResult] = {}
        self.actions: dict[str, Action] = {}
        self.pending: dict[str, _PendingAction] = {}
        self.startup_errors: list[str] = []
        self._lock = RLock()
        if register_defaults:
            self.register_default_adapters()

    def register_adapter(self, adapter: BaseAdapter) -> None:
        self.executor.register_adapter(adapter)

    def register_default_adapters(self) -> None:
        """Register adapters that are shipped with the core package.

        Adapter constructors are intentionally isolated so an optional COM or
        KiCad dependency cannot prevent the MCP server from starting.
        """

        try:
            from adapters.kicad.adapter import KiCadAdapter

            self.register_adapter(KiCadAdapter())
        except Exception as exc:
            self.startup_errors.append(f"Unable to initialize KiCad adapter: {exc}")

        try:
            from adapters.multisim.adapter import MultisimAdapter

            self.register_adapter(MultisimAdapter())
        except Exception as exc:
            self.startup_errors.append(f"Unable to initialize Multisim adapter: {exc}")

    def adapter(self, app: str) -> BaseAdapter | None:
        try:
            return self.executor.get_adapter(app)
        except AttributeError:
            # Compatibility with the original executor before get_adapter was
            # added; this branch can be removed after downstream consumers move.
            return getattr(self.executor, "_adapters", {}).get(app)
        except Exception:
            return None

    def record(
        self,
        action: Action,
        result: ActionResult,
        *,
        retry_on_failure: bool = True,
    ) -> None:
        with self._lock:
            self.actions[action.action_id] = action
            self.results[result.action_id] = result
            if result.status == ActionStatus.CONFIRMATION_REQUIRED:
                self.pending[action.action_id] = _PendingAction(
                    action=action,
                    retry_on_failure=retry_on_failure,
                )
            else:
                self.pending.pop(action.action_id, None)

    def replace_result(self, result: ActionResult) -> None:
        with self._lock:
            self.results[result.action_id] = result


_runtime: RelayRuntime | None = None


def get_runtime() -> RelayRuntime:
    """Return the process-wide relay runtime, creating it on first use."""

    global _runtime
    if _runtime is None:
        _runtime = RelayRuntime()
    return _runtime


def configure_runtime(executor: ActionExecutor, *, register_defaults: bool = False) -> RelayRuntime:
    """Replace the process runtime; primarily useful for integration tests."""

    global _runtime
    _runtime = RelayRuntime(executor=executor, register_defaults=register_defaults)
    return _runtime


def reset_runtime() -> RelayRuntime:
    """Reset runtime state and restore the default adapter registry."""

    global _runtime
    _runtime = RelayRuntime()
    return _runtime


def _dump(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value


def _error_result(
    code: str,
    message: str,
    *,
    suggested_action: str = "",
    context: dict[str, Any] | None = None,
    severity: ErrorSeverity = ErrorSeverity.FATAL,
    recoverable: bool = False,
) -> dict[str, Any]:
    error = ErrorDetail(
        error_code=code,
        severity=severity,
        message=message,
        suggested_action=suggested_action,
        context=context or {},
        recoverable=recoverable,
    )
    return {"success": False, "summary": message, "errors": [_dump(error)]}


def _validation_error(exc: Exception) -> dict[str, Any]:
    return _error_result(
        "ERR_INVALID_ARGUMENT",
        f"Invalid tool arguments: {exc}",
        suggested_action="Correct the arguments and try again",
    )


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


def _effective_risk(action_name: str, requested: RiskLevel) -> RiskLevel:
    if requested in {RiskLevel.LOW, RiskLevel.MEDIUM} and any(
        word in action_name.lower() for word in _DANGEROUS_ACTION_WORDS
    ):
        return RiskLevel.HIGH
    return requested


def _permission_note(action_name: str, risk: RiskLevel) -> str:
    if risk == RiskLevel.CRITICAL:
        return f"Critical action '{action_name}' may affect production equipment."
    if risk == RiskLevel.HIGH:
        return f"High-risk action '{action_name}' may alter hardware or erase data."
    return ""


def _existing_output_targets(parameters: dict[str, Any]) -> list[str]:
    """Return output paths that would be overwritten by an action."""

    targets: list[str] = []
    output_file = parameters.get("output_file")
    if output_file:
        try:
            path = Path(str(output_file))
            if path.exists():
                targets.append(str(path))
        except OSError:
            pass

    output_dir = parameters.get("output_dir")
    if output_dir:
        try:
            path = Path(str(output_dir))
            if path.is_dir() and next(path.iterdir(), None) is not None:
                targets.append(str(path))
        except OSError:
            pass
    return targets


def _make_action(args: RunActionInput) -> Action:
    requested_risk = RiskLevel(args.risk_level)
    risk = _effective_risk(args.action_name, requested_risk)
    overwrite_targets = _existing_output_targets(args.parameters)
    if overwrite_targets and risk == RiskLevel.LOW:
        risk = RiskLevel.MEDIUM
    requires_confirmation = bool(overwrite_targets) or risk in {
        RiskLevel.HIGH,
        RiskLevel.CRITICAL,
    }
    note = _permission_note(args.action_name, risk)
    if overwrite_targets:
        note = f"Action '{args.action_name}' will overwrite existing output: {overwrite_targets}."
    return Action(
        action_id=_new_id("act"),
        task_id=args.task_id or _new_id("task"),
        action_name=args.action_name,
        action_type=ActionExecutor._infer_action_type(args.action_name),
        app=args.app,
        risk_level=risk,
        parameters=args.parameters,
        requires_confirmation=requires_confirmation,
        permission_note=note,
        timeout_seconds=args.timeout_seconds,
    )


def _result_payload(result: ActionResult) -> dict[str, Any]:
    return cast(dict[str, Any], _dump(result))


def _confirmation_result(action: Action) -> ActionResult:
    now = datetime.now()
    note = action.permission_note or _permission_note(action.action_name, action.risk_level)
    error = ErrorDetail(
        error_code="ERR_CONFIRMATION_REQUIRED",
        severity=ErrorSeverity.NEEDS_HUMAN,
        message=note or f"Action '{action.action_name}' requires explicit confirmation.",
        suggested_action="Call confirm_action with confirm=true or confirm=false",
        context={
            "action_id": action.action_id,
            "app": action.app,
            "risk_level": action.risk_level.value,
        },
        recoverable=True,
    )
    return ActionResult(
        success=False,
        action_id=action.action_id,
        task_id=action.task_id,
        action_name=action.action_name,
        status=ActionStatus.CONFIRMATION_REQUIRED,
        start_time=now,
        end_time=now,
        summary="Action is waiting for explicit confirmation.",
        warnings=[note] if note else [],
        errors=[error],
        next_suggestion=f"Call confirm_action(action_id='{action.action_id}', confirm=true)",
        metadata={"risk_level": action.risk_level.value},
    )


def _adapter_exception_result(action: Action, exc: Exception) -> ActionResult:
    now = datetime.now()
    return ActionResult(
        success=False,
        action_id=action.action_id,
        task_id=action.task_id,
        action_name=action.action_name,
        status=ActionStatus.FAILED,
        start_time=now,
        end_time=now,
        summary=f"Adapter execution failed: {exc}",
        errors=[
            ErrorDetail(
                error_code="ERR_ADAPTER_EXCEPTION",
                severity=ErrorSeverity.FATAL,
                message=str(exc),
                context={"app": action.app, "action_name": action.action_name},
            )
        ],
    )


def _is_retryable(action: Action, result: ActionResult) -> bool:
    return (
        not result.success
        and result.status != ActionStatus.CONFIRMATION_REQUIRED
        and any(error.severity in action.retry_policy.retry_on for error in result.errors)
    )


def _execute(
    runtime: RelayRuntime,
    action: Action,
    *,
    retry_on_failure: bool,
) -> ActionResult:
    max_attempts = 1 + (action.retry_policy.max_retries if retry_on_failure else 0)
    result: ActionResult | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            result = runtime.executor.execute(action)
        except Exception as exc:
            result = _adapter_exception_result(action, exc)

        if not _is_retryable(action, result) or attempt == max_attempts:
            break

        delay = action.retry_policy.delay_seconds * (
            action.retry_policy.backoff_multiplier ** (attempt - 1)
        )
        sleep(delay)

    if result is None:  # Defensive: max_attempts is constrained to at least one.
        raise RuntimeError("Action execution produced no result")
    result.metadata.setdefault("risk_level", action.risk_level.value)
    result.metadata["attempt_count"] = attempt
    runtime.record(action, result, retry_on_failure=retry_on_failure)
    return result


def _handle_list_adapters(args: dict[str, Any]) -> dict[str, Any]:
    try:
        request = ListAdaptersInput.model_validate(args)
    except Exception as exc:
        return _validation_error(exc)

    runtime = get_runtime()
    adapters = runtime.executor.list_adapters(filter=request.filter)
    available = [adapter for adapter in adapters if adapter.available]
    return {
        "success": True,
        "adapters": [_dump(adapter) for adapter in adapters],
        "count": len(adapters),
        "available_count": len(available),
        "summary": f"Found {len(adapters)} registered adapter(s), {len(available)} available.",
        "warnings": list(runtime.startup_errors),
    }


def _handle_run_action(args: dict[str, Any]) -> dict[str, Any]:
    try:
        request = RunActionInput.model_validate(args)
    except Exception as exc:
        return _validation_error(exc)

    runtime = get_runtime()
    action = _make_action(request)
    if runtime.adapter(action.app) is None:
        result = _execute(runtime, action, retry_on_failure=request.retry_on_failure)
        return _result_payload(result)

    if request.mode == ExecutionMode.DRY_RUN.value:
        now = datetime.now()
        result = ActionResult(
            success=True,
            action_id=action.action_id,
            task_id=action.task_id,
            action_name=action.action_name,
            status=ActionStatus.SUCCESS,
            start_time=now,
            end_time=now,
            summary="Dry-run completed; no adapter side effects were performed.",
            next_suggestion="Call run_action again with mode='normal' to execute.",
            metadata={"dry_run": True, "risk_level": action.risk_level.value},
        )
        runtime.record(action, result)
        return _result_payload(result)

    if action.requires_confirmation:
        result = _confirmation_result(action)
        runtime.record(action, result, retry_on_failure=request.retry_on_failure)
        return _result_payload(result)

    result = _execute(runtime, action, retry_on_failure=request.retry_on_failure)
    return _result_payload(result)


def _handle_validate_result(args: dict[str, Any]) -> dict[str, Any]:
    try:
        request = ValidateResultInput.model_validate(args)
    except Exception as exc:
        return _validation_error(exc)

    runtime = get_runtime()
    result = runtime.results.get(request.action_id)
    action = runtime.actions.get(request.action_id)
    if result is None or action is None:
        return _error_result(
            "ERR_ACTION_NOT_FOUND",
            f"No action result is available for '{request.action_id}'.",
            suggested_action="Call run_action first and use its action_id.",
            context={"action_id": request.action_id},
        )

    adapter = runtime.adapter(action.app)
    if adapter is None:
        return _error_result(
            "ERR_ADAPTER_NOT_FOUND",
            f"No adapter is registered for '{action.app}'.",
            suggested_action="Call list_adapters to inspect registered adapters.",
            context={"app": action.app},
        )

    if request.checks:
        unknown = [name for name in request.checks if name not in builtin_rules]
        if unknown:
            return _error_result(
                "ERR_VALIDATION_CHECK_NOT_FOUND",
                f"Unknown validation check(s): {unknown}",
                suggested_action=f"Use one of: {sorted(builtin_rules)}",
            )
        validator = ResultValidator()
        validator.register_all([builtin_rules[name] for name in request.checks])
        report = validator.validate(result)
    else:
        try:
            report = adapter.validate(result)
        except Exception as exc:
            return _error_result(
                "ERR_VALIDATION_EXCEPTION",
                f"Adapter validation failed: {exc}",
                context={"action_id": request.action_id},
            )

    result.validation = report
    runtime.replace_result(result)
    return {
        "success": report.passed,
        "action_id": request.action_id,
        "validation": _dump(report),
        "summary": report.recommendation
        or ("Validation passed." if report.passed else "Validation failed."),
    }


def _handle_collect_logs(args: dict[str, Any]) -> dict[str, Any]:
    try:
        request = CollectLogsInput.model_validate(args)
    except Exception as exc:
        return _validation_error(exc)

    runtime = get_runtime()
    if request.action_id and request.action_id not in runtime.results:
        return _error_result(
            "ERR_ACTION_NOT_FOUND",
            f"No action result is available for '{request.action_id}'.",
            context={"action_id": request.action_id},
        )

    results = list(runtime.results.values())
    if request.action_id:
        results = [result for result in results if result.action_id == request.action_id]
    if request.task_id:
        results = [result for result in results if result.task_id == request.task_id]

    if not results:
        return _error_result(
            "ERR_LOGS_NOT_FOUND",
            "No matching action logs were found.",
            suggested_action="Provide a known action_id or task_id.",
        )

    logs = [line for result in results for line in result.logs]
    errors = [error for result in results for error in result.errors]
    artifacts = [artifact for result in results for artifact in result.artifacts]
    raw_output = (
        [result.raw_output for result in results if result.raw_output]
        if request.include_raw_output
        else None
    )
    text = "\n".join(logs)
    if request.format == "text":
        text = text or "No log lines were recorded."

    payload: dict[str, Any] = {
        "success": True,
        "action_id": request.action_id or None,
        "task_id": request.task_id or None,
        "logs": logs,
        "errors": [_dump(error) for error in errors],
        "artifacts": [_dump(artifact) for artifact in artifacts],
        "raw_output": raw_output,
        "summary": (
            f"Collected {len(logs)} log line(s), {len(errors)} error(s), "
            f"and {len(artifacts)} artifact(s)."
        ),
    }
    if request.format == "text":
        payload["text"] = text
    return payload


def _handle_confirm_action(args: dict[str, Any]) -> dict[str, Any]:
    try:
        request = ConfirmActionInput.model_validate(args)
    except Exception as exc:
        return _validation_error(exc)

    runtime = get_runtime()
    pending = runtime.pending.get(request.action_id)
    current = runtime.results.get(request.action_id)
    if pending is None or current is None or current.status != ActionStatus.CONFIRMATION_REQUIRED:
        return _error_result(
            "ERR_NOT_IN_CONFIRMABLE_STATE",
            f"Action '{request.action_id}' is not waiting for confirmation.",
            context={"action_id": request.action_id},
        )

    action = pending.action
    if not request.confirm:
        now = datetime.now()
        cancelled = ActionResult(
            success=False,
            action_id=action.action_id,
            task_id=action.task_id,
            action_name=action.action_name,
            status=ActionStatus.CANCELLED,
            start_time=now,
            end_time=now,
            summary="Action cancelled before execution.",
            logs=[request.reason] if request.reason else [],
            metadata={"cancel_reason": request.reason, "risk_level": action.risk_level.value},
        )
        runtime.replace_result(cancelled)
        runtime.pending.pop(action.action_id, None)
        return {
            "success": True,
            "confirmed": False,
            "action_id": action.action_id,
            "message": f"Cancelled {action.action_name}.",
            "next_step": "Modify the parameters and call run_action again if needed.",
            "result": _result_payload(cancelled),
        }

    confirmed_action = action.model_copy(update={"requires_confirmation": False})
    result = _execute(
        runtime,
        confirmed_action,
        retry_on_failure=pending.retry_on_failure,
    )
    return {
        "success": result.success,
        "confirmed": True,
        "action_id": action.action_id,
        "message": f"Confirmation accepted for {action.action_name}.",
        "next_step": "Inspect the returned result and validate it if appropriate.",
        "result": _result_payload(result),
    }


def _handle_preview_action(args: dict[str, Any]) -> dict[str, Any]:
    try:
        request = PreviewActionInput.model_validate(args)
    except Exception as exc:
        return _validation_error(exc)

    runtime = get_runtime()
    adapter = runtime.adapter(request.app)
    if adapter is None:
        return _error_result(
            "ERR_ADAPTER_NOT_FOUND",
            f"No adapter is registered for '{request.app}'.",
            suggested_action="Call list_adapters to inspect registered adapters.",
        )
    if request.action_name not in adapter.available_actions:
        return _error_result(
            "ERR_ACTION_NOT_SUPPORTED",
            f"Adapter '{request.app}' does not support '{request.action_name}'.",
            suggested_action=f"Use one of: {adapter.available_actions}",
        )

    parameters = request.parameters
    risk = _effective_risk(request.action_name, RiskLevel.LOW)
    overwrite_targets = _existing_output_targets(parameters)
    if overwrite_targets and risk == RiskLevel.LOW:
        risk = RiskLevel.MEDIUM
    will_modify: list[str] = []
    will_create: list[str] = []
    will_delete: list[str] = []
    output_dir = parameters.get("output_dir")
    output_file = parameters.get("output_file")
    project_path = parameters.get("project_path") or parameters.get("file_path")
    if output_dir:
        will_modify.append(str(output_dir))
        will_create.append(str(output_dir))
    if output_file:
        will_modify.append(str(output_file))
        will_create.append(str(output_file))
    if project_path and risk in {RiskLevel.HIGH, RiskLevel.CRITICAL}:
        will_modify.append(str(project_path))
    if any(word in request.action_name.lower() for word in ("erase", "flash", "burn")):
        will_delete.append("target device memory or existing firmware")

    warnings: list[str] = []
    if not adapter.check_availability():
        warnings.append("The adapter is registered but its target software is unavailable.")
    preview = {
        "will_modify_files": will_modify,
        "will_create_files": will_create,
        "will_delete_files": will_delete,
        "estimated_duration_seconds": 0,
        "requires_confirmation": bool(overwrite_targets)
        or risk in {RiskLevel.HIGH, RiskLevel.CRITICAL},
        "risk_level": risk.value,
        "risks": (
            [f"Existing output will be overwritten: {overwrite_targets}"]
            if overwrite_targets
            else [_permission_note(request.action_name, risk)]
            if risk != RiskLevel.LOW
            else []
        ),
        "warnings": warnings,
    }
    return {
        "success": True,
        "preview": preview,
        "summary": "Action preview generated without execution.",
    }


async def list_adapters(filter: str = "") -> dict[str, Any]:
    return _handle_list_adapters({"filter": filter})


async def run_action(
    app: str,
    action_name: str,
    parameters: dict[str, Any] | None = None,
    mode: Literal["dry_run", "normal", "force"] = "normal",
    risk_level: Literal["low", "medium", "high", "critical"] = "low",
    task_id: str = "",
    timeout_seconds: int = 300,
    retry_on_failure: bool = True,
) -> dict[str, Any]:
    return _handle_run_action(
        {
            "app": app,
            "action_name": action_name,
            "parameters": parameters or {},
            "mode": mode,
            "risk_level": risk_level,
            "task_id": task_id,
            "timeout_seconds": timeout_seconds,
            "retry_on_failure": retry_on_failure,
        }
    )


async def validate_result(action_id: str, checks: list[str] | None = None) -> dict[str, Any]:
    return _handle_validate_result({"action_id": action_id, "checks": checks or []})


async def collect_logs(
    action_id: str = "",
    task_id: str = "",
    include_raw_output: bool = False,
    format: Literal["json", "text"] = "json",
) -> dict[str, Any]:
    return _handle_collect_logs(
        {
            "action_id": action_id,
            "task_id": task_id,
            "include_raw_output": include_raw_output,
            "format": format,
        }
    )


async def confirm_action(action_id: str, confirm: bool, reason: str = "") -> dict[str, Any]:
    return _handle_confirm_action({"action_id": action_id, "confirm": confirm, "reason": reason})


async def preview_action(
    app: str,
    action_name: str,
    parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _handle_preview_action(
        {
            "app": app,
            "action_name": action_name,
            "parameters": parameters or {},
        }
    )


def register_all_tools(mcp: _ToolRegistrar) -> None:
    """Register the six public tools on an MCPServer instance."""

    @mcp.tool(
        name="list_adapters",
        description="List registered industrial software adapters and availability.",
    )
    async def _list_adapters(filter: str = "") -> dict[str, Any]:
        return await list_adapters(filter)

    @mcp.tool(
        name="run_action",
        description=(
            "Execute a structured action through an industrial software adapter. "
            "High-risk and overwrite actions always require confirm_action, including "
            "in force mode."
        ),
    )
    async def _run_action(
        app: str,
        action_name: str,
        parameters: dict[str, Any] | None = None,
        mode: Literal["dry_run", "normal", "force"] = "normal",
        risk_level: Literal["low", "medium", "high", "critical"] = "low",
        task_id: str = "",
        timeout_seconds: int = 300,
        retry_on_failure: bool = True,
    ) -> dict[str, Any]:
        return await run_action(
            app,
            action_name,
            parameters,
            mode,
            risk_level,
            task_id,
            timeout_seconds,
            retry_on_failure,
        )

    @mcp.tool(
        name="validate_result",
        description="Validate a stored action result with adapter or built-in checks.",
    )
    async def _validate_result(action_id: str, checks: list[str] | None = None) -> dict[str, Any]:
        return await validate_result(action_id, checks)

    @mcp.tool(
        name="collect_logs",
        description="Collect logs, errors, and artifacts for an action or task.",
    )
    async def _collect_logs(
        action_id: str = "",
        task_id: str = "",
        include_raw_output: bool = False,
        format: Literal["json", "text"] = "json",
    ) -> dict[str, Any]:
        return await collect_logs(action_id, task_id, include_raw_output, format)

    @mcp.tool(
        name="confirm_action",
        description="Explicitly confirm or cancel an action waiting at the safety gate.",
    )
    async def _confirm_action(action_id: str, confirm: bool, reason: str = "") -> dict[str, Any]:
        return await confirm_action(action_id, confirm, reason)

    @mcp.tool(
        name="preview_action",
        description="Preview an adapter action without executing it.",
    )
    async def _preview_action(
        app: str,
        action_name: str,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await preview_action(app, action_name, parameters)


__all__ = [
    "RelayRuntime",
    "collect_logs",
    "configure_runtime",
    "confirm_action",
    "get_runtime",
    "list_adapters",
    "preview_action",
    "register_all_tools",
    "reset_runtime",
    "run_action",
    "validate_result",
]
