"""
Bifrost — Hermes Relay
=======================
Hermes 开源模型系列的 function calling 适配层。

本模块是 codex-relay 的薄包装层：
- 复用 codex-relay/core/   (数据模型 + 动作引擎 + 校验框架)
- 复用 codex-relay/adapters/ (KiCad/STM32/TI/SolidWorks 适配器)
- 仅负责：将 Core 能力包装为 Hermes 兼容的 function calling 格式

与 Codex 路径的区别：
- Codex:  Skill (SKILL.md) → MCP Server (stdio) → Core
- Hermes: GOAP Prompt (系统提示) → Tool Wrapper → Core
"""

__version__ = "0.1.0"
