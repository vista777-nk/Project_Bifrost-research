"""
Hermes Tools — 初始化
"""
from .tools import (
    get_hermes_tool_definitions,
    execute_hermes_tool_call,
    tools_to_json,
    is_core_available,
)
from .prompts import (
    build_system_prompt,
    build_chatml_messages,
    build_chatml_prompt,
)
from .goap_templates import (
    get_goap_template_for_skill,
    render_goap_template,
    list_available_goap_templates,
    GOAP_SYSTEM_INSTRUCTION,
)

__all__ = [
    # tools
    "get_hermes_tool_definitions",
    "execute_hermes_tool_call",
    "tools_to_json",
    "is_core_available",
    # prompts
    "build_system_prompt",
    "build_chatml_messages",
    "build_chatml_prompt",
    # goap
    "get_goap_template_for_skill",
    "render_goap_template",
    "list_available_goap_templates",
    "GOAP_SYSTEM_INSTRUCTION",
]
