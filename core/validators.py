"""
Bifrost Core — 校验框架

提供可注册、可组合的校验规则系统，用于对 ActionResult 进行执行后校验。

核心概念：
- ValidationRule: 单个校验规则（名称 + 校验函数）
- ResultValidator: 规则注册器和校验执行器
- builtin_rules: 内置的通用校验规则（file_exists / non_empty_artifacts / no_errors）

参考: docs/02-data-models.md §3.4 ValidationReport
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from core.domain import ActionResult, CheckResult, ValidationReport, ValidationStatus

# ── 校验规则 ────────────────────────────────────────────────────


class ValidationRule:
    """单个校验规则。

    check_fn 签名: (ActionResult) -> CheckResult
    """

    def __init__(self, name: str, check_fn: Callable[[ActionResult], CheckResult]):
        self.name = name
        self.check_fn = check_fn

    def __repr__(self) -> str:
        return f"ValidationRule({self.name!r})"


# ── 校验器 ──────────────────────────────────────────────────────


class ResultValidator:
    """校验框架核心。

    用法:
        validator = ResultValidator()
        validator.register(ValidationRule(name="file_exists", check_fn=...))
        report = validator.validate(action_result)
        if not report.passed:
            print(report.failed_checks)
    """

    def __init__(self):
        self._rules: list[ValidationRule] = []

    def register(self, rule: ValidationRule) -> None:
        """注册一条校验规则"""
        self._rules.append(rule)

    def register_all(self, rules: list[ValidationRule]) -> None:
        """批量注册校验规则"""
        self._rules.extend(rules)

    def validate(
        self,
        result: ActionResult,
        recommendation: str = "",
    ) -> ValidationReport:
        """对 ActionResult 执行所有已注册的校验规则。

        Args:
            result: 待校验的动作结果
            recommendation: 校验失败时的综合建议（空字符串表示自动生成）

        Returns:
            ValidationReport: 包含所有校验项的结果
        """
        checks: list[CheckResult] = []
        failed: list[CheckResult] = []

        for rule in self._rules:
            try:
                check = rule.check_fn(result)
            except Exception as exc:
                # 校验规则本身异常 → 视为失败
                check = CheckResult(
                    check_name=rule.name,
                    status=ValidationStatus.FAILED,
                    message=f"校验规则执行异常: {exc}",
                )

            checks.append(check)
            if check.status == ValidationStatus.FAILED:
                failed.append(check)

        all_passed = len(failed) == 0
        if not recommendation and failed:
            recommendation = f"{len(failed)} 项校验未通过"

        return ValidationReport(
            action_id=result.action_id,
            passed=all_passed,
            checks=checks,
            failed_checks=failed,
            recommendation=recommendation,
        )


# ── 内置校验规则 ────────────────────────────────────────────────


def _check_file_exists(result: ActionResult) -> CheckResult:
    """检查产物文件是否在磁盘上存在"""
    if not result.artifacts:
        return CheckResult(
            check_name="file_exists",
            status=ValidationStatus.FAILED,
            message="无产物文件可供检查",
        )

    missing = []
    for art in result.artifacts:
        if not Path(art.path).exists():
            missing.append(art.path)

    if missing:
        return CheckResult(
            check_name="file_exists",
            status=ValidationStatus.FAILED,
            message=f"{len(missing)} 个产物文件不存在: {missing[:3]}...",
            evidence=str(missing),
        )
    return CheckResult(
        check_name="file_exists",
        status=ValidationStatus.PASSED,
        message=f"全部 {len(result.artifacts)} 个产物文件存在",
    )


def _check_non_empty_artifacts(result: ActionResult) -> CheckResult:
    """检查产物列表非空"""
    if not result.artifacts:
        return CheckResult(
            check_name="non_empty_artifacts",
            status=ValidationStatus.FAILED,
            message="产物列表为空——动作可能未产生任何输出",
        )
    return CheckResult(
        check_name="non_empty_artifacts",
        status=ValidationStatus.PASSED,
        message=f"产物列表含 {len(result.artifacts)} 个文件",
    )


def _check_no_errors(result: ActionResult) -> CheckResult:
    """检查动作结果无错误"""
    if result.errors:
        codes = [e.error_code for e in result.errors]
        return CheckResult(
            check_name="no_errors",
            status=ValidationStatus.FAILED,
            message=f"动作报告了 {len(result.errors)} 个错误: {codes}",
        )
    return CheckResult(
        check_name="no_errors",
        status=ValidationStatus.PASSED,
        message="无错误",
    )


# 内置规则字典（按名称访问）
builtin_rules: dict[str, ValidationRule] = {
    "file_exists": ValidationRule(name="file_exists", check_fn=_check_file_exists),
    "non_empty_artifacts": ValidationRule(
        name="non_empty_artifacts", check_fn=_check_non_empty_artifacts
    ),
    "no_errors": ValidationRule(name="no_errors", check_fn=_check_no_errors),
}
