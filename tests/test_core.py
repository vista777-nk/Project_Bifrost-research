"""
Phase 1 Step 2a — Core 层单元测试（TDD: 先写测试，后写实现）

测试覆盖：
- 枚举: ActionStatus / ErrorSeverity / ValidationStatus / ExecutionMode
- 数据模型: Task / RetryPolicy / Action / Artifact / ErrorDetail / ActionResult / CheckResult / ValidationReport / AdapterInfo
- pydantic 行为: extra="forbid" / 序列化 / 默认值 / 约束 / Optional 字段

参考: docs/02-data-models.md
"""

import json
from datetime import datetime

import pytest

from core.actions import ActionExecutor

# ── 导入被测模块（TDD: 此时 domain.py 尚不存在，测试先写）────────
# 为保持 TDD 纯粹性，以下 import 在 core/domain.py 实现前会失败——
# 这正是"红→绿→重构"循环中期待的"红灯"阶段。
# 请在实现 core/domain.py 后运行此测试。
from core.domain import (
    Action,
    ActionResult,
    ActionStatus,
    AdapterInfo,
    Artifact,
    CheckResult,
    ErrorDetail,
    ErrorSeverity,
    ExecutionMode,
    RetryPolicy,
    Task,
    ValidationReport,
    ValidationStatus,
)
from core.errors import (
    ActionFailedError,
    AdapterNotFoundError,
    ConfirmationRequiredError,
    RelayError,
    TimeoutError,
    ValidationFailedError,
)
from core.validators import (
    ResultValidator,
    ValidationRule,
    builtin_rules,
)
from core.workflows import Step, Workflow, run_workflow

# ═══════════════════════════════════════════════════════════════
# 1. 枚举测试
# ═══════════════════════════════════════════════════════════════

class TestActionStatus:
    """ActionStatus 枚举"""

    def test_all_members_exist(self):
        expected = {"pending", "running", "success", "failed", "confirmation_required", "cancelled"}
        actual = {m.value for m in ActionStatus}
        assert actual == expected

    def test_is_string_enum(self):
        assert ActionStatus.PENDING == "pending"
        assert ActionStatus.SUCCESS == "success"
        assert isinstance(ActionStatus.PENDING.value, str)


class TestErrorSeverity:
    """ErrorSeverity 枚举"""

    def test_all_members_exist(self):
        expected = {"retryable", "fatal", "needs_human"}
        actual = {m.value for m in ErrorSeverity}
        assert actual == expected


class TestValidationStatus:
    """ValidationStatus 枚举"""

    def test_all_members_exist(self):
        expected = {"passed", "failed", "warning", "skipped"}
        actual = {m.value for m in ValidationStatus}
        assert actual == expected


class TestExecutionMode:
    """ExecutionMode 枚举"""

    def test_all_members_exist(self):
        expected = {"dry_run", "normal", "force"}
        actual = {m.value for m in ExecutionMode}
        assert actual == expected


# ═══════════════════════════════════════════════════════════════
# 2. Task 数据模型
# ═══════════════════════════════════════════════════════════════

class TestTask:
    """Task — 用户或 Agent 提出的工程目标"""

    def test_create_minimal(self):
        """最简字段创建"""
        task = Task(
            task_id="task-001",
            title="导出 KiCad Gerber",
            target_app="kicad",
            goal="导出工程 Gerber 并检查 DRC",
        )
        assert task.task_id == "task-001"
        assert task.title == "导出 KiCad Gerber"
        assert task.target_app == "kicad"
        assert task.goal == "导出工程 Gerber 并检查 DRC"
        # 默认值
        assert task.priority == 5
        assert task.mode == ExecutionMode.NORMAL
        assert task.inputs == {}
        assert task.constraints == []
        assert task.requires_confirmation is False
        assert task.expected_outputs == []
        assert isinstance(task.created_at, datetime)
        assert task.metadata == {}

    def test_create_full(self):
        """所有字段显式赋值"""
        now = datetime(2026, 8, 5, 12, 0, 0)
        task = Task(
            task_id="task-full",
            title="完整任务",
            target_app="kicad",
            goal="测试全字段",
            priority=1,
            mode=ExecutionMode.DRY_RUN,
            inputs={"project_path": "/tmp/test.kicad_pro"},
            constraints=["只读模式"],
            requires_confirmation=True,
            expected_outputs=["output/gerber/"],
            created_at=now,
            metadata={"author": "test"},
        )
        assert task.priority == 1
        assert task.mode == ExecutionMode.DRY_RUN
        assert task.inputs["project_path"] == "/tmp/test.kicad_pro"
        assert task.constraints == ["只读模式"]
        assert task.requires_confirmation is True
        assert task.expected_outputs == ["output/gerber/"]
        assert task.created_at == now

    def test_priority_constraints(self):
        """priority 必须在 1-10 之间"""
        Task(task_id="t", title="t", target_app="kicad", goal="g", priority=1)
        Task(task_id="t", title="t", target_app="kicad", goal="g", priority=10)

        with pytest.raises(Exception):  # pydantic ValidationError
            Task(task_id="t", title="t", target_app="kicad", goal="g", priority=0)

        with pytest.raises(Exception):
            Task(task_id="t", title="t", target_app="kicad", goal="g", priority=11)

    def test_extra_fields_forbidden(self):
        """extra='forbid' — 不允许未定义字段"""
        with pytest.raises(Exception):
            Task(
                task_id="t",
                title="t",
                target_app="kicad",
                goal="g",
                unknown_field="should_fail",
            )

    def test_serialization(self):
        """model_dump 输出正确 JSON 兼容字典"""
        task = Task(
            task_id="task-ser",
            title="序列化测试",
            target_app="kicad",
            goal="测试序列化",
            priority=3,
            mode=ExecutionMode.NORMAL,
        )
        d = task.model_dump()
        assert d["task_id"] == "task-ser"
        assert d["title"] == "序列化测试"
        assert d["target_app"] == "kicad"
        assert d["priority"] == 3
        assert d["mode"] == "normal"
        assert "created_at" in d

    def test_json_roundtrip(self):
        """JSON 序列化→反序列化往返"""
        task = Task(
            task_id="task-json",
            title="JSON 测试",
            target_app="multisim",
            goal="测试 JSON 往返",
        )
        json_str = task.model_dump_json()
        data = json.loads(json_str)
        task2 = Task(**data)
        assert task2.task_id == task.task_id
        assert task2.title == task.title


# ═══════════════════════════════════════════════════════════════
# 3. RetryPolicy 数据模型
# ═══════════════════════════════════════════════════════════════

class TestRetryPolicy:
    """RetryPolicy — 重试策略"""

    def test_defaults(self):
        rp = RetryPolicy()
        assert rp.max_retries == 3
        assert rp.delay_seconds == 5
        assert rp.backoff_multiplier == 2.0
        assert rp.retry_on == [ErrorSeverity.RETRYABLE]

    def test_custom(self):
        rp = RetryPolicy(
            max_retries=5,
            delay_seconds=10,
            backoff_multiplier=1.5,
            retry_on=[ErrorSeverity.RETRYABLE, ErrorSeverity.NEEDS_HUMAN],
        )
        assert rp.max_retries == 5
        assert rp.delay_seconds == 10
        assert rp.backoff_multiplier == 1.5
        assert len(rp.retry_on) == 2

    def test_constraints(self):
        """约束: max_retries 0-10, delay 1-300, multiplier 1.0-10.0"""
        with pytest.raises(Exception):
            RetryPolicy(max_retries=11)
        with pytest.raises(Exception):
            RetryPolicy(max_retries=-1)
        with pytest.raises(Exception):
            RetryPolicy(delay_seconds=0)
        with pytest.raises(Exception):
            RetryPolicy(delay_seconds=301)
        with pytest.raises(Exception):
            RetryPolicy(backoff_multiplier=0.5)


# ═══════════════════════════════════════════════════════════════
# 4. Action 数据模型
# ═══════════════════════════════════════════════════════════════

class TestAction:
    """Action — 最小可执行单元"""

    def test_create_minimal(self):
        action = Action(
            action_id="act-001",
            task_id="task-001",
            action_name="export_gerber",
            action_type="execute",
            app="kicad",
        )
        assert action.action_id == "act-001"
        assert action.task_id == "task-001"
        assert action.action_name == "export_gerber"
        assert action.action_type == "execute"
        assert action.app == "kicad"
        # 默认值
        assert action.adapter == ""
        assert action.parameters == {}
        assert action.precheck is None
        assert action.postcheck is None
        assert isinstance(action.retry_policy, RetryPolicy)
        assert action.requires_confirmation is False
        assert action.timeout_seconds == 300
        assert action.tags == []

    def test_create_with_params(self):
        action = Action(
            action_id="act-002",
            task_id="task-002",
            action_name="flash_firmware",
            action_type="write",
            app="stm32cubeide",
            parameters={"firmware_path": "/tmp/fw.bin", "device": "STM32F407"},
            requires_confirmation=True,
            timeout_seconds=600,
            tags=["flash", "hardware"],
        )
        assert action.parameters["firmware_path"] == "/tmp/fw.bin"
        assert action.requires_confirmation is True
        assert action.timeout_seconds == 600
        assert "flash" in action.tags

    def test_timeout_constraints(self):
        """timeout 1-3600 秒"""
        Action(action_id="a", task_id="t", action_name="n", action_type="t", app="app", timeout_seconds=1)
        with pytest.raises(Exception):
            Action(action_id="a", task_id="t", action_name="n", action_type="t", app="app", timeout_seconds=0)
        with pytest.raises(Exception):
            Action(action_id="a", task_id="t", action_name="n", action_type="t", app="app", timeout_seconds=3601)

    def test_extra_fields_forbidden(self):
        with pytest.raises(Exception):
            Action(
                action_id="a", task_id="t", action_name="n", action_type="t", app="app",
                garbage="no",
            )


# ═══════════════════════════════════════════════════════════════
# 5. Artifact 数据模型
# ═══════════════════════════════════════════════════════════════

class TestArtifact:
    """Artifact — 产物文件描述"""

    def test_create_minimal(self):
        art = Artifact(path="/tmp/output/test.gbr")
        assert art.path == "/tmp/output/test.gbr"
        assert art.size_bytes == 0
        assert art.checksum is None
        assert art.mime_type is None
        assert art.description == ""

    def test_create_full(self):
        art = Artifact(
            path="/tmp/output/test.gbr",
            size_bytes=245760,
            checksum="sha256:abc123def456",
            mime_type="application/x-gerber",
            description="顶层铜箔 Gerber",
        )
        assert art.size_bytes == 245760
        assert art.checksum == "sha256:abc123def456"
        assert art.mime_type == "application/x-gerber"
        assert art.description == "顶层铜箔 Gerber"


# ═══════════════════════════════════════════════════════════════
# 6. ErrorDetail 数据模型
# ═══════════════════════════════════════════════════════════════

class TestErrorDetail:
    """ErrorDetail — 结构化错误信息"""

    def test_create_minimal(self):
        err = ErrorDetail(
            error_code="ERR_TIMEOUT",
            severity=ErrorSeverity.RETRYABLE,
            message="操作超时",
        )
        assert err.error_code == "ERR_TIMEOUT"
        assert err.severity == ErrorSeverity.RETRYABLE
        assert err.message == "操作超时"
        assert err.suggested_action == ""
        assert err.context == {}
        assert err.recoverable is False

    def test_create_full(self):
        err = ErrorDetail(
            error_code="ERR_CONFIRMATION_REQUIRED",
            severity=ErrorSeverity.NEEDS_HUMAN,
            message="烧录固件需要确认",
            suggested_action="调用 confirm_action 确认",
            context={"device": "STM32F407", "firmware": "build/fw.bin"},
            recoverable=True,
        )
        assert err.severity == ErrorSeverity.NEEDS_HUMAN
        assert err.suggested_action == "调用 confirm_action 确认"
        assert err.context["device"] == "STM32F407"
        assert err.recoverable is True


# ═══════════════════════════════════════════════════════════════
# 7. ActionResult 数据模型
# ═══════════════════════════════════════════════════════════════

class TestActionResult:
    """ActionResult — 动作执行的结构化返回"""

    def _make_basic_result(self, **overrides) -> ActionResult:
        now = datetime(2026, 8, 5, 12, 0, 0)
        defaults = dict(
            success=True,
            action_id="act-001",
            task_id="task-001",
            action_name="export_gerber",
            status=ActionStatus.SUCCESS,
            start_time=now,
            end_time=now,
        )
        defaults.update(overrides)
        return ActionResult(**defaults)

    def test_create_success(self):
        result = self._make_basic_result()
        assert result.success is True
        assert result.status == ActionStatus.SUCCESS
        assert result.duration_ms == 0
        assert result.summary == ""
        assert result.artifacts == []
        assert result.warnings == []
        assert result.errors == []
        assert result.logs == []
        assert result.validation is None
        assert result.next_suggestion == ""
        assert result.raw_output is None
        assert result.metadata == {}

    def test_create_with_artifacts(self):
        art = Artifact(path="/tmp/test.gbr", size_bytes=100)
        result = self._make_basic_result(
            summary="成功导出 1 个 Gerber 文件",
            artifacts=[art],
            duration_ms=5000,
        )
        assert len(result.artifacts) == 1
        assert result.artifacts[0].path == "/tmp/test.gbr"
        assert result.summary == "成功导出 1 个 Gerber 文件"
        assert result.duration_ms == 5000

    def test_create_failed(self):
        err = ErrorDetail(
            error_code="ERR_FILE_NOT_FOUND",
            severity=ErrorSeverity.FATAL,
            message="文件不存在",
        )
        result = self._make_basic_result(
            success=False,
            status=ActionStatus.FAILED,
            errors=[err],
            logs=["[12:00:00] 尝试打开文件", "[12:00:01] 文件不存在"],
            next_suggestion="检查路径后重试",
        )
        assert result.success is False
        assert result.status == ActionStatus.FAILED
        assert len(result.errors) == 1
        assert result.errors[0].error_code == "ERR_FILE_NOT_FOUND"
        assert len(result.logs) == 2

    def test_create_confirmation_required(self):
        err = ErrorDetail(
            error_code="ERR_CONFIRMATION_REQUIRED",
            severity=ErrorSeverity.NEEDS_HUMAN,
            message="需要用户确认",
            recoverable=True,
        )
        result = self._make_basic_result(
            success=False,
            status=ActionStatus.CONFIRMATION_REQUIRED,
            errors=[err],
            warnings=["即将擦除 Flash"],
        )
        assert result.status == ActionStatus.CONFIRMATION_REQUIRED
        assert len(result.warnings) == 1
        assert result.errors[0].recoverable is True

    def test_validation_nested(self):
        """ActionResult 内嵌 ValidationReport"""
        check = CheckResult(check_name="file_exists", status=ValidationStatus.PASSED, message="ok")
        report = ValidationReport(action_id="act-001", passed=True, checks=[check])
        result = self._make_basic_result(validation=report)
        assert result.validation is not None
        assert result.validation.passed is True
        assert len(result.validation.checks) == 1


# ═══════════════════════════════════════════════════════════════
# 8. CheckResult 数据模型
# ═══════════════════════════════════════════════════════════════

class TestCheckResult:
    """CheckResult — 单个校验项"""

    def test_create_passed(self):
        cr = CheckResult(check_name="file_exists", status=ValidationStatus.PASSED, message="文件存在", evidence="/tmp/test.gbr")
        assert cr.check_name == "file_exists"
        assert cr.status == ValidationStatus.PASSED
        assert cr.message == "文件存在"
        assert cr.evidence == "/tmp/test.gbr"

    def test_create_failed(self):
        cr = CheckResult(check_name="file_size", status=ValidationStatus.FAILED)
        assert cr.status == ValidationStatus.FAILED
        assert cr.message == ""
        assert cr.evidence == ""


# ═══════════════════════════════════════════════════════════════
# 9. ValidationReport 数据模型
# ═══════════════════════════════════════════════════════════════

class TestValidationReport:
    """ValidationReport — 校验报告"""

    def test_create_all_passed(self):
        checks = [
            CheckResult(check_name="file_exists", status=ValidationStatus.PASSED),
            CheckResult(check_name="file_size", status=ValidationStatus.PASSED),
        ]
        report = ValidationReport(action_id="act-001", passed=True, checks=checks)
        assert report.action_id == "act-001"
        assert report.passed is True
        assert len(report.checks) == 2
        assert report.failed_checks == []
        assert report.evidence == []
        assert report.recommendation == ""
        assert isinstance(report.validated_at, datetime)

    def test_create_with_failures(self):
        ok = CheckResult(check_name="file_exists", status=ValidationStatus.PASSED)
        fail = CheckResult(check_name="drc_check", status=ValidationStatus.FAILED, message="间距违规")
        warn = CheckResult(check_name="unconnected", status=ValidationStatus.WARNING)
        report = ValidationReport(
            action_id="act-002",
            passed=False,
            checks=[ok, fail, warn],
            failed_checks=[fail],
            evidence=["drc_report.json"],
            recommendation="修复 1 处 DRC 违规后重新导出",
        )
        assert report.passed is False
        assert len(report.checks) == 3
        assert len(report.failed_checks) == 1
        assert report.failed_checks[0].check_name == "drc_check"
        assert "drc_report.json" in report.evidence


# ═══════════════════════════════════════════════════════════════
# 10. AdapterInfo 数据模型
# ═══════════════════════════════════════════════════════════════

class TestAdapterInfo:
    """AdapterInfo — 适配器信息（list_adapters 返回）"""

    def test_create_available(self):
        info = AdapterInfo(
            name="kicad",
            display_name="KiCad EDA",
            version="0.1.0",
            software_version="8.0.9",
            available=True,
            available_actions=["open_project", "export_gerber", "run_drc"],
            priority_path="pcbnew_api",
            capabilities=["export", "validate", "pcb"],
        )
        assert info.name == "kicad"
        assert info.display_name == "KiCad EDA"
        assert info.available is True
        assert "export_gerber" in info.available_actions
        assert info.priority_path == "pcbnew_api"
        assert "pcb" in info.capabilities
        assert info.status_message == ""

    def test_create_unavailable(self):
        info = AdapterInfo(
            name="solidworks",
            display_name="SolidWorks 2024",
            version="0.1.0",
            available=False,
            available_actions=[],
            priority_path="com",
            status_message="SolidWorks 未安装或 COM 组件不可用",
        )
        assert info.available is False
        assert info.available_actions == []
        assert info.software_version is None
        assert info.status_message == "SolidWorks 未安装或 COM 组件不可用"
        assert info.capabilities == []


# ═══════════════════════════════════════════════════════════════
# 11. 错误体系（core/errors.py — TDD 先写测试）
# ═══════════════════════════════════════════════════════════════



class TestRelayError:
    """RelayError — 所有 Bifrost 错误的基类"""

    def test_base_error(self):
        err = RelayError(
            error_code="ERR_UNKNOWN",
            message="未知错误",
            severity=ErrorSeverity.FATAL,
        )
        assert err.error_code == "ERR_UNKNOWN"
        assert err.message == "未知错误"
        assert err.severity == ErrorSeverity.FATAL
        assert err.suggested_action == ""
        assert err.context == {}
        assert err.recoverable is False
        assert isinstance(err, Exception)

    def test_defaults(self):
        err = RelayError(error_code="ERR_TEST", message="test")
        assert err.severity == ErrorSeverity.FATAL
        assert err.suggested_action == ""
        assert err.context == {}
        assert err.recoverable is False

    def test_str_representation(self):
        err = RelayError(error_code="ERR_TEST", message="something went wrong")
        assert "ERR_TEST" in str(err)
        assert "something went wrong" in str(err)

    def test_with_context(self):
        err = RelayError(
            error_code="ERR_TEST",
            message="failed",
            context={"path": "/tmp/test", "line": 42},
        )
        assert err.context["path"] == "/tmp/test"
        assert err.context["line"] == 42


class TestActionFailedError:
    """ActionFailedError — 动作执行失败"""

    def test_basic(self):
        err = ActionFailedError(
            action_id="act-001",
            action_name="export_gerber",
            message="Gerber 导出失败",
        )
        assert err.error_code == "ERR_ACTION_FAILED"
        assert err.action_id == "act-001"
        assert err.action_name == "export_gerber"
        assert err.severity == ErrorSeverity.FATAL

    def test_is_relay_error(self):
        err = ActionFailedError(action_id="a", action_name="n", message="m")
        assert isinstance(err, RelayError)

    def test_with_suggestion(self):
        err = ActionFailedError(
            action_id="act-002",
            action_name="flash_firmware",
            message="烧录失败",
            suggested_action="检查调试器连接后重试",
        )
        assert err.suggested_action == "检查调试器连接后重试"


class TestConfirmationRequiredError:
    """ConfirmationRequiredError — 需要用户确认"""

    def test_basic(self):
        err = ConfirmationRequiredError(
            action_id="act-001",
            message="烧录固件需要确认",
        )
        assert err.error_code == "ERR_CONFIRMATION_REQUIRED"
        assert err.severity == ErrorSeverity.NEEDS_HUMAN
        assert err.recoverable is True

    def test_is_relay_error(self):
        err = ConfirmationRequiredError(action_id="a", message="m")
        assert isinstance(err, RelayError)


class TestAdapterNotFoundError:
    """AdapterNotFoundError — 适配器不可用"""

    def test_basic(self):
        err = AdapterNotFoundError(app="kicad")
        assert err.error_code == "ERR_ADAPTER_NOT_FOUND"
        assert err.app == "kicad"
        assert "kicad" in str(err)

    def test_is_relay_error(self):
        err = AdapterNotFoundError(app="unknown")
        assert isinstance(err, RelayError)


class TestTimeoutError:
    """TimeoutError — 执行超时"""

    def test_basic(self):
        err = TimeoutError(
            action_id="act-001",
            timeout_seconds=300,
        )
        assert err.error_code == "ERR_TIMEOUT"
        assert err.action_id == "act-001"
        assert err.timeout_seconds == 300
        assert err.severity == ErrorSeverity.RETRYABLE
        assert err.recoverable is True

    def test_is_relay_error(self):
        err = TimeoutError(action_id="a")
        assert isinstance(err, RelayError)


class TestValidationFailedError:
    """ValidationFailedError — 校验失败"""

    def test_basic(self):
        err = ValidationFailedError(
            action_id="act-001",
            message="文件大小校验失败",
            failed_checks=["file_size", "drc_check"],
        )
        assert err.error_code == "ERR_VALIDATION_FAILED"
        assert err.action_id == "act-001"
        assert "file_size" in err.failed_checks
        assert err.severity == ErrorSeverity.FATAL

    def test_is_relay_error(self):
        err = ValidationFailedError(action_id="a", message="m")
        assert isinstance(err, RelayError)


# ═══════════════════════════════════════════════════════════════
# 12. 校验框架（core/validators.py — TDD 先写测试）
# ═══════════════════════════════════════════════════════════════

def _make_success_result(action_id: str = "act-001") -> ActionResult:
    """辅助：创建成功的 ActionResult"""
    now = datetime(2026, 8, 5, 12, 0, 0)
    return ActionResult(
        success=True,
        action_id=action_id,
        task_id="task-001",
        action_name="export_gerber",
        status=ActionStatus.SUCCESS,
        start_time=now,
        end_time=now,
        artifacts=[
            Artifact(path="/tmp/out/test.gbr", size_bytes=1000),
            Artifact(path="/tmp/out/test.drl", size_bytes=200),
        ],
    )


class TestValidationRule:
    """ValidationRule — 单个校验规则"""

    def test_create_rule(self):
        def always_pass(result: ActionResult) -> CheckResult:
            return CheckResult(check_name="always", status=ValidationStatus.PASSED)

        rule = ValidationRule(name="always", check_fn=always_pass)
        assert rule.name == "always"
        assert callable(rule.check_fn)

    def test_rule_execution(self):
        def check_artifacts(result: ActionResult) -> CheckResult:
            if len(result.artifacts) > 0:
                return CheckResult(check_name="has_artifacts", status=ValidationStatus.PASSED, message=f"{len(result.artifacts)} files")
            return CheckResult(check_name="has_artifacts", status=ValidationStatus.FAILED, message="no artifacts")

        rule = ValidationRule(name="has_artifacts", check_fn=check_artifacts)
        result = _make_success_result()
        check = rule.check_fn(result)
        assert check.status == ValidationStatus.PASSED
        assert "2 files" in check.message


class TestResultValidator:
    """ResultValidator — 校验框架核心"""

    def test_register_and_validate(self):
        validator = ResultValidator()

        def always_pass(r: ActionResult) -> CheckResult:
            return CheckResult(check_name="pass", status=ValidationStatus.PASSED)

        validator.register(ValidationRule(name="pass", check_fn=always_pass))
        result = _make_success_result()
        report = validator.validate(result)
        assert report.passed is True
        assert len(report.checks) == 1

    def test_validate_all_passed(self):
        validator = ResultValidator()

        validator.register(ValidationRule(
            name="p1",
            check_fn=lambda r: CheckResult(check_name="p1", status=ValidationStatus.PASSED),
        ))
        validator.register(ValidationRule(
            name="p2",
            check_fn=lambda r: CheckResult(check_name="p2", status=ValidationStatus.PASSED),
        ))

        report = validator.validate(_make_success_result())
        assert report.passed is True
        assert len(report.checks) == 2
        assert len(report.failed_checks) == 0

    def test_validate_with_failure(self):
        validator = ResultValidator()

        validator.register(ValidationRule(
            name="ok",
            check_fn=lambda r: CheckResult(check_name="ok", status=ValidationStatus.PASSED),
        ))
        validator.register(ValidationRule(
            name="fail",
            check_fn=lambda r: CheckResult(check_name="fail", status=ValidationStatus.FAILED, message="broken"),
        ))

        report = validator.validate(_make_success_result())
        assert report.passed is False
        assert len(report.failed_checks) == 1
        assert report.failed_checks[0].check_name == "fail"

    def test_validate_empty_rules(self):
        """无规则时默认通过"""
        validator = ResultValidator()
        report = validator.validate(_make_success_result())
        assert report.passed is True
        assert report.checks == []

    def test_validate_custom_recommendation(self):
        validator = ResultValidator()

        validator.register(ValidationRule(
            name="bad",
            check_fn=lambda r: CheckResult(check_name="bad", status=ValidationStatus.FAILED, message="bad"),
        ))

        report = validator.validate(_make_success_result(), recommendation="请修复后重试")
        assert report.passed is False
        assert report.recommendation == "请修复后重试"


class TestBuiltinRules:
    """内置校验规则"""

    def test_file_exists_pass(self):
        """无法在单元测试中验证真实文件，仅验证规则可构造和调用"""
        rule = builtin_rules.get("file_exists")
        assert rule is not None
        assert rule.name == "file_exists"

    def test_file_exists_fail_on_empty(self):
        rule = builtin_rules.get("file_exists")
        now = datetime(2026, 8, 5, 12, 0, 0)
        empty = ActionResult(
            success=True, action_id="a", task_id="t", action_name="n",
            status=ActionStatus.SUCCESS, start_time=now, end_time=now,
        )
        check = rule.check_fn(empty)
        assert check.status == ValidationStatus.FAILED

    def test_non_empty_artifacts_pass(self):
        rule = builtin_rules.get("non_empty_artifacts")
        result = _make_success_result()
        check = rule.check_fn(result)
        assert check.status == ValidationStatus.PASSED

    def test_non_empty_artifacts_fail(self):
        rule = builtin_rules.get("non_empty_artifacts")
        now = datetime(2026, 8, 5, 12, 0, 0)
        empty = ActionResult(
            success=True, action_id="a", task_id="t", action_name="n",
            status=ActionStatus.SUCCESS, start_time=now, end_time=now,
        )
        check = rule.check_fn(empty)
        assert check.status == ValidationStatus.FAILED

    def test_no_errors_rule_pass(self):
        rule = builtin_rules.get("no_errors")
        result = _make_success_result()
        check = rule.check_fn(result)
        assert check.status == ValidationStatus.PASSED

    def test_no_errors_rule_fail(self):
        rule = builtin_rules.get("no_errors")
        now = datetime(2026, 8, 5, 12, 0, 0)
        bad = ActionResult(
            success=False, action_id="a", task_id="t", action_name="n",
            status=ActionStatus.FAILED, start_time=now, end_time=now,
            errors=[ErrorDetail(error_code="ERR_X", severity=ErrorSeverity.FATAL, message="fail")],
        )
        check = rule.check_fn(bad)
        assert check.status == ValidationStatus.FAILED


# ═══════════════════════════════════════════════════════════════
# 13. 动作执行引擎（core/actions.py — TDD 先写测试）
# ═══════════════════════════════════════════════════════════════

# 需要 BaseAdapter 抽象接口作测试替身
from adapters.base import BaseAdapter


class _MockAdapter(BaseAdapter):
    """Mock 适配器——用于测试 ActionExecutor"""

    def __init__(self, name="mock", available=True, actions=None, mode="success"):
        self._name = name
        self._available = available
        self._actions = actions or ["mock_action"]
        self._mode = mode  # "success" | "fail" | "confirm"

    @property
    def name(self) -> str:
        return self._name

    @property
    def version(self) -> str:
        return "0.1.0"

    @property
    def available_actions(self) -> list[str]:
        return self._actions

    def check_availability(self) -> bool:
        return self._available

    def execute(self, action: Action) -> ActionResult:
        if self._mode == "confirm":
            return ActionResult(
                success=False,
                action_id=action.action_id,
                task_id=action.task_id,
                action_name=action.action_name,
                status=ActionStatus.CONFIRMATION_REQUIRED,
                start_time=datetime.now(),
                end_time=datetime.now(),
                warnings=["需要确认"],
                errors=[ErrorDetail(
                    error_code="ERR_CONFIRMATION_REQUIRED",
                    severity=ErrorSeverity.NEEDS_HUMAN,
                    message="需要用户确认",
                    recoverable=True,
                )],
            )
        elif self._mode == "fail":
            return ActionResult(
                success=False,
                action_id=action.action_id,
                task_id=action.task_id,
                action_name=action.action_name,
                status=ActionStatus.FAILED,
                start_time=datetime.now(),
                end_time=datetime.now(),
                errors=[ErrorDetail(
                    error_code="ERR_MOCK_FAIL",
                    severity=ErrorSeverity.FATAL,
                    message="Mock 失败",
                )],
            )
        else:
            return ActionResult(
                success=True,
                action_id=action.action_id,
                task_id=action.task_id,
                action_name=action.action_name,
                status=ActionStatus.SUCCESS,
                start_time=datetime.now(),
                end_time=datetime.now(),
                summary="Mock 成功",
                artifacts=[Artifact(path="/tmp/mock.out", size_bytes=42)],
            )

    def validate(self, result: ActionResult) -> ValidationReport:
        return ValidationReport(action_id=result.action_id, passed=True)


class TestActionExecutor:
    """ActionExecutor — 动作执行引擎"""

    def test_register_adapter(self):
        executor = ActionExecutor()
        executor.register_adapter(_MockAdapter(name="kicad"))
        adapters = executor.list_adapters()
        assert len(adapters) == 1
        assert adapters[0].name == "kicad"

    def test_list_adapters_with_filter(self):
        executor = ActionExecutor()
        executor.register_adapter(_MockAdapter(name="kicad"))
        executor.register_adapter(_MockAdapter(name="keil"))

        all_adapters = executor.list_adapters()
        assert len(all_adapters) == 2

        kicad_only = executor.list_adapters(filter="kicad")
        assert len(kicad_only) == 1
        assert kicad_only[0].name == "kicad"

    def test_list_adapters_filter_no_match(self):
        executor = ActionExecutor()
        executor.register_adapter(_MockAdapter(name="kicad"))
        result = executor.list_adapters(filter="solidworks")
        assert len(result) == 0

    def test_execute_success(self):
        executor = ActionExecutor()
        executor.register_adapter(_MockAdapter(name="kicad", mode="success"))

        action = Action(
            action_id="act-001",
            task_id="task-001",
            action_name="mock_action",
            action_type="execute",
            app="kicad",
        )
        result = executor.execute(action)
        assert result.success is True
        assert result.status == ActionStatus.SUCCESS
        assert result.summary == "Mock 成功"
        assert len(result.artifacts) == 1

    def test_execute_adapter_not_found(self):
        executor = ActionExecutor()
        action = Action(
            action_id="act-001",
            task_id="task-001",
            action_name="mock_action",
            action_type="execute",
            app="nonexistent",
        )
        result = executor.execute(action)
        assert result.success is False
        assert result.status == ActionStatus.FAILED
        assert any("nonexistent" in e.message for e in result.errors)

    def test_execute_unavailable_adapter(self):
        executor = ActionExecutor()
        executor.register_adapter(_MockAdapter(name="kicad", available=False))

        action = Action(
            action_id="act-001",
            task_id="task-001",
            action_name="mock_action",
            action_type="execute",
            app="kicad",
        )
        result = executor.execute(action)
        assert result.success is False

    def test_execute_confirmation_required(self):
        executor = ActionExecutor()
        executor.register_adapter(_MockAdapter(name="kicad", mode="confirm"))

        action = Action(
            action_id="act-001",
            task_id="task-001",
            action_name="mock_action",
            action_type="execute",
            app="kicad",
        )
        result = executor.execute(action)
        assert result.status == ActionStatus.CONFIRMATION_REQUIRED
        assert any("确认" in e.message for e in result.errors)

    def test_execute_failure(self):
        executor = ActionExecutor()
        executor.register_adapter(_MockAdapter(name="kicad", mode="fail"))

        action = Action(
            action_id="act-001",
            task_id="task-001",
            action_name="mock_action",
            action_type="execute",
            app="kicad",
        )
        result = executor.execute(action)
        assert result.success is False
        assert result.status == ActionStatus.FAILED

    def test_run_action_convenience(self):
        """run_action 便捷方法"""
        executor = ActionExecutor()
        executor.register_adapter(_MockAdapter(name="kicad", mode="success"))

        result = executor.run_action(
            app="kicad",
            action_name="mock_action",
            task_id="task-001",
        )
        assert result.success is True

    def test_run_action_adapter_not_found(self):
        executor = ActionExecutor()
        with pytest.raises(AdapterNotFoundError):
            executor.run_action(app="nonexistent", action_name="test")


# ═══════════════════════════════════════════════════════════════
# 14. 工作流编排（core/workflows.py — TDD 先写测试）
# ═══════════════════════════════════════════════════════════════

class TestStep:
    """Step — 工作流中的单个步骤"""

    def test_create_step(self):
        step = Step(
            step_id="step-1",
            name="导出 Gerber",
            app="kicad",
            action_name="export_gerber",
        )
        assert step.step_id == "step-1"
        assert step.name == "导出 Gerber"
        assert step.app == "kicad"
        assert step.action_name == "export_gerber"
        assert step.parameters == {}
        assert step.stop_on_failure is True

    def test_create_step_with_params(self):
        step = Step(
            step_id="step-2",
            name="烧录",
            app="stm32cubeide",
            action_name="flash_firmware",
            parameters={"firmware": "build/fw.bin"},
            requires_confirmation=True,
            stop_on_failure=True,
        )
        assert step.parameters["firmware"] == "build/fw.bin"
        assert step.requires_confirmation is True


class TestWorkflow:
    """Workflow — 多步骤工作流"""

    def _make_executor(self):
        executor = ActionExecutor()
        executor.register_adapter(_MockAdapter(name="kicad", mode="success"))
        executor.register_adapter(_MockAdapter(name="multisim", mode="success"))
        return executor

    def test_create_workflow(self):
        wf = Workflow(
            workflow_id="wf-001",
            title="导出 Gerber + DRC",
            steps=[
                Step(step_id="s1", name="打开工程", app="kicad", action_name="open_project"),
                Step(step_id="s2", name="导出 Gerber", app="kicad", action_name="export_gerber"),
            ],
        )
        assert wf.workflow_id == "wf-001"
        assert len(wf.steps) == 2

    def test_run_workflow_all_success(self):
        executor = self._make_executor()
        wf = Workflow(
            workflow_id="wf-001",
            title="测试工作流",
            steps=[
                Step(step_id="s1", name="步骤1", app="kicad", action_name="mock_action"),
                Step(step_id="s2", name="步骤2", app="kicad", action_name="mock_action"),
            ],
        )
        report = wf.run(executor)
        assert report["workflow_id"] == "wf-001"
        assert report["completed"] is True
        assert report["failed_steps"] == 0
        assert len(report["results"]) == 2

    def test_run_workflow_stop_on_first_failure(self):
        executor = self._make_executor()
        # 第二个 adapter 设为失败模式
        executor.register_adapter(_MockAdapter(name="multisim", mode="fail"))

        wf = Workflow(
            workflow_id="wf-002",
            title="失败工作流",
            steps=[
                Step(step_id="s1", name="成功步骤", app="kicad", action_name="mock_action"),
                Step(step_id="s2", name="失败步骤", app="multisim", action_name="mock_action", stop_on_failure=True),
                Step(step_id="s3", name="不该执行", app="kicad", action_name="mock_action"),
            ],
        )
        report = wf.run(executor)
        assert report["completed"] is False
        assert report["failed_steps"] >= 1
        # 步骤3不应执行
        assert len(report["results"]) == 2

    def test_run_workflow_continue_on_failure(self):
        executor = self._make_executor()
        executor.register_adapter(_MockAdapter(name="multisim", mode="fail"))

        wf = Workflow(
            workflow_id="wf-003",
            title="继续执行",
            steps=[
                Step(step_id="s1", name="成功", app="kicad", action_name="mock_action"),
                Step(step_id="s2", name="失败但不停止", app="multisim", action_name="mock_action", stop_on_failure=False),
                Step(step_id="s3", name="继续", app="kicad", action_name="mock_action"),
            ],
        )
        report = wf.run(executor)
        assert report["completed"] is False  # 有失败但整体未完成
        assert len(report["results"]) == 3  # 所有步骤都执行了

    def test_run_workflow_convenience_function(self):
        executor = self._make_executor()
        wf = Workflow(
            workflow_id="wf-004",
            title="便捷函数测试",
            steps=[
                Step(step_id="s1", name="步骤1", app="kicad", action_name="mock_action"),
            ],
        )
        report = run_workflow(wf, executor)
        assert report["completed"] is True
