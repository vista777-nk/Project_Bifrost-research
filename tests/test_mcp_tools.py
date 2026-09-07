"""Relay tool integration tests using the dependency-free MockAdapter."""

from __future__ import annotations

import asyncio
from unittest.mock import Mock

import pytest
from codex_plugin.mcp import tools as mcp_tools
from codex_plugin.mcp.schemas import get_tool_schemas
from codex_plugin.mcp.tools import (
    collect_logs,
    configure_runtime,
    confirm_action,
    list_adapters,
    preview_action,
    run_action,
    validate_result,
)

from adapters.mock_adapter import MockAdapter
from core.actions import ActionExecutor
from core.domain import ActionStatus, ErrorSeverity


def _configure(*, mode: str = "success") -> None:
    executor = ActionExecutor()
    executor.register_adapter(
        MockAdapter(
            name="mock",
            mode=mode,
            actions=["mock_action", "flash_firmware", "export_gerber"],
        )
    )
    configure_runtime(executor)


def test_tool_schemas_cover_all_tools() -> None:
    schemas = get_tool_schemas()
    assert set(schemas) == {
        "list_adapters",
        "run_action",
        "validate_result",
        "collect_logs",
        "confirm_action",
        "preview_action",
    }
    assert "app" in schemas["run_action"]["properties"]
    assert "action_id" in schemas["validate_result"]["required"]


def test_list_and_run_result_lifecycle() -> None:
    _configure()

    adapters = asyncio.run(list_adapters())
    assert adapters["success"] is True
    assert adapters["adapters"][0]["name"] == "mock"

    result = asyncio.run(run_action("mock", "mock_action", task_id="task-42"))
    assert result["success"] is True
    assert result["status"] == ActionStatus.SUCCESS.value
    assert result["task_id"] == "task-42"

    validation = asyncio.run(validate_result(result["action_id"]))
    assert validation["success"] is True
    assert validation["validation"]["passed"] is True

    logs = asyncio.run(collect_logs(task_id="task-42", format="text"))
    assert logs["success"] is True
    assert "text" in logs


def test_high_risk_action_requires_confirmation_then_executes() -> None:
    _configure()

    pending = asyncio.run(run_action("mock", "flash_firmware"))
    assert pending["success"] is False
    assert pending["status"] == ActionStatus.CONFIRMATION_REQUIRED.value
    assert pending["errors"][0]["error_code"] == "ERR_CONFIRMATION_REQUIRED"

    confirmed = asyncio.run(confirm_action(pending["action_id"], confirm=True, reason="approved"))
    assert confirmed["success"] is True
    assert confirmed["confirmed"] is True
    assert confirmed["result"]["status"] == ActionStatus.SUCCESS.value

    repeated = asyncio.run(confirm_action(pending["action_id"], confirm=True))
    assert repeated["success"] is False
    assert repeated["errors"][0]["error_code"] == "ERR_NOT_IN_CONFIRMABLE_STATE"


def test_force_mode_does_not_bypass_high_risk_confirmation() -> None:
    _configure()
    pending = asyncio.run(run_action("mock", "mock_action", mode="force", risk_level="high"))
    assert pending["status"] == ActionStatus.CONFIRMATION_REQUIRED.value


@pytest.mark.parametrize("mode", ["normal", "force"])
@pytest.mark.parametrize("risk_level", ["low", "medium", "high", "critical"])
def test_dangerous_action_risk_cannot_be_downgraded(mode, risk_level, monkeypatch) -> None:
    _configure()
    adapter = mcp_tools.get_runtime().executor.get_adapter("mock")
    execute = Mock(wraps=adapter.execute)
    monkeypatch.setattr(adapter, "execute", execute)

    pending = asyncio.run(
        run_action("mock", "flash_firmware", mode=mode, risk_level=risk_level)
    )

    execute.assert_not_called()
    assert pending["status"] == ActionStatus.CONFIRMATION_REQUIRED.value
    assert pending["metadata"]["risk_level"] == (
        "critical" if risk_level == "critical" else "high"
    )

    confirmed = asyncio.run(confirm_action(pending["action_id"], confirm=True))
    assert confirmed["success"] is True
    execute.assert_called_once()


@pytest.mark.parametrize("risk_level", ["low", "medium"])
def test_nondangerous_action_keeps_requested_risk(risk_level) -> None:
    _configure()

    result = asyncio.run(run_action("mock", "mock_action", risk_level=risk_level))

    assert result["success"] is True
    assert result["metadata"]["risk_level"] == risk_level


def test_confirmation_can_cancel_without_adapter_execution() -> None:
    _configure(mode="fail")
    pending = asyncio.run(run_action("mock", "flash_firmware"))

    cancelled = asyncio.run(
        confirm_action(pending["action_id"], confirm=False, reason="not approved")
    )
    assert cancelled["success"] is True
    assert cancelled["confirmed"] is False
    assert cancelled["result"]["status"] == ActionStatus.CANCELLED.value


def test_dry_run_and_preview_do_not_execute_adapter() -> None:
    _configure(mode="fail")
    dry_run = asyncio.run(run_action("mock", "mock_action", mode="dry_run"))
    assert dry_run["success"] is True
    assert dry_run["metadata"]["dry_run"] is True

    preview = asyncio.run(preview_action("mock", "export_gerber", {"output_dir": "out"}))
    assert preview["success"] is True
    assert preview["preview"]["will_create_files"] == ["out"]


def test_existing_output_requires_confirmation(tmp_path) -> None:
    _configure()
    output_dir = tmp_path / "gerber"
    output_dir.mkdir()
    (output_dir / "old.gbr").write_text("old")

    pending = asyncio.run(
        run_action(
            "mock",
            "export_gerber",
            parameters={"output_dir": str(output_dir)},
        )
    )
    assert pending["status"] == ActionStatus.CONFIRMATION_REQUIRED.value
    assert pending["metadata"]["risk_level"] == "medium"

    preview = asyncio.run(
        preview_action(
            "mock",
            "export_gerber",
            {"output_dir": str(output_dir)},
        )
    )
    assert preview["preview"]["requires_confirmation"] is True


def test_unknown_action_result_is_structured() -> None:
    _configure()
    result = asyncio.run(run_action("missing", "mock_action"))
    assert result["success"] is False
    assert result["errors"][0]["error_code"] == "ERR_ADAPTER_NOT_FOUND"


def test_retryable_failure_uses_retry_policy(monkeypatch) -> None:
    adapter = MockAdapter(name="mock", mode="fail", actions=["mock_action"])
    original_execute = adapter.execute
    calls = 0

    def execute_with_recovery(action):
        nonlocal calls
        calls += 1
        if calls == 3:
            adapter._mode = "success"
        result = original_execute(action)
        if result.errors:
            result.errors[0].severity = ErrorSeverity.RETRYABLE
        return result

    adapter.execute = execute_with_recovery
    executor = ActionExecutor()
    executor.register_adapter(adapter)
    configure_runtime(executor)
    monkeypatch.setattr(mcp_tools, "sleep", lambda _seconds: None)

    result = asyncio.run(run_action("mock", "mock_action", retry_on_failure=True))
    assert result["success"] is True
    assert result["metadata"]["attempt_count"] == 3
