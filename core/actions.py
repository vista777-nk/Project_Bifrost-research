"""
Bifrost Core — 动作执行引擎

ActionExecutor 是 Core 层的核心调度器：
- 注册/管理多个软件适配器
- 查找适配器、执行动作
- 处理确认流程和重试逻辑
- 列出可用适配器（给 list_adapters 工具用）

参考: docs/01-architecture.md §2.1, docs/03-tools-design.md §2 (run_action)
"""

from __future__ import annotations

import uuid
from datetime import datetime

from adapters.base import BaseAdapter
from core.domain import (
    Action,
    ActionResult,
    ActionStatus,
    AdapterInfo,
    ErrorDetail,
    ErrorSeverity,
)
from core.errors import AdapterNotFoundError


class ActionExecutor:
    """动作执行引擎。

    持有所有已注册的适配器，负责任务的调度执行。

    用法:
        executor = ActionExecutor()
        executor.register_adapter(KiCadAdapter())
        result = executor.run_action(app="kicad", action_name="export_gerber", ...)
    """

    def __init__(self):
        self._adapters: dict[str, BaseAdapter] = {}

    # ── 适配器管理 ──────────────────────────────────────────────

    def register_adapter(self, adapter: BaseAdapter) -> None:
        """注册一个适配器（按 name 索引）"""
        self._adapters[adapter.name] = adapter

    def _get_adapter(self, app: str) -> BaseAdapter:
        """查找适配器，未找到抛出 AdapterNotFoundError"""
        adapter = self._adapters.get(app)
        if adapter is None:
            raise AdapterNotFoundError(app=app)
        return adapter

    # ── 适配器列表 ──────────────────────────────────────────────

    def list_adapters(self, filter: str = "") -> list[AdapterInfo]:
        """列出可用适配器。

        Args:
            filter: 按名称过滤（空字符串=全部）

        Returns:
            list[AdapterInfo]: 适配器信息列表
        """
        result = []
        for name, adapter in self._adapters.items():
            if filter and name != filter:
                continue
            available = adapter.check_availability()
            result.append(AdapterInfo(
                name=adapter.name,
                display_name=self._display_name_for(adapter.name),
                version=adapter.version,
                software_version=getattr(adapter, "software_version", None),
                available=available,
                available_actions=adapter.available_actions,
                priority_path=self._priority_path_for(adapter.name),
                status_message=(
                    ""
                    if available
                    else getattr(
                        adapter,
                        "status_message",
                        f"{self._display_name_for(adapter.name)} 不可用",
                    )
                ),
            ))
        return result

    # ── 动作执行 ────────────────────────────────────────────────

    def execute(self, action: Action) -> ActionResult:
        """执行一个 Action（完整流程：查找适配器 → 执行 → 返回结果）。

        不会自动重试——重试逻辑由上层（Skill/MCP tool）根据 retry_policy 决定。
        """
        try:
            adapter = self._get_adapter(action.app)
        except AdapterNotFoundError as exc:
            return ActionResult(
                success=False,
                action_id=action.action_id,
                task_id=action.task_id,
                action_name=action.action_name,
                status=ActionStatus.FAILED,
                start_time=datetime.now(),
                end_time=datetime.now(),
                errors=[ErrorDetail(
                    error_code="ERR_ADAPTER_NOT_FOUND",
                    severity=ErrorSeverity.FATAL,
                    message=str(exc),
                    suggested_action=exc.suggested_action,
                    context=exc.context,
                    recoverable=False,
                )],
            )

        if not adapter.can_execute(action):
            return ActionResult(
                success=False,
                action_id=action.action_id,
                task_id=action.task_id,
                action_name=action.action_name,
                status=ActionStatus.FAILED,
                start_time=datetime.now(),
                end_time=datetime.now(),
                errors=[ErrorDetail(
                    error_code="ERR_ADAPTER_UNAVAILABLE",
                    severity=ErrorSeverity.FATAL,
                    message=f"适配器 '{action.app}' 当前不可用（软件未安装或许可过期）",
                    suggested_action=f"请安装 {self._display_name_for(action.app)} 后重试",
                    context={"app": action.app},
                    recoverable=False,
                )],
            )

        # 委托给适配器执行
        return adapter.execute(action)

    def run_action(
        self,
        app: str,
        action_name: str,
        parameters: dict | None = None,
        mode: str = "normal",
        task_id: str = "",
        timeout_seconds: int = 300,
    ) -> ActionResult:
        """便捷方法：构造 Action 并执行。

        Args:
            app: 目标软件
            action_name: 动作名称
            parameters: 动作参数
            mode: 执行模式 (dry_run | normal | force)
            task_id: 关联的 Task ID（不提供则自动生成）
            timeout_seconds: 超时秒数

        Returns:
            ActionResult

        Raises:
            AdapterNotFoundError: 当指定 app 没有注册适配器时
        """
        if not task_id:
            task_id = f"task-{uuid.uuid4().hex[:8]}"

        # 先检查适配器是否存在（run_action 层面直接 raise，不通过 execute 捕获）
        self._get_adapter(app)

        action = Action(
            action_id=f"act-{uuid.uuid4().hex[:8]}",
            task_id=task_id,
            action_name=action_name,
            action_type=self._infer_action_type(action_name),
            app=app,
            parameters=parameters or {},
            timeout_seconds=timeout_seconds,
        )
        return self.execute(action)

    # ── 辅助方法 ────────────────────────────────────────────────

    @staticmethod
    def _infer_action_type(action_name: str) -> str:
        """根据动作名称推断类型"""
        _read_kw = ("export", "collect", "get", "list", "read", "identify", "inspect", "find")
        if any(kw in action_name for kw in _read_kw):
            return "read"
        _write_kw = ("flash", "erase", "write", "burn", "save", "modify", "replace", "create", "edit")
        if any(kw in action_name for kw in _write_kw):
            return "write"
        _exec_kw = ("build", "compile", "simulate", "run", "execute", "open")
        if any(kw in action_name for kw in _exec_kw):
            return "execute"
        if "validate" in action_name or "verify" in action_name or "check" in action_name:
            return "validate"
        return "execute"

    @staticmethod
    def _display_name_for(name: str) -> str:
        """适配器名 → 显示名称"""
        _display_names = {
            "kicad": "KiCad EDA",
            "keil": "Keil MDK",
            "stm32cubeide": "STM32CubeIDE",
            "ccs": "Code Composer Studio",
            "autocad": "AutoCAD",
            "multisim": "NI Multisim",
            "solidworks": "SolidWorks",
        }
        return _display_names.get(name, name)

    @staticmethod
    def _priority_path_for(name: str) -> str:
        """适配器名 → 主集成路径"""
        _paths = {
            "kicad": "pcbnew_api",
            "keil": "cli",
            "stm32cubeide": "cli",
            "ccs": "cli+dss",
            "autocad": "accoreconsole+com",
            "multisim": "com",
            "solidworks": "com",
        }
        return _paths.get(name, "unknown")

    def get_adapter(self, app: str) -> BaseAdapter:
        """Return a registered adapter for relay integrations."""

        return self._get_adapter(app)
