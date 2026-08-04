"""
Hermes 系统提示生成器
====================
构建包含工具定义、GOAP 推理指令、安全规则的系统提示。

Hermes 使用 ChatML 格式：
<|im_start|>system
...
<|im_end|>
<|im_start|>user
...
<|im_end|>

参考：NousResearch/Hermes-Function-Calling 的 prompter.py
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Optional

from .tools import get_hermes_tool_definitions
from .goap_templates import GOAP_SYSTEM_INSTRUCTION, get_goap_template_for_skill

# ── 基础系统提示 ─────────────────────────────────────────────────

BASE_SYSTEM_PROMPT = """You are a function calling AI model specialized in industrial software automation.
You are part of the Bifrost relay system, bridging AI agents with real engineering tools.

Your capabilities include:
- Operating KiCad 8.0 for PCB design (export Gerber, run DRC, export BOM)
- Building and flashing firmware with Keil MDK 5.39 (UV4 CLI)
- Configuring, building, and flashing STM32 projects with STM32CubeIDE
- Flashing and debugging TI chips with Code Composer Studio (CCS) 12.8
- Automating AutoCAD 2022 (accoreconsole + COM scripting)
- Reading and analyzing Multisim 14.3 circuits (COM Automation API)
- Automating SolidWorks 2024 SP5 (COM / Macro API)

You are provided with function signatures within <tools></tools> XML tags.
You may call one or more functions to assist with the user query.
Don't make assumptions about what values to plug into functions.
If available tools are not relevant, respond in natural conversational language.

For each function call, return a JSON object with function name and arguments within
<tool_call></tool_call> XML tags.

Use <scratch_pad></scratch_pad> XML tags to record your reasoning and planning
before you call the functions."""


SAFETY_RULES = """## ⚠️ Safety Rules (ABSOLUTE)

The following operations MUST NOT be executed without explicit user confirmation:
1. Flashing/writing to hardware (STM32, TI chips)
2. Erasing Flash/EEPROM
3. Overwriting existing project files
4. Deleting any files
5. Batch exporting that overwrites previous results
6. Sending production commands

When a tool returns status="confirmation_required", STOP and ask the user
to confirm before proceeding. Never auto-confirm destructive actions.

If a tool fails 3 times consecutively, STOP and report to the user.
If a tool returns severity="fatal", STOP and report to the user."""


OUTPUT_FORMAT = """## Output Format

When reporting results to the user, use this format:
✅ Successful steps: brief description
⚠️ Warnings: list warnings
❌ Failed steps: describe reason and suggested fix
📁 Artifacts: list output file paths"""


# ── 提示构建函数 ──────────────────────────────────────────────────

def build_system_prompt(
    skill_name: Optional[str] = None,
    include_goap: bool = True,
    extra_instructions: Optional[str] = None,
) -> str:
    """
    构建完整的 Hermes 系统提示。

    Args:
        skill_name: 指定 skill（如 'kicad-pcb'），用于加载对应的 GOAP 模板
        include_goap: 是否包含 GOAP 推理指令
        extra_instructions: 额外的自定义指令

    Returns:
        str: 完整系统提示文本（不含 ChatML 标签，由调用方包装）
    """
    parts = [BASE_SYSTEM_PROMPT]

    # 工具定义（JSON → <tools> XML）
    tools = get_hermes_tool_definitions()
    parts.append(f"\n<tools>\n{_tools_to_json_str(tools)}\n</tools>")

    # GOAP 推理指令
    if include_goap:
        parts.append(GOAP_SYSTEM_INSTRUCTION)
        if skill_name:
            goap_template = get_goap_template_for_skill(skill_name)
            if goap_template:
                parts.append(f"\n## Skill-Specific GOAP Template\n{goap_template}")

    # 安全规则
    parts.append(SAFETY_RULES)

    # 输出格式
    parts.append(OUTPUT_FORMAT)

    # 日期上下文
    parts.append(f"\nToday's date: {date.today().isoformat()}")

    # 额外指令
    if extra_instructions:
        parts.append(f"\n{extra_instructions}")

    return "\n\n".join(parts)


def build_chatml_messages(
    user_query: str,
    skill_name: Optional[str] = None,
    system_prompt: Optional[str] = None,
) -> list[dict[str, str]]:
    """
    构建 ChatML 格式的消息列表。

    Args:
        user_query: 用户查询
        skill_name: 指定 skill
        system_prompt: 自定义系统提示（不提供则自动生成）

    Returns:
        list[dict]: [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]
    """
    if system_prompt is None:
        system_prompt = build_system_prompt(skill_name=skill_name)

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_query},
    ]


def build_chatml_prompt(
    user_query: str,
    skill_name: Optional[str] = None,
    system_prompt: Optional[str] = None,
) -> str:
    """
    构建完整的 ChatML 格式提示字符串。

    可直接传入 Hermes 模型的 tokenizer。

    Args:
        user_query: 用户查询
        skill_name: 指定 skill
        system_prompt: 自定义系统提示

    Returns:
        str: ChatML 格式的完整提示
    """
    messages = build_chatml_messages(user_query, skill_name, system_prompt)
    lines = []
    for msg in messages:
        lines.append(f"<|im_start|>{msg['role']}\n{msg['content']}<|im_end|>")
    lines.append("<|im_start|>assistant\n")
    return "\n".join(lines)


# ── 辅助函数 ──────────────────────────────────────────────────────

def _tools_to_json_str(tools: list[dict]) -> str:
    """将工具定义列表转为格式化的 JSON 字符串"""
    import json
    return json.dumps(tools, ensure_ascii=False, indent=2)
