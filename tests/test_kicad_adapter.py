"""
Phase 1 Step 3d — KiCad Adapter 单元测试

测试 KiCadAdapter 在不安装 KiCad 的 CI 环境中的行为：
- 接口合规性
- 不可用时的优雅降级
- collect_artifacts（纯文件系统操作，不依赖 KiCad）
- 参数校验

注：标记 @pytest.mark.kicad 的测试需要 KiCad 安装后才能运行，
CI 默认跳过。
"""

import os
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from core.domain import Action, ActionStatus, ErrorSeverity
from adapters.kicad.adapter import KiCadAdapter


# ═══════════════════════════════════════════════════════════════
# 接口合规性
# ═══════════════════════════════════════════════════════════════

class TestKiCadAdapterInterface:
    """KiCadAdapter 实现 BaseAdapter 接口"""

    def test_implements_base_adapter(self):
        from adapters.base import BaseAdapter
        adapter = KiCadAdapter()
        assert isinstance(adapter, BaseAdapter)

    def test_name(self):
        assert KiCadAdapter().name == "kicad"

    def test_version(self):
        assert KiCadAdapter().version == "0.1.0"

    def test_available_actions(self):
        actions = KiCadAdapter().available_actions
        assert "export_gerber" in actions
        assert "run_drc" in actions
        assert "export_bom" in actions
        assert "open_project" in actions
        assert "collect_artifacts" in actions
        assert "get_project_info" in actions

    def test_check_availability_does_not_crash(self):
        """check_availability 在任何环境下都不应崩溃"""
        adapter = KiCadAdapter()
        result = adapter.check_availability()
        assert isinstance(result, bool)


# ═══════════════════════════════════════════════════════════════
# 优雅降级（无 KiCad 环境）
# ═══════════════════════════════════════════════════════════════

def _make_action(action_name: str, **params) -> Action:
    return Action(
        action_id="act-001", task_id="task-001",
        action_name=action_name, action_type="execute", app="kicad",
        parameters=params,
    )


class TestKiCadAdapterUnavailable:
    """无 KiCad 时的优雅降级"""

    def test_execute_returns_unavailable_when_no_kicad(self):
        adapter = KiCadAdapter()
        # 如果 KiCad 碰巧可用，跳过此测试
        if adapter.check_availability():
            pytest.skip("KiCad 已安装——跳过不可用测试")

        result = adapter.execute(_make_action("export_gerber", project_path="/tmp/test.kicad_pcb"))
        assert result.success is False
        assert result.errors[0].error_code == "ERR_SOFTWARE_NOT_FOUND"

    def test_execute_unsupported_action(self):
        adapter = KiCadAdapter()
        result = adapter.execute(_make_action("nonexistent_action"))
        assert result.success is False
        assert result.errors[0].error_code == "ERR_ACTION_NOT_SUPPORTED"


# ═══════════════════════════════════════════════════════════════
# collect_artifacts（纯文件系统操作，不依赖 KiCad）
# ═══════════════════════════════════════════════════════════════

class TestKiCadCollectArtifacts:
    """collect_artifacts 不依赖 KiCad，可在任何环境测试"""

    def test_collect_in_empty_dir(self):
        adapter = KiCadAdapter()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = adapter.execute(_make_action("collect_artifacts", output_dir=tmpdir))
            assert result.success is True
            assert len(result.artifacts) == 0

    def test_collect_finds_matching_files(self):
        adapter = KiCadAdapter()
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建几个模拟产物文件
            (Path(tmpdir) / "test.gbr").write_text("gerber")
            (Path(tmpdir) / "test.drl").write_text("drill")
            (Path(tmpdir) / "report.json").write_text("{}")
            (Path(tmpdir) / "readme.txt").write_text("hello")  # 不匹配 *.txt

            result = adapter.execute(_make_action("collect_artifacts", output_dir=tmpdir))
            assert result.success is True
            # 默认 patterns: *.gbr, *.drl, *.csv, *.json
            assert len(result.artifacts) == 3  # gbr + drl + json
            paths = [a.path for a in result.artifacts]
            assert any("test.gbr" in p for p in paths)
            assert any("test.drl" in p for p in paths)
            assert any("report.json" in p for p in paths)

    def test_collect_custom_patterns(self):
        adapter = KiCadAdapter()
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "data.csv").write_text("a,b,c")
            (Path(tmpdir) / "notes.txt").write_text("hello")

            result = adapter.execute(_make_action(
                "collect_artifacts", output_dir=tmpdir, patterns=["*.csv"],
            ))
            assert len(result.artifacts) == 1
            assert "data.csv" in result.artifacts[0].path


# ═══════════════════════════════════════════════════════════════
# 参数校验
# ═══════════════════════════════════════════════════════════════

class TestKiCadParameterValidation:
    """缺参时的错误返回（注：若 KiCad 未安装，参数检查前会先触发不可用错误）"""

    def test_export_gerber_missing_project_path(self):
        adapter = KiCadAdapter()
        result = adapter.execute(_make_action("export_gerber"))
        assert result.success is False
        # 两种可能的错误路径：KiCad 不可用 或 缺少参数
        error_codes = {e.error_code for e in result.errors}
        assert error_codes & {"ERR_SOFTWARE_NOT_FOUND", "ERR_MISSING_PARAM"}

    def test_export_bom_missing_schematic_path(self):
        adapter = KiCadAdapter()
        result = adapter.execute(_make_action("export_bom"))
        assert result.success is False
        error_codes = {e.error_code for e in result.errors}
        assert error_codes & {"ERR_SOFTWARE_NOT_FOUND", "ERR_MISSING_PARAM"}
