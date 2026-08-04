"""
Hermes 工具包装层
================
将 Core 的工具包装为 Hermes/OpenAI 兼容的 function calling 格式。

Core 和 Adapters 位于项目根目录，与 hermes-relay/ 同级。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable

# ── 导入项目根目录的 Core（core/ 和 adapters/ 在根） ──────────
_ROOT = Path(__file__).resolve().parent.parent.parent  # hermes-relay/ → 根
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# 延迟导入——Core 模块尚未实现时不会崩溃，只在使用时报错
_core_available = False
try:
    from core.domain import Action, ActionResult, Task
    from core.actions import ActionExecutor
    from core.validators import ResultValidator
    from core.errors import RelayError
    from adapters.base import BaseAdapter
    _core_available = True
except ImportError:
    pass


# ── 工具定义（OpenAI/Hermes 兼容格式）─────────────────────────

def get_hermes_tool_definitions() -> list[dict[str, Any]]:
    """
    返回 Hermes 兼容的工具定义列表。

    每个工具定义遵循 OpenAI function calling schema：
    {
        "type": "function",
        "function": {
            "name": "...",
            "description": "...",
            "parameters": { "type": "object", "properties": {...}, "required": [...] }
        }
    }

    Returns:
        list[dict]: 工具定义列表，可直接注入 Hermes 系统提示的 <tools> 标签
    """
    return [
        _make_list_adapters_tool(),
        _make_run_action_tool(),
        _make_validate_result_tool(),
        _make_collect_logs_tool(),
        _make_confirm_action_tool(),
        _make_preview_action_tool(),
    ]


def _make_list_adapters_tool() -> dict:
    return {
        "type": "function",
        "function": {
            "name": "list_adapters",
            "description": (
                "列出当前可用的工业软件适配器（KiCad、Keil MDK、STM32CubeIDE、CCS、AutoCAD、Multisim、SolidWorks）"
                "及其各自版本、状态和可用动作列表。"
                "在任何实际操作之前调用此工具以确认目标软件可用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filter": {
                        "type": "string",
                        "description": "按名称过滤: 'kicad' | 'keil' | 'stm32cubeide' | 'ccs' | 'autocad' | 'multisim' | 'solidworks'。空字符串表示全部。",
                        "default": "",
                    }
                },
                "required": [],
            },
        },
    }


def _make_run_action_tool() -> dict:
    return {
        "type": "function",
        "function": {
            "name": "run_action",
            "description": (
                "执行一个结构化工业软件动作。这是最核心的通用工具。\n"
                "支持的动作类型取决于目标软件适配器。\n"
                "高风险动作（烧录、擦除、覆盖文件）会触发确认流程。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "app": {
                        "type": "string",
                        "description": "目标软件: kicad | stm32 | ti | solidworks",
                        "enum": ["kicad", "keil", "stm32cubeide", "ccs", "autocad", "multisim", "solidworks"],
                    },
                    "action_name": {
                        "type": "string",
                        "description": (
                            "动作名称。例如: open_project / export_gerber / run_drc / "
                            "export_bom / flash_firmware / identify_device / "
                            "verify_flash / collect_artifacts"
                        ),
                    },
                    "parameters": {
                        "type": "object",
                        "description": "动作参数，由目标 adapter 解释。例如 {\"project_path\": \"...\"}",
                        "default": {},
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["dry_run", "normal", "force"],
                        "description": (
                            "执行模式: dry_run=仅预览 / normal=正常执行 / force=强制执行（跳过确认）"
                        ),
                        "default": "normal",
                    },
                    "timeout_seconds": {
                        "type": "integer",
                        "description": "超时秒数",
                        "default": 300,
                    },
                },
                "required": ["app", "action_name"],
            },
        },
    }


def _make_validate_result_tool() -> dict:
    return {
        "type": "function",
        "function": {
            "name": "validate_result",
            "description": (
                "校验上一次执行的动作结果。检查输出文件是否存在、大小是否正常、"
                "DRC 是否通过等。每次 run_action 后建议调用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action_id": {
                        "type": "string",
                        "description": "要校验的 action_id（由 run_action 返回）",
                    },
                    "checks": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "指定校验项列表，空数组表示全部默认校验",
                        "default": [],
                    },
                },
                "required": ["action_id"],
            },
        },
    }


def _make_collect_logs_tool() -> dict:
    return {
        "type": "function",
        "function": {
            "name": "collect_logs",
            "description": (
                "收集指定动作或任务的日志、错误信息和产物列表。"
                "出错时或任务结束时使用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action_id": {
                        "type": "string",
                        "description": "指定动作 ID",
                        "default": "",
                    },
                    "task_id": {
                        "type": "string",
                        "description": "指定任务 ID（收集该任务下所有动作的日志）",
                        "default": "",
                    },
                    "include_raw_output": {
                        "type": "boolean",
                        "description": "是否包含软件原始输出",
                        "default": False,
                    },
                },
                "required": [],
            },
        },
    }


def _make_confirm_action_tool() -> dict:
    return {
        "type": "function",
        "function": {
            "name": "confirm_action",
            "description": (
                "⚠️ 安全工具。对之前被标记为需要确认的高风险动作进行显式确认或取消。\n"
                "涉及烧录 Flash、擦除芯片、覆盖工程文件等操作时必须调用。\n"
                "不要在未经用户同意的情况下自动确认。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action_id": {
                        "type": "string",
                        "description": "要确认的动作 ID",
                    },
                    "confirm": {
                        "type": "boolean",
                        "description": "true=确认执行 / false=取消动作",
                    },
                    "reason": {
                        "type": "string",
                        "description": "确认或取消的原因（可选）",
                        "default": "",
                    },
                },
                "required": ["action_id", "confirm"],
            },
        },
    }


def _make_preview_action_tool() -> dict:
    return {
        "type": "function",
        "function": {
            "name": "preview_action",
            "description": (
                "预览动作效果（dry-run），不实际执行。"
                "用于在不确定后果时先查看会发生什么。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "app": {
                        "type": "string",
                        "description": "目标软件: kicad | stm32 | ti | solidworks",
                    },
                    "action_name": {
                        "type": "string",
                        "description": "动作名称",
                    },
                    "parameters": {
                        "type": "object",
                        "description": "动作参数",
                        "default": {},
                    },
                },
                "required": ["app", "action_name"],
            },
        },
    }


# ── 工具执行调度器 ─────────────────────────────────────────────

def execute_hermes_tool_call(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """
    执行 Hermes 模型调用的工具。

    解析模型输出的 <tool_call> JSON，调用对应的 Core 功能，返回结构化结果。

    Args:
        tool_name: 工具名称（与 get_hermes_tool_definitions 中的 name 对应）
        arguments: 工具参数

    Returns:
        dict: 结构化执行结果，包含 success / summary / artifacts / errors 等字段

    Raises:
        ImportError: 如果 codex-relay Core 尚未实现
    """
    if not _core_available:
        raise ImportError(
            "Core 尚未实现。请先完成 Phase 1 开发（参见 docs/05-implementation-plan.md）。"
        )

    # 工具名 → 处理函数映射
    _handlers: dict[str, Callable] = {
        "list_adapters": _handle_list_adapters,
        "run_action": _handle_run_action,
        "validate_result": _handle_validate_result,
        "collect_logs": _handle_collect_logs,
        "confirm_action": _handle_confirm_action,
        "preview_action": _handle_preview_action,
    }

    handler = _handlers.get(tool_name)
    if handler is None:
        return {
            "success": False,
            "summary": f"未知工具: {tool_name}",
            "errors": [{"error_code": "ERR_UNKNOWN_TOOL", "message": f"工具 '{tool_name}' 未注册"}],
        }

    try:
        return handler(arguments)
    except RelayError as exc:
        return {
            "success": False,
            "summary": str(exc),
            "errors": [{"error_code": exc.error_code, "message": str(exc)}],
        }
    except Exception as exc:
        return {
            "success": False,
            "summary": f"工具执行异常: {exc}",
            "errors": [{"error_code": "ERR_INTERNAL", "message": str(exc)}],
        }


# ── 各工具的处理函数（占位，实现时填充）─────────────────────────

def _handle_list_adapters(args: dict) -> dict:
    """TODO: 实现 list_adapters"""
    # from core.actions import ActionExecutor
    # executor = ActionExecutor()
    # return executor.list_adapters(filter=args.get("filter", ""))
    return {
        "success": True,
        "summary": "list_adapters 尚未实现（Phase 1 开发中）",
        "adapters": [],
        "warnings": ["Core 层尚未实现"],
    }


def _handle_run_action(args: dict) -> dict:
    """TODO: 实现 run_action"""
    return {
        "success": False,
        "summary": "run_action 尚未实现（Phase 1 开发中）",
        "errors": [{"error_code": "ERR_NOT_IMPLEMENTED", "message": "Core 层尚未实现"}],
    }


def _handle_validate_result(args: dict) -> dict:
    """TODO: 实现 validate_result"""
    return {"success": False, "summary": "validate_result 尚未实现", "errors": []}


def _handle_collect_logs(args: dict) -> dict:
    """TODO: 实现 collect_logs"""
    return {"success": False, "summary": "collect_logs 尚未实现", "errors": []}


def _handle_confirm_action(args: dict) -> dict:
    """TODO: 实现 confirm_action"""
    return {"success": False, "summary": "confirm_action 尚未实现", "errors": []}


def _handle_preview_action(args: dict) -> dict:
    """TODO: 实现 preview_action"""
    return {"success": False, "summary": "preview_action 尚未实现", "errors": []}


# ── 便捷函数 ────────────────────────────────────────────────────

def tools_to_json() -> str:
    """将所有工具定义序列化为 JSON 字符串（用于注入 <tools> 标签）"""
    return json.dumps(get_hermes_tool_definitions(), ensure_ascii=False, indent=2)


def is_core_available() -> bool:
    """检查 codex-relay Core 是否可用"""
    return _core_available
