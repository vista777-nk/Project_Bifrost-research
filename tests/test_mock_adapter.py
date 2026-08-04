"""
Phase 1 Step 3c — Mock Adapter 单元测试

验证 MockAdapter 的三类行为和 BaseAdapter 接口合规性。
"""

from datetime import datetime

from core.domain import Action, ActionStatus, ErrorSeverity
from adapters.mock_adapter import MockAdapter


# ═══════════════════════════════════════════════════════════════
# 接口合规性
# ═══════════════════════════════════════════════════════════════

class TestMockAdapterInterface:
    """MockAdapter 实现 BaseAdapter 接口"""

    def test_implements_base_adapter(self):
        from adapters.base import BaseAdapter
        adapter = MockAdapter()
        assert isinstance(adapter, BaseAdapter)

    def test_name_property(self):
        adapter = MockAdapter(name="kicad")
        assert adapter.name == "kicad"

    def test_version_property(self):
        adapter = MockAdapter(version="1.2.3")
        assert adapter.version == "1.2.3"

    def test_available_actions(self):
        adapter = MockAdapter(actions=["open_project", "export_gerber", "run_drc"])
        assert "export_gerber" in adapter.available_actions
        assert len(adapter.available_actions) == 3

    def test_check_availability(self):
        available = MockAdapter(available=True)
        assert available.check_availability() is True

        unavailable = MockAdapter(available=False)
        assert unavailable.check_availability() is False


# ═══════════════════════════════════════════════════════════════
# 三类行为模式
# ═══════════════════════════════════════════════════════════════

def _make_action(action_name="test_action", app="mock") -> Action:
    return Action(
        action_id="act-001",
        task_id="task-001",
        action_name=action_name,
        action_type="execute",
        app=app,
    )


class TestMockAdapterSuccess:
    """success 模式"""

    def test_execute_returns_success(self):
        adapter = MockAdapter(mode="success")
        result = adapter.execute(_make_action())
        assert result.success is True
        assert result.status == ActionStatus.SUCCESS
        assert "模拟成功" in result.summary

    def test_execute_returns_artifacts(self):
        adapter = MockAdapter(mode="success")
        result = adapter.execute(_make_action("export_gerber"))
        assert len(result.artifacts) == 1
        assert "export_gerber" in result.artifacts[0].path

    def test_validate_passed(self):
        adapter = MockAdapter(mode="success")
        result = adapter.execute(_make_action())
        report = adapter.validate(result)
        assert report.passed is True


class TestMockAdapterFail:
    """fail 模式"""

    def test_execute_returns_failure(self):
        adapter = MockAdapter(mode="fail", error_code="ERR_TIMEOUT", error_message="超时了")
        result = adapter.execute(_make_action())
        assert result.success is False
        assert result.status == ActionStatus.FAILED
        assert result.errors[0].error_code == "ERR_TIMEOUT"
        assert "超时了" in result.errors[0].message

    def test_validate_fails(self):
        adapter = MockAdapter(mode="fail")
        result = adapter.execute(_make_action())
        report = adapter.validate(result)
        assert report.passed is False


class TestMockAdapterConfirm:
    """confirm 模式"""

    def test_execute_returns_confirmation_required(self):
        adapter = MockAdapter(mode="confirm")
        result = adapter.execute(_make_action("flash_firmware"))
        assert result.status == ActionStatus.CONFIRMATION_REQUIRED
        assert result.errors[0].error_code == "ERR_CONFIRMATION_REQUIRED"
        assert result.errors[0].severity == ErrorSeverity.NEEDS_HUMAN
        assert result.errors[0].recoverable is True


# ═══════════════════════════════════════════════════════════════
# 可配置性
# ═══════════════════════════════════════════════════════════════

class TestMockAdapterConfig:
    """自定义配置"""

    def test_custom_name_and_actions(self):
        adapter = MockAdapter(
            name="custom-app",
            version="9.9.9",
            actions=["action_a", "action_b"],
        )
        assert adapter.name == "custom-app"
        assert adapter.version == "9.9.9"
        assert adapter.available_actions == ["action_a", "action_b"]

    def test_defaults(self):
        adapter = MockAdapter()
        assert adapter.name == "mock"
        assert adapter.version == "0.1.0"
        assert adapter.available_actions == ["mock_action"]
        assert adapter.check_availability() is True
