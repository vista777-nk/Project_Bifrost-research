"""
Bifrost Core — 结构化错误体系

所有 Bifrost 错误都继承自 RelayError，携带：
- error_code: 机器可读错误码
- message: 人类可读描述
- severity: 错误严重程度（可自动重试 / 致命 / 需人工）
- suggested_action: 建议的下一步操作
- context: 出错时的上下文快照
- recoverable: 是否可恢复

参考: docs/02-data-models.md §3.3 ErrorDetail + docs/03-tools-design.md 错误场景表
"""

from __future__ import annotations

from core.domain import ErrorSeverity


class RelayError(Exception):
    """Bifrost 所有错误的基类。

    继承 Exception 以便在 try/except 中捕获，
    同时携带结构化字段以便日志和 Agent 做出智能响应。
    """

    def __init__(
        self,
        error_code: str,
        message: str,
        severity: ErrorSeverity = ErrorSeverity.FATAL,
        suggested_action: str = "",
        context: dict | None = None,
        recoverable: bool = False,
    ):
        self.error_code = error_code
        self.message = message
        self.severity = severity
        self.suggested_action = suggested_action
        self.context = context or {}
        self.recoverable = recoverable
        super().__init__(message)

    def __str__(self) -> str:
        return f"[{self.error_code}] {self.message}"


class ActionFailedError(RelayError):
    """动作执行失败（通用）。"""

    def __init__(
        self,
        action_id: str,
        action_name: str,
        message: str,
        severity: ErrorSeverity = ErrorSeverity.FATAL,
        suggested_action: str = "",
        context: dict | None = None,
    ):
        super().__init__(
            error_code="ERR_ACTION_FAILED",
            message=message,
            severity=severity,
            suggested_action=suggested_action,
            context=context,
        )
        self.action_id = action_id
        self.action_name = action_name


class ConfirmationRequiredError(RelayError):
    """需要用户确认才能继续的高风险操作。"""

    def __init__(
        self,
        action_id: str,
        message: str,
        context: dict | None = None,
    ):
        super().__init__(
            error_code="ERR_CONFIRMATION_REQUIRED",
            message=message,
            severity=ErrorSeverity.NEEDS_HUMAN,
            suggested_action="调用 confirm_action 确认或取消此操作",
            context=context,
            recoverable=True,
        )
        self.action_id = action_id


class AdapterNotFoundError(RelayError):
    """指定 app 没有可用的适配器。"""

    def __init__(self, app: str):
        super().__init__(
            error_code="ERR_ADAPTER_NOT_FOUND",
            message=(
                f"未找到 '{app}' 的可用适配器。"
                "请确认软件已安装，或先调用 list_adapters 查看可用适配器。"
            ),
            severity=ErrorSeverity.FATAL,
            suggested_action="调用 list_adapters 查看可用适配器列表",
            context={"app": app},
        )
        self.app = app


class TimeoutError(RelayError):
    """动作执行超时。"""

    def __init__(
        self,
        action_id: str,
        timeout_seconds: int = 300,
    ):
        super().__init__(
            error_code="ERR_TIMEOUT",
            message=f"动作 {action_id} 在 {timeout_seconds}s 内未完成。",
            severity=ErrorSeverity.RETRYABLE,
            suggested_action="可增大 timeout_seconds 后重试",
            context={"action_id": action_id, "timeout_seconds": timeout_seconds},
            recoverable=True,
        )
        self.action_id = action_id
        self.timeout_seconds = timeout_seconds


class ValidationFailedError(RelayError):
    """校验未通过。"""

    def __init__(
        self,
        action_id: str,
        message: str,
        failed_checks: list[str] | None = None,
    ):
        super().__init__(
            error_code="ERR_VALIDATION_FAILED",
            message=message,
            severity=ErrorSeverity.FATAL,
            suggested_action="检查失败项并修复后重新执行",
            context={"action_id": action_id, "failed_checks": failed_checks or []},
        )
        self.action_id = action_id
        self.failed_checks = failed_checks or []
