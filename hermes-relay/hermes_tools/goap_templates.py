"""
GOAP (Goal Oriented Action Planning) 推理模板
=============================================
为 Hermes-3 模型提供结构化推理框架。

GOAP 四阶段：
    Goal:       重新陈述用户目标
    Actions:    列出需要调用的函数和参数（Python 风格伪代码）
    Observation: 工具返回结果摘要
    Reflection:  评估工具相关性、参数完备性、任务状态

参考：Hermes-3 tool-use template with <scratch_pad>
"""

from __future__ import annotations

# ── GOAP 系统指令 ─────────────────────────────────────────────────

GOAP_SYSTEM_INSTRUCTION = """## GOAP Reasoning Framework

Before calling any tools, use <scratch_pad></scratch_pad> XML tags to plan your approach:

<scratch_pad>
Goal: <restate the user's specific objective>
Actions:
  <list planned function calls in Python-style pseudocode>
  - result_var = functions.function_name(param1=value1, ...)
Observation: <summarize tool results here after execution>
Reflection: <evaluate: are tools relevant? are parameters complete? is the task done?>
</scratch_pad>

Then emit your tool calls within <tool_call></tool_call> XML tags."""


# ── 各软件的 GOAP 模板 ────────────────────────────────────────────

GOAP_TEMPLATES: dict[str, str] = {
    "kicad-pcb": """## KiCad PCB GOAP Template

<scratch_pad>
Goal: {user_goal}
Actions:
  - adapter_status = functions.list_adapters(filter="kicad")
  - project_result = functions.run_action(app="kicad", action_name="open_project", parameters={{"project_path": "{project_path}"}})
  - export_result = functions.run_action(app="kicad", action_name="{action_name}", parameters={params})
  - validation = functions.validate_result(action_id=export_result.action_id)
  - logs = functions.collect_logs(action_id=export_result.action_id)
Observation: <fill after each tool execution>
Reflection: <evaluate: all steps complete? any DRC errors? files present and non-empty?>
</scratch_pad>""",

    "stm32-flash": """## STM32 Flash GOAP Template

<scratch_pad>
Goal: {user_goal}
Actions:
  - adapter_status = functions.list_adapters(filter="stm32")
  - device_info = functions.run_action(app="stm32", action_name="identify_device", parameters={{}})
  - preview = functions.preview_action(app="stm32", action_name="flash_firmware", parameters={params})
  - ⚠️ flash_result = functions.run_action(app="stm32", action_name="flash_firmware", parameters={params})
  - verify = functions.run_action(app="stm32", action_name="verify_flash", parameters={{}})
  - logs = functions.collect_logs(action_id=flash_result.action_id)
Observation: <fill after each tool execution>
Reflection: <evaluate: device identified? flash confirmed by user? verify passed?>
</scratch_pad>""",

    "ti-flash": """## TI Flash GOAP Template

<scratch_pad>
Goal: {user_goal}
Actions:
  - adapter_status = functions.list_adapters(filter="ti")
  - device_info = functions.run_action(app="ti", action_name="identify_device", parameters={{}})
  - ⚠️ flash_result = functions.run_action(app="ti", action_name="flash_firmware", parameters={params})
  - verify = functions.run_action(app="ti", action_name="verify_flash", parameters={{}})
Observation: <fill after each tool execution>
Reflection: <evaluate: device identified? flash confirmed? verify passed?>
</scratch_pad>""",

    "solidworks-cad": """## SolidWorks CAD GOAP Template

<scratch_pad>
Goal: {user_goal}
Actions:
  - adapter_status = functions.list_adapters(filter="solidworks")
  - doc_result = functions.run_action(app="solidworks", action_name="open_document", parameters={{"file_path": "{file_path}"}})
  - export_result = functions.run_action(app="solidworks", action_name="{action_name}", parameters={params})
  - validation = functions.validate_result(action_id=export_result.action_id)
Observation: <fill after each tool execution>
Reflection: <evaluate: document opened? export complete? files valid?>
</scratch_pad>""",

    "relay-core": """## Relay Core GOAP Template

<scratch_pad>
Goal: {user_goal}
Actions:
  - adapter_status = functions.list_adapters(filter="{app_filter}")
  - action_result = functions.{tool_name}({params})
  - logs = functions.collect_logs(action_id=action_result.action_id)
Observation: <fill after each tool execution>
Reflection: <evaluate: adapters available? action successful? next steps?>
</scratch_pad>""",
}


def get_goap_template_for_skill(skill_name: str) -> str | None:
    """
    获取指定 skill 的 GOAP 推理模板。

    Args:
        skill_name: skill 名称（如 'kicad-pcb', 'stm32-flash'）

    Returns:
        str | None: GOAP 模板文本，未找到则返回 None
    """
    return GOAP_TEMPLATES.get(skill_name)


def render_goap_template(skill_name: str, **variables: str) -> str:
    """
    渲染 GOAP 模板，填充变量。

    Args:
        skill_name: skill 名称
        **variables: 模板变量（如 user_goal, project_path, action_name 等）

    Returns:
        str: 渲染后的 GOAP scratch_pad 文本
    """
    template = GOAP_TEMPLATES.get(skill_name, GOAP_TEMPLATES["relay-core"])
    try:
        return template.format(**variables)
    except KeyError as exc:
        # 缺失的变量用占位符填充
        return template.replace("{" + str(exc).strip("'") + "}", f"<{exc}>")


def list_available_goap_templates() -> list[str]:
    """列出所有可用的 GOAP 模板名称"""
    return list(GOAP_TEMPLATES.keys())
