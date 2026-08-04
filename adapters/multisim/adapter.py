"""
Multisim Adapter — 通过 COM Automation API 操作 NI Multisim。

集成路径优先级:
  🥇 COM Automation API (pywin32) — 完整电路操作、仿真控制、数据采集
  🥈 命令行 netlist 仿真         — 批处理，能力有限
  ❌ .ms14 直接解析              — 专有二进制格式，不可行

支持的动作:
  read_circuit     — 打开设计文件，读取电路信息
  export_netlist   — 导出 SPICE 网表
  run_simulation   — 运行仿真（瞬态/AC/DC）
  get_output_data  — 采集输出数据
  list_components  — 枚举元件

限制:
  - 仅 Windows（COM Automation API）
  - 若 Multisim COM 组件为 32-bit，需 32-bit Python
  - COM 接口无官方完整文档

参考: docs/research-actual-software-stack.md §6
可借鉴: github.com/Last-emo-boy/Multisim-MCP
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from adapters.base import BaseAdapter
from core.domain import (
    Action,
    ActionStatus,
    Artifact,
    ErrorDetail,
    ActionResult,
    ErrorSeverity,
    CheckResult,
    ValidationReport,
    ValidationStatus,
)


class MultisimAdapter(BaseAdapter):
    """NI Multisim 适配器。

    通过 COM Automation API 控制 Multisim。
    在无 Multisim 环境（非 Windows / 未安装）时优雅降级。
    """

    def __init__(self):
        self._com_available = False
        self._status_message = ""
        self._app = None  # COM Application 对象（延迟连接）
        self._detect()

    # ── BaseAdapter 接口 ────────────────────────────────────────

    @property
    def name(self) -> str:
        return "multisim"

    @property
    def version(self) -> str:
        return "0.1.0"

    @property
    def available_actions(self) -> list[str]:
        return [
            "read_circuit",
            "export_netlist",
            "run_simulation",
            "get_output_data",
            "list_components",
        ]

    def check_availability(self) -> bool:
        return self._com_available

    @property
    def status_message(self) -> str:
        return self._status_message

    def execute(self, action: Action) -> ActionResult:
        if not self.check_availability():
            return self._unavailable_result(action)

        handlers = {
            "read_circuit": self._read_circuit,
            "export_netlist": self._export_netlist,
            "run_simulation": self._run_simulation,
            "get_output_data": self._get_output_data,
            "list_components": self._list_components,
        }

        handler = handlers.get(action.action_name)
        if handler is None:
            return ActionResult(
                success=False, action_id=action.action_id, task_id=action.task_id,
                action_name=action.action_name, status=ActionStatus.FAILED,
                start_time=datetime.now(), end_time=datetime.now(),
                summary=f"不支持的动作: {action.action_name}",
                errors=[ErrorDetail(
                    error_code="ERR_ACTION_NOT_SUPPORTED",
                    severity=ErrorSeverity.FATAL,
                    message=f"Multisim 适配器不支持 '{action.action_name}'。可用: {self.available_actions}",
                )],
            )

        try:
            return handler(action)
        except Exception as exc:
            return ActionResult(
                success=False, action_id=action.action_id, task_id=action.task_id,
                action_name=action.action_name, status=ActionStatus.FAILED,
                start_time=datetime.now(), end_time=datetime.now(),
                summary=f"Multisim 执行异常: {exc}",
                errors=[ErrorDetail(
                    error_code="ERR_MULTISIM_EXCEPTION",
                    severity=ErrorSeverity.FATAL,
                    message=str(exc),
                    recoverable=False,
                )],
            )

    def validate(self, result: ActionResult) -> ValidationReport:
        checks = [
            CheckResult(
                check_name="simulation_output",
                status=ValidationStatus.PASSED if result.success else ValidationStatus.FAILED,
                message="仿真成功" if result.success else "仿真失败",
            )
        ]
        return ValidationReport(
            action_id=result.action_id,
            passed=result.success,
            checks=checks,
            failed_checks=[c for c in checks if c.status == ValidationStatus.FAILED],
        )

    # ── 环境检测 ────────────────────────────────────────────────

    def _detect(self):
        """检测 Multisim COM Automation API 可用性"""
        if sys.platform != "win32":
            self._status_message = "Multisim COM Automation 仅支持 Windows"
            return

        try:
            import win32com.client
            app = win32com.client.Dispatch("Multisim.Application")
            self._com_available = True
            self._app = app
        except ImportError:
            self._status_message = "pywin32 未安装。请运行: pip install pywin32"
        except Exception as exc:
            self._status_message = f"Multisim COM 组件不可用: {exc}"

    # ── 动作实现（骨架——COM 细节待 Phase 1 后续对接真实 Multisim 验证） ─

    def _read_circuit(self, action: Action) -> ActionResult:
        file_path = action.parameters.get("file_path", "")
        if not file_path:
            return ActionResult(
                success=False, action_id=action.action_id, task_id=action.task_id,
                action_name=action.action_name, status=ActionStatus.FAILED,
                start_time=datetime.now(), end_time=datetime.now(),
                summary="缺少 file_path 参数",
                errors=[ErrorDetail(error_code="ERR_MISSING_PARAM", severity=ErrorSeverity.FATAL,
                                    message="缺少必要参数 'file_path'")],
            )

        if not Path(file_path).exists():
            return ActionResult(
                success=False, action_id=action.action_id, task_id=action.task_id,
                action_name=action.action_name, status=ActionStatus.FAILED,
                start_time=datetime.now(), end_time=datetime.now(),
                summary=f"文件不存在: {file_path}",
                errors=[ErrorDetail(error_code="ERR_FILE_NOT_FOUND", severity=ErrorSeverity.FATAL,
                                    message=f"设计文件不存在: {file_path}")],
            )

        # TODO: 通过 COM API 打开设计并读取电路信息
        # 当前为骨架——返回成功但标注为骨架实现
        return ActionResult(
            success=True, action_id=action.action_id, task_id=action.task_id,
            action_name=action.action_name, status=ActionStatus.SUCCESS,
            start_time=datetime.now(), end_time=datetime.now(),
            summary=f"已读取电路: {file_path}（骨架——COM 细节待真实 Multisim 验证）",
            artifacts=[Artifact(path=file_path, description="Multisim 设计文件")],
            warnings=["Multisim COM 集成细节待真实软件环境验证"],
        )

    def _export_netlist(self, action: Action) -> ActionResult:
        file_path = action.parameters.get("file_path", "")
        output_file = action.parameters.get("output_file", "")

        if not file_path:
            return self._missing_param_result(action, "file_path")

        if not output_file:
            output_file = str(Path(file_path).with_suffix(".cir"))

        # TODO: COM API 导出网表
        return ActionResult(
            success=True, action_id=action.action_id, task_id=action.task_id,
            action_name=action.action_name, status=ActionStatus.SUCCESS,
            start_time=datetime.now(), end_time=datetime.now(),
            summary=f"网表已导出到: {output_file}（骨架）",
            artifacts=[Artifact(path=output_file, description="SPICE 网表")],
            warnings=["COM 导出细节待真实 Multisim 验证"],
        )

    def _run_simulation(self, action: Action) -> ActionResult:
        analysis_type = action.parameters.get("analysis_type", "transient")
        output_names = action.parameters.get("output_names", [])
        stop_time = action.parameters.get("stop_time", 0.01)

        # TODO: COM API 运行仿真
        return ActionResult(
            success=True, action_id=action.action_id, task_id=action.task_id,
            action_name=action.action_name, status=ActionStatus.SUCCESS,
            start_time=datetime.now(), end_time=datetime.now(),
            summary=f"{analysis_type} 仿真完成（骨架）",
            metadata={"analysis_type": analysis_type, "output_names": output_names},
            warnings=["COM 仿真细节待真实 Multisim 验证"],
        )

    def _get_output_data(self, action: Action) -> ActionResult:
        output_name = action.parameters.get("output_name", "")
        return ActionResult(
            success=True, action_id=action.action_id, task_id=action.task_id,
            action_name=action.action_name, status=ActionStatus.SUCCESS,
            start_time=datetime.now(), end_time=datetime.now(),
            summary=f"输出数据: {output_name}（骨架）",
            warnings=["COM 数据采集细节待真实 Multisim 验证"],
        )

    def _list_components(self, action: Action) -> ActionResult:
        # TODO: COM API 枚举元件
        return ActionResult(
            success=True, action_id=action.action_id, task_id=action.task_id,
            action_name=action.action_name, status=ActionStatus.SUCCESS,
            start_time=datetime.now(), end_time=datetime.now(),
            summary="元件列表（骨架——待真实 Multisim 验证）",
            artifacts=[],
            warnings=["COM 枚举细节待真实 Multisim 验证"],
        )

    # ── 辅助方法 ────────────────────────────────────────────────

    def _missing_param_result(self, action: Action, param: str) -> ActionResult:
        return ActionResult(
            success=False, action_id=action.action_id, task_id=action.task_id,
            action_name=action.action_name, status=ActionStatus.FAILED,
            start_time=datetime.now(), end_time=datetime.now(),
            summary=f"缺少必要参数: {param}",
            errors=[ErrorDetail(error_code="ERR_MISSING_PARAM", severity=ErrorSeverity.FATAL,
                                message=f"缺少 '{param}'", suggested_action=f"请提供 '{param}'")],
        )

    def _unavailable_result(self, action: Action) -> ActionResult:
        return ActionResult(
            success=False, action_id=action.action_id, task_id=action.task_id,
            action_name=action.action_name, status=ActionStatus.FAILED,
            start_time=datetime.now(), end_time=datetime.now(),
            summary="Multisim 不可用",
            errors=[ErrorDetail(error_code="ERR_SOFTWARE_NOT_FOUND", severity=ErrorSeverity.FATAL,
                                message=f"Multisim 不可用。{self._status_message}",
                                suggested_action="在 Windows 上安装 NI Multisim 14.x 和 pywin32")],
        )
