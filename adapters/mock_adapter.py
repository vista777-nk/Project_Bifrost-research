"""
Mock Adapter — 用于测试和开发阶段验证架构的模拟适配器。

不连接任何真实工业软件，可模拟三类动作结果：
- success: 返回成功结果 + 模拟产物
- fail: 返回失败结果 + 错误详情
- confirm: 返回 confirmation_required 状态

用途：Phase 1 集成测试、MCP Server 端到端测试、CI 环境。
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from adapters.base import BaseAdapter
from core.domain import (
    Action,
    ActionStatus,
    Artifact,
    ErrorDetail,
    ActionResult,
    ErrorSeverity,
    ValidationReport,
    ValidationStatus,
    CheckResult,
)


class MockAdapter(BaseAdapter):
    """可配置的模拟适配器。

    支持三种模式:
    - "success": 正常执行成功
    - "fail": 执行失败
    - "confirm": 需要用户确认

    用法:
        adapter = MockAdapter(name="kicad", mode="success")
        adapter = MockAdapter(name="kicad", mode="fail", error_code="ERR_TIMEOUT")
    """

    def __init__(
        self,
        name: str = "mock",
        version: str = "0.1.0",
        available: bool = True,
        mode: str = "success",  # "success" | "fail" | "confirm"
        actions: Optional[list[str]] = None,
        error_code: str = "ERR_MOCK_FAIL",
        error_message: str = "模拟失败",
    ):
        self._name = name
        self._version = version
        self._available = available
        self._mode = mode
        self._actions = actions or ["mock_action"]
        self._error_code = error_code
        self._error_message = error_message

    # ── BaseAdapter 接口 ────────────────────────────────────────

    @property
    def name(self) -> str:
        return self._name

    @property
    def version(self) -> str:
        return self._version

    @property
    def available_actions(self) -> list[str]:
        return list(self._actions)

    def check_availability(self) -> bool:
        return self._available

    def execute(self, action: Action) -> ActionResult:
        now = datetime.now()
        base = dict(
            action_id=action.action_id,
            task_id=action.task_id,
            action_name=action.action_name,
            start_time=now,
            end_time=now,
        )

        if self._mode == "confirm":
            return ActionResult(
                success=False,
                status=ActionStatus.CONFIRMATION_REQUIRED,
                warnings=["模拟确认需求——此操作需要用户确认"],
                errors=[ErrorDetail(
                    error_code="ERR_CONFIRMATION_REQUIRED",
                    severity=ErrorSeverity.NEEDS_HUMAN,
                    message=f"动作 '{action.action_name}' 需要显式确认（MockAdapter confirm 模式）",
                    suggested_action="调用 confirm_action 确认或取消此操作",
                    context={"app": self._name, "mode": "confirm"},
                    recoverable=True,
                )],
                **base,
            )

        if self._mode == "fail":
            return ActionResult(
                success=False,
                status=ActionStatus.FAILED,
                summary=f"模拟失败: {self._error_message}",
                errors=[ErrorDetail(
                    error_code=self._error_code,
                    severity=ErrorSeverity.FATAL,
                    message=self._error_message,
                    context={"app": self._name, "mode": "fail"},
                    recoverable=False,
                )],
                **base,
            )

        # success
        return ActionResult(
            success=True,
            status=ActionStatus.SUCCESS,
            summary=f"模拟成功: {action.action_name}",
            artifacts=[
                Artifact(
                    path=f"/mock/{self._name}/output/{action.action_name}.out",
                    size_bytes=1024,
                    description=f"Mock {self._name} 产物",
                )
            ],
            **base,
        )

    def validate(self, result: ActionResult) -> ValidationReport:
        checks = [
            CheckResult(
                check_name="mock_check",
                status=ValidationStatus.PASSED if result.success else ValidationStatus.FAILED,
                message="Mock 校验" if result.success else "Mock 校验未通过",
            )
        ]
        return ValidationReport(
            action_id=result.action_id,
            passed=result.success,
            checks=checks,
            failed_checks=[c for c in checks if c.status == ValidationStatus.FAILED],
        )
