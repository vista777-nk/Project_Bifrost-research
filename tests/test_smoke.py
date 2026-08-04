"""冒烟测试：验证包结构完整、Hermes 骨架可用。

Phase 1 之前的最低保障：确保根包可导入、Hermes 工具定义完整。
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_core_package_importable():
    import core

    assert core is not None


def test_adapters_package_importable():
    import adapters

    assert adapters is not None


def test_hermes_tool_definitions_complete():
    if str(ROOT / "hermes-relay") not in sys.path:
        sys.path.insert(0, str(ROOT / "hermes-relay"))
    from hermes_tools import get_hermes_tool_definitions

    tools = get_hermes_tool_definitions()
    names = {t["function"]["name"] for t in tools}
    assert names == {
        "list_adapters",
        "run_action",
        "validate_result",
        "collect_logs",
        "confirm_action",
        "preview_action",
    }


def test_hermes_system_prompt_buildable():
    if str(ROOT / "hermes-relay") not in sys.path:
        sys.path.insert(0, str(ROOT / "hermes-relay"))
    from hermes_tools import build_system_prompt

    prompt = build_system_prompt(skill_name="kicad-pcb")
    assert "<tools>" in prompt
    assert "KiCad" in prompt
