"""
KiCad Adapter — 通过 pcbnew Python API 和 kicad-cli 操作 KiCad EDA。

集成路径优先级（CLI/API > 宏 > 脚本 > GUI > 人工）:
  🥇 pcbnew Python API  — 需要内存中操作 board 对象时
  🥈 kicad-cli          — 单步导出/DRC/BOM，更稳定、适合 CI
  ❌ GUI 自动化          — 永不使用

支持的动作:
  open_project    — 加载 .kicad_pcb 文件（pcbnew）
  export_gerber   — 导出 Gerber 制造文件（kicad-cli）
  export_bom      — 导出 BOM（kicad-cli）
  run_drc         — 运行设计规则检查（kicad-cli --format json）
  collect_artifacts — 收集产物文件列表（文件系统）
  get_project_info — 读取工程元信息（pcbnew + 文件解析）

环境检测:
  - import pcbnew  → 主路径可用
  - shutil.which("kicad-cli") → CLI 可用
  - 二者都不可用 → available=False

参考: docs/research-kicad-cli.md
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
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


class KiCadAdapter(BaseAdapter):
    """KiCad EDA 适配器。

    自动检测 pcbnew 和 kicad-cli 的可用性。
    未安装 KiCad 时优雅降级（available=False + 友好的状态消息）。
    """

    def __init__(self):
        self._pcbnew_available = False
        self._cli_available = False
        self._version: Optional[str] = None
        self._status_message = ""
        self._detect()

    # ── BaseAdapter 接口 ────────────────────────────────────────

    @property
    def name(self) -> str:
        return "kicad"

    @property
    def version(self) -> str:
        return "0.1.0"

    @property
    def available_actions(self) -> list[str]:
        return [
            "open_project",
            "export_gerber",
            "export_bom",
            "run_drc",
            "collect_artifacts",
            "get_project_info",
        ]

    def check_availability(self) -> bool:
        return self._pcbnew_available or self._cli_available

    @property
    def status_message(self) -> str:
        return self._status_message

    def execute(self, action: Action) -> ActionResult:
        handlers = {
            "open_project": self._open_project,
            "export_gerber": self._export_gerber,
            "export_bom": self._export_bom,
            "run_drc": self._run_drc,
            "collect_artifacts": self._collect_artifacts,
            "get_project_info": self._get_project_info,
        }

        # 1. 先检查动作是否支持（无论 KiCad 是否可用）
        handler = handlers.get(action.action_name)
        if handler is None:
            return self._unsupported_action_result(action)

        # 2. collect_artifacts/get_project_info 不依赖 KiCad，绕过可用性检查
        _no_kicad_needed = {"collect_artifacts", "get_project_info"}
        if action.action_name not in _no_kicad_needed and not self.check_availability():
            return self._unavailable_result(action)

        try:
            return handler(action)
        except Exception as exc:
            return ActionResult(
                success=False,
                action_id=action.action_id,
                task_id=action.task_id,
                action_name=action.action_name,
                status=ActionStatus.FAILED,
                start_time=datetime.now(),
                end_time=datetime.now(),
                summary=f"KiCad 动作执行异常: {exc}",
                errors=[ErrorDetail(
                    error_code="ERR_KICAD_EXCEPTION",
                    severity=ErrorSeverity.FATAL,
                    message=str(exc),
                    recoverable=False,
                )],
            )

    def validate(self, result: ActionResult) -> ValidationReport:
        checks: list[CheckResult] = []

        # 检查产物文件存在
        for art in result.artifacts:
            exists = Path(art.path).exists()
            checks.append(CheckResult(
                check_name=f"file_exists:{art.path}",
                status=ValidationStatus.PASSED if exists else ValidationStatus.FAILED,
                message=f"{art.path} {'存在' if exists else '不存在'}",
                evidence=art.path,
            ))

        all_passed = all(c.status != ValidationStatus.FAILED for c in checks)
        return ValidationReport(
            action_id=result.action_id,
            passed=all_passed,
            checks=checks,
            failed_checks=[c for c in checks if c.status == ValidationStatus.FAILED],
        )

    # ── 环境检测 ────────────────────────────────────────────────

    def _detect(self):
        """检测 KiCad 安装状态"""
        issues = []

        # 检测 pcbnew
        try:
            import pcbnew
            self._pcbnew_available = True
            try:
                self._version = pcbnew.Version()
            except Exception:
                self._version = None
        except ImportError:
            issues.append("pcbnew 模块不可用（KiCad Python API 未安装或未在 PATH 中）")

        # 检测 kicad-cli
        if shutil.which("kicad-cli"):
            self._cli_available = True
            if not self._version:
                self._version = self._detect_cli_version()
        else:
            issues.append("kicad-cli 不在 PATH 中")

        if issues:
            self._status_message = "; ".join(issues)

    def _detect_cli_version(self) -> Optional[str]:
        try:
            result = subprocess.run(
                ["kicad-cli", "version", "--format", "plain"],
                capture_output=True, text=True, timeout=10,
            )
            return result.stdout.strip() if result.returncode == 0 else None
        except Exception:
            return None

    # ── 动作实现 ────────────────────────────────────────────────

    def _open_project(self, action: Action) -> ActionResult:
        """加载 PCB 工程（pcbnew API）"""
        project_path = action.parameters.get("project_path", "")
        if not project_path:
            return self._missing_param_result(action, "project_path")

        if not self._pcbnew_available:
            return ActionResult(
                success=False, action_id=action.action_id, task_id=action.task_id,
                action_name=action.action_name, status=ActionStatus.FAILED,
                start_time=datetime.now(), end_time=datetime.now(),
                summary="pcbnew API 不可用，无法加载工程",
                errors=[ErrorDetail(
                    error_code="ERR_PCBNEW_UNAVAILABLE",
                    severity=ErrorSeverity.FATAL,
                    message="pcbnew Python API 不可用。请确认 KiCad 已安装且 Python 可导入 pcbnew 模块。",
                    suggested_action="使用 kicad-cli 命令行路径操作，或安装 KiCad 并配置 PYTHONPATH",
                )],
            )

        try:
            import pcbnew
            board = pcbnew.LoadBoard(project_path)
            return ActionResult(
                success=True, action_id=action.action_id, task_id=action.task_id,
                action_name=action.action_name, status=ActionStatus.SUCCESS,
                start_time=datetime.now(), end_time=datetime.now(),
                summary=f"已加载工程: {project_path}",
                artifacts=[Artifact(path=project_path, description="KiCad PCB 文件")],
                metadata={
                    "footprint_count": len(list(board.GetFootprints())),
                    "net_count": board.GetNetCount(),
                },
            )
        except FileNotFoundError:
            return ActionResult(
                success=False, action_id=action.action_id, task_id=action.task_id,
                action_name=action.action_name, status=ActionStatus.FAILED,
                start_time=datetime.now(), end_time=datetime.now(),
                summary=f"工程文件不存在: {project_path}",
                errors=[ErrorDetail(
                    error_code="ERR_FILE_NOT_FOUND",
                    severity=ErrorSeverity.FATAL,
                    message=f"工程文件不存在: {project_path}",
                    recoverable=False,
                )],
            )

    def _export_gerber(self, action: Action) -> ActionResult:
        """导出 Gerber 文件（kicad-cli）"""
        project_path = action.parameters.get("project_path", "")
        output_dir = action.parameters.get("output_dir", "")
        layers = action.parameters.get("layers", "")

        if not project_path:
            return self._missing_param_result(action, "project_path")

        if not self._cli_available:
            return self._cli_unavailable_result(action)

        if not output_dir:
            output_dir = str(Path(project_path).parent / "gerber_output")
        os.makedirs(output_dir, exist_ok=True)

        cmd = ["kicad-cli", "pcb", "export", "gerbers", "-o", output_dir]
        if layers:
            cmd.extend(["--layers", layers])
        cmd.append(project_path)

        return self._run_cli(action, cmd, summary_prefix="Gerber 导出")

    def _export_bom(self, action: Action) -> ActionResult:
        """导出 BOM（kicad-cli sch export bom）"""
        schematic_path = action.parameters.get("schematic_path", "")
        output_file = action.parameters.get("output_file", "")

        if not schematic_path:
            return self._missing_param_result(action, "schematic_path")

        if not self._cli_available:
            return self._cli_unavailable_result(action)

        if not output_file:
            output_file = str(Path(schematic_path).with_suffix(".csv"))

        cmd = ["kicad-cli", "sch", "export", "bom", "-o", output_file, schematic_path]
        return self._run_cli(action, cmd, summary_prefix="BOM 导出",
                             artifacts=[Artifact(path=output_file, description="BOM CSV")])

    def _run_drc(self, action: Action) -> ActionResult:
        """运行 DRC（kicad-cli pcb drc --format json）"""
        project_path = action.parameters.get("project_path", "")
        output_file = action.parameters.get("output_file", "")

        if not project_path:
            return self._missing_param_result(action, "project_path")

        if not self._cli_available:
            return self._cli_unavailable_result(action)

        if not output_file:
            output_file = str(Path(project_path).with_suffix("")) + "_drc.json"

        cmd = [
            "kicad-cli", "pcb", "drc",
            "--format", "json",
            "--severity-all",
            "--exit-code-violations",
            "-o", output_file,
            project_path,
        ]
        return self._run_cli(action, cmd, summary_prefix="DRC 检查",
                             artifacts=[Artifact(path=output_file, description="DRC JSON 报告")])

    def _collect_artifacts(self, action: Action) -> ActionResult:
        """收集产物文件列表（文件系统遍历）"""
        output_dir = action.parameters.get("output_dir", ".")
        patterns = action.parameters.get("patterns", ["*.gbr", "*.drl", "*.csv", "*.json"])

        artifacts: list[Artifact] = []
        base = Path(output_dir)
        if base.exists():
            for pattern in patterns:
                for f in base.rglob(pattern):
                    stat = f.stat()
                    artifacts.append(Artifact(
                        path=str(f),
                        size_bytes=stat.st_size,
                        description=f.stem,
                    ))

        return ActionResult(
            success=True, action_id=action.action_id, task_id=action.task_id,
            action_name=action.action_name, status=ActionStatus.SUCCESS,
            start_time=datetime.now(), end_time=datetime.now(),
            summary=f"在 {output_dir} 找到 {len(artifacts)} 个产物文件",
            artifacts=artifacts,
        )

    def _get_project_info(self, action: Action) -> ActionResult:
        """读取工程元信息"""
        project_path = action.parameters.get("project_path", "")
        if not project_path:
            return self._missing_param_result(action, "project_path")

        info: dict = {"project_path": project_path}

        # 尝试 pcbnew
        if self._pcbnew_available:
            try:
                import pcbnew
                board = pcbnew.LoadBoard(project_path)
                info["footprint_count"] = len(list(board.GetFootprints()))
                info["net_count"] = board.GetNetCount()
            except Exception:
                info["pcbnew_error"] = "无法读取 PCB 文件"

        return ActionResult(
            success=True, action_id=action.action_id, task_id=action.task_id,
            action_name=action.action_name, status=ActionStatus.SUCCESS,
            start_time=datetime.now(), end_time=datetime.now(),
            summary=f"工程信息: {project_path}",
            metadata=info,
            artifacts=[Artifact(path=project_path, description="KiCad 工程")],
        )

    # ── 辅助方法 ────────────────────────────────────────────────

    def _run_cli(
        self,
        action: Action,
        cmd: list[str],
        summary_prefix: str = "",
        artifacts: Optional[list[Artifact]] = None,
    ) -> ActionResult:
        """执行 kicad-cli 命令并返回结构化结果"""
        start = datetime.now()
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=action.timeout_seconds,
            )
            end = datetime.now()
            duration_ms = int((end - start).total_seconds() * 1000)

            logs = [f"[CLI] {' '.join(cmd)}"]
            if result.stdout:
                logs.append(result.stdout.strip())

            if result.returncode == 0:
                return ActionResult(
                    success=True, action_id=action.action_id, task_id=action.task_id,
                    action_name=action.action_name, status=ActionStatus.SUCCESS,
                    start_time=start, end_time=end, duration_ms=duration_ms,
                    summary=f"{summary_prefix}完成（{duration_ms}ms）",
                    artifacts=artifacts or [],
                    logs=logs,
                    raw_output=result.stdout[:2000] if result.stdout else None,
                )
            elif result.returncode == 5 and action.action_name == "run_drc":
                # kicad-cli drc --exit-code-violations: exit code 5 = 有 DRC 违规
                return ActionResult(
                    success=True, action_id=action.action_id, task_id=action.task_id,
                    action_name=action.action_name, status=ActionStatus.SUCCESS,
                    start_time=start, end_time=end, duration_ms=duration_ms,
                    summary=f"{summary_prefix}完成——发现 DRC 违规（请查看报告）",
                    artifacts=artifacts or [],
                    warnings=["DRC 发现违规——请查看 JSON 报告了解详情"],
                    logs=logs,
                    raw_output=result.stdout[:2000] if result.stdout else None,
                )
            else:
                return ActionResult(
                    success=False, action_id=action.action_id, task_id=action.task_id,
                    action_name=action.action_name, status=ActionStatus.FAILED,
                    start_time=start, end_time=end, duration_ms=duration_ms,
                    summary=f"{summary_prefix}失败（退出码 {result.returncode}）",
                    errors=[ErrorDetail(
                        error_code="ERR_CLI_FAILED",
                        severity=ErrorSeverity.FATAL,
                        message=result.stderr.strip() or f"kicad-cli 退出码 {result.returncode}",
                        context={"exit_code": result.returncode, "stderr": result.stderr[:1000]},
                    )],
                    logs=logs,
                    raw_output=result.stderr[:2000] if result.stderr else None,
                )
        except subprocess.TimeoutExpired:
            return ActionResult(
                success=False, action_id=action.action_id, task_id=action.task_id,
                action_name=action.action_name, status=ActionStatus.FAILED,
                start_time=start, end_time=datetime.now(),
                summary=f"{summary_prefix}超时（>{action.timeout_seconds}s）",
                errors=[ErrorDetail(
                    error_code="ERR_TIMEOUT",
                    severity=ErrorSeverity.RETRYABLE,
                    message=f"kicad-cli 执行超时（>{action.timeout_seconds}s）",
                    recoverable=True,
                )],
            )

    def _missing_param_result(self, action: Action, param: str) -> ActionResult:
        return ActionResult(
            success=False, action_id=action.action_id, task_id=action.task_id,
            action_name=action.action_name, status=ActionStatus.FAILED,
            start_time=datetime.now(), end_time=datetime.now(),
            summary=f"缺少必要参数: {param}",
            errors=[ErrorDetail(
                error_code="ERR_MISSING_PARAM",
                severity=ErrorSeverity.FATAL,
                message=f"缺少必要参数 '{param}'",
                suggested_action=f"请在 parameters 中提供 '{param}'",
            )],
        )

    def _cli_unavailable_result(self, action: Action) -> ActionResult:
        return ActionResult(
            success=False, action_id=action.action_id, task_id=action.task_id,
            action_name=action.action_name, status=ActionStatus.FAILED,
            start_time=datetime.now(), end_time=datetime.now(),
            summary="kicad-cli 不可用",
            errors=[ErrorDetail(
                error_code="ERR_KICAD_CLI_UNAVAILABLE",
                severity=ErrorSeverity.FATAL,
                message="kicad-cli 不在 PATH 中。请安装 KiCad 8.x+。",
                suggested_action="安装 KiCad 或将 kicad-cli 所在目录加入 PATH",
            )],
        )

    def _unsupported_action_result(self, action: Action) -> ActionResult:
        return ActionResult(
            success=False, action_id=action.action_id, task_id=action.task_id,
            action_name=action.action_name, status=ActionStatus.FAILED,
            start_time=datetime.now(), end_time=datetime.now(),
            summary=f"不支持的动作: {action.action_name}",
            errors=[ErrorDetail(
                error_code="ERR_ACTION_NOT_SUPPORTED",
                severity=ErrorSeverity.FATAL,
                message=f"KiCad 适配器不支持动作 '{action.action_name}'。可用动作: {self.available_actions}",
            )],
        )

    def _unavailable_result(self, action: Action) -> ActionResult:
        return ActionResult(
            success=False, action_id=action.action_id, task_id=action.task_id,
            action_name=action.action_name, status=ActionStatus.FAILED,
            start_time=datetime.now(), end_time=datetime.now(),
            summary="KiCad 不可用",
            errors=[ErrorDetail(
                error_code="ERR_SOFTWARE_NOT_FOUND",
                severity=ErrorSeverity.FATAL,
                message=f"KiCad 未安装或不可用。{self._status_message}",
                suggested_action="安装 KiCad 8.x+ 并确保 pcbnew 或 kicad-cli 可用",
            )],
        )
