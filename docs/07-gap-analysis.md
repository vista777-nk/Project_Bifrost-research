# 调研报告：Codex/Hermes 插件开发范式对比与差距分析

> **日期**：2026-08-04
> **调研范围**：openai/codex (103k⭐)、openai/plugins (4.9k⭐)、openai/skills (24.5k⭐)、NousResearch/Hermes-Function-Calling (1.4k⭐)、modelcontextprotocol/servers (89k⭐)、agentskills.io 开放标准

---

## 1. 核心发现：我们之前的理解和实际差距巨大

一句话总结：**我们之前的设计是"闭门造车"，与 Codex 真实的插件体系差距很大。** 好消息是，这些差距都可以修正，而且修正后的设计会比原来专业得多。

---

## 2. Codex 插件体系的真实面目

### 2.1 插件清单格式（我们完全搞错了）

**我们设计的**：
```json
// codex_plugin/plugin.json — 不存在的位置
{
  "name": "codex-relay",
  "skills": [{ "path": "skills/relay-workflows/SKILL.md", "triggers": [...] }],
  "mcpServers": { "codex-relay": { "command": "python", "args": [...] } }
}
```

**Codex 实际的格式（位于 `.codex-plugin/plugin.json`）**：

```json
{
  "name": "codex-relay",
  "version": "0.1.0",
  "description": "工业软件中继适配层",
  "author": { "name": "Your Name" },
  "homepage": "https://github.com/xxx/codex-relay",
  "license": "MIT",
  "keywords": ["kicad", "stm32", "pcb", "firmware"],
  "skills": "./skills/",
  "mcpServers": "./.mcp.json",
  "interface": {
    "displayName": "Codex Relay",
    "shortDescription": "工业软件中继适配层",
    "longDescription": "让 Codex 稳定调用 KiCad/STM32/TI/SolidWorks...",
    "developerName": "Your Name",
    "category": "Developer Tools",
    "capabilities": ["Interactive", "Read", "Write"],
    "defaultPrompt": "导出 KiCad Gerber 并检查 DRC",
    "brandColor": "#2563EB",
    "composerIcon": "./assets/icon.png",
    "logo": "./assets/logo.png"
  }
}
```

**关键差异**：
- ❌ 插件清单在 `.codex-plugin/plugin.json`，不是 `codex_plugin/plugin.json`
- ❌ `skills` 和 `mcpServers` 是路径字符串（指向目录），不是内联数组
- ❌ MCP Server 配置在独立的 `.mcp.json` 文件，不在 plugin.json 里
- ❌ 没有 `triggers` 字段，匹配靠 skill 的 `name`/`description` + 用户 `$mention`

### 2.2 新版 Agent Plugin 格式（Codex 正在迁移到的新标准）

Codex 现在支持两种清单格式，新格式叫 **Agent Plugin Manifest**：

```json
{
  "$schema": "https://agentskills.io/spec/agent-plugin/v1.json",
  "name": "codex-relay",
  "version": "0.1.0",
  "description": "工业软件中继适配层",
  "author": { "name": "Your Name" },
  "homepage": "https://github.com/xxx/codex-relay",
  "license": "MIT",
  "keywords": ["kicad", "stm32", "industrial", "eda"],
  "extensions": {
    "com.openai": {
      "skills": "./skills/",
      "mcpServers": "./.mcp.json",
      "apps": "./.app.json",
      "interface": { ... }
    }
  }
}
```

**关键差异**：
- 需要 `$schema` 字段指向 Agent Plugin 规范
- `extensions.com.openai` 下放 Codex 专有配置
- 允许跨平台（Hermes 等可以通过不同 extension namespace 共存）

### 2.3 SKILL.md 的真实格式（Agent Skills 开放标准）

**我们设计的**：纯 Markdown，无结构化元数据。

**实际标准**（由 Anthropic 提出，Codex/Copilot/VS Code/Junie 等均支持）：

```markdown
---
name: relay-workflows
description: 工业软件中继工作流 — 安全地操作 KiCad/STM32/TI/SolidWorks
---

# Relay Workflows

## 触发条件
当用户提出以下类型请求时使用此 skill：
- KiCad / PCB 设计 / Gerber / DRC / BOM
- STM32 / 烧录 / 固件刷写
...

## 工具速查
| 工具 | 用途 |
|------|------|
| list_adapters | 列出可用软件适配器 |
...
```

**关键差异**：
- ✅ 需要 **YAML 前置元数据**（`name`, `description`）
- ✅ Agent 启动时只加载 `name` + `description`（渐进式发现）
- ✅ 用户用 `$skill-name` 语法显式调用
- ✅ 每个 skill 是一个**文件夹**，内含 `SKILL.md` + 可选 `scripts/`、`references/`、`assets/`

### 2.4 渐进式发现机制（Progressive Disclosure）

```
Stage 1: Discovery（启动时）
  → Agent 只加载所有 skill 的 name + description（极低成本）
  
Stage 2: Activation（任务匹配时）
  → 当任务与 skill 的 description 匹配，或用户显式 $mention
  → Agent 读取完整 SKILL.md 内容进入上下文
  
Stage 3: Execution（执行时）
  → Agent 按照 SKILL.md 中的指示操作
  → 可选执行 bundled scripts、读取 references
```

**我们之前完全没考虑这个机制**，设计的是一个静态的、一次性全加载的 Skill 文档。

---

## 3. MCP Server 的真实配置方式

### 3.1 `.mcp.json` 文件格式

```json
{
  "mcpServers": {
    "codex-relay": {
      "command": "python",
      "args": ["-m", "codex_relay.mcp.server"],
      "env": {
        "PYTHONPATH": "${pluginRoot}"
      }
    }
  }
}
```

或 Codex 用户级配置（`.codex/config.toml`）：

```toml
[mcp_servers.codex-relay]
command = "python"
args = ["-m", "codex_relay.mcp.server"]
```

### 3.2 我们对 MCP 的理解基本正确

MCP Server 的实现方式（Python MCP SDK、工具注册、stdio 通信）我们的设计和实际一致。只是配置方式需要调整。

---

## 4. Hermes Function Calling 的真实模式

### 4.1 Hermes 不是"另一个 Codex"

**关键认知修正**：Hermes 是一个**开源 LLM 模型系列**，不是像 Codex 那样的 Agent 框架。它没有"插件系统"。

Hermes 的 function calling 是通过 **prompt engineering** 实现的：
- 系统提示中包含 `<tools>` XML 标签
- 模型输出 `<tool_call>` XML 标签
- 外部代码解析 XML、执行工具、返回 `<tool_response>`

### 4.2 Hermes 的工具定义方式

```python
from langchain.tools import tool

@tool
def flash_firmware(device: str, firmware_path: str) -> dict:
    """
    烧录固件到指定 STM32 设备。
    Args:
        device (str): 设备标识符，如 'STM32F407'
        firmware_path (str): 固件文件路径
    Returns:
        dict: 包含烧录结果的结构化字典
    """
    # 实现...
```

工具定义的 docstring 会自动转换为 OpenAI tool schema 格式。

### 4.3 GOAP 推理框架（重要！）

Hermes-3 引入了 **Goal Oriented Action Planning**：

```
<scratch_pad>
Goal: 把 KiCad 工程导出 Gerber 并检查
Actions:
  - gerber_files = functions.export_gerber(project_path="...")
  - drc_result = functions.run_drc(project_path="...")
  - validation = functions.validate_result(action_id=drc_result.action_id)
Observation: (执行结果填入)
Reflection: 所有步骤成功，DRC 无错误，建议用户查看 Gerber 文件
</scratch_pad>
<tool_call>
{"name": "export_gerber", "arguments": {...}}
</tool_call>
```

**这不只是"调用工具"，而是让模型在调用工具前先做规划和推理。** 这比我们设计的简单 Skill 文档要强大得多。

### 4.4 Hermes 对 codex-relay 的真正意义

Hermes 适配不是"把插件移植过去"，而是：
1. 用 Hermes 支持的 function calling 格式包装 Core 的工具
2. 利用 GOAP 推理框架增强复杂任务的分解能力
3. Core 层不变，只换"调用协议"

---

## 5. 业界参考项目

| 项目 | Stars | 语言 | 关键借鉴 |
|------|-------|------|---------|
| `openai/codex` | 103k | Rust 96% | 插件体系、Skill 标准、Agent Plugin 格式 |
| `openai/plugins` | 4.9k | JS/Python | 真实插件范例（Figma、Notion、Linear） |
| `openai/skills` | 24.5k | Python | Skill 编写范式（已弃用，迁移至 plugins） |
| `NousResearch/Hermes-Function-Calling` | 1.4k | Python | @tool 装饰器、GOAP、prompt 模板 |
| `modelcontextprotocol/servers` | 89k | TS/Python | MCP Server 参考实现 |
| `agentskills/agentskills` | - | - | Agent Skills 开放标准规范 |

---

## 6. 差距汇总：我们的设计需要修正的地方

### 6.1 严重问题（必须修正）

| # | 问题 | 现状 | 应该改成 |
|---|------|------|---------|
| 1 | 插件清单路径 | `codex_plugin/plugin.json` | `.codex-plugin/plugin.json`（或根目录 `plugin.json` Agent Plugin 格式） |
| 2 | 插件清单格式 | 自创格式 | 遵循 Agent Plugin 标准，含 `$schema`、`extensions` |
| 3 | SKILL.md 格式 | 纯 Markdown | YAML frontmatter (`name` + `description`) + Markdown body |
| 4 | Skill 组织 | 单个 SKILL.md 文件 | 每个 skill 一个文件夹，内含 `SKILL.md` |
| 5 | MCP 配置 | plugin.json 内联 | 独立 `.mcp.json` 文件 |
| 6 | 渐进式发现 | 未考虑 | 实现 name/description 元数据提取 |

### 6.2 中等问题（建议修正）

| # | 问题 | 现状 | 应该改成 |
|---|------|------|---------|
| 7 | Skill 触发机制 | 自定义 `triggers` 字段 | 依赖 Skill `name` + `description` + 用户 `$mention` |
| 8 | 目录结构 | `codex_plugin/skills/relay-workflows/SKILL.md` | `skills/relay-workflows/SKILL.md`（在插件根目录） |
| 9 | MCP Server 位置 | `codex_plugin/mcp/` | `mcp/`（更扁平）或保持在 codex_plugin 但做符号链接 |
| 10 | GOAP 推理 | 未考虑 | 在 SKILL.md 中嵌入 GOAP 模板（为 Hermes 做准备） |
| 11 | 多 skill 设计 | 单一 skill | 每个软件一个独立 skill（更易发现和复用） |

### 6.3 可以保留的设计

| # | 内容 | 原因 |
|---|------|------|
| 1 | Core 层的 pydantic 数据模型 | 框架无关，设计完全正确 |
| 2 | Adapter 模式 | 单一职责、可替换，架构正确 |
| 3 | 错误分类体系 | 工程实用，保留 |
| 4 | 破坏性动作确认机制 | 安全必要，保留 |
| 5 | Python 3.11+ | TDR-001 结论仍然成立 |
| 6 | 结构化输出 | 核心设计正确 |

---

## 7. 修正后的推荐项目结构

```
bifrost/                              ← 项目根（社区文档 + 共享核心）
├── README.md / CODE_OF_CONDUCT.md / SECURITY.md
├── pyproject.toml / requirements.txt
│
├── core/                             # 📁 核心引擎（框架无关，Codex + Hermes 共享）
│   ├── domain.py / actions.py / validators.py / errors.py
│
├── adapters/                         # 📁 工业软件适配器（8 个）
│   ├── base.py
│   ├── kicad/ multisim/ stm32cubeide/ ccs/
│   └── keil/ autocad/ solidworks/ stm32/
│
├── tests/                            # 📁 统一测试
├── examples/                         # 📁 使用示例
│
├── codex-relay/                      # 📁 Codex 专属
│   ├── plugin.json                   #   Agent Plugin 清单
│   ├── .mcp.json                     #   MCP Server 配置
│   ├── skills/                       #   9 个 skill 文件夹（每软件一个）
│   └── codex_plugin/mcp/             #   MCP Server 实现（server/tools/schemas）
│
├── hermes-relay/                     # 📁 Hermes 专属（薄包装层）
│   └── hermes_tools/                 #   tools.py / prompts.py / goap_templates.py
│
└── docs/                             # 📁 技术文档体系
    ├── 00-overview.md … 09-hermes-integration.md
    ├── decisions/
    └── research-*.md
```

---

## 8. 修正后的格式落地位置

修正后的 plugin.json（Agent Plugin 格式）、SKILL.md 格式（YAML frontmatter + Markdown body + GOAP 模板）和 `.mcp.json` 配置，已并入 `docs/04-plugin-design.md` 作为**唯一权威定义**，本文不再重复，以避免两处定义漂移。

目录结构已按"根目录共享 `core/` + `adapters/`"方案实际落地（见根 `README.md` 架构图与本文第 7 节）。

---

## 11. 分步修正行动计划

### 文档重构（A 类）——已全部完成 ✅

| 序号 | 任务 | 状态 |
|------|------|:---:|
| A1 | 更新 `docs/04-plugin-design.md` — 插件清单格式为 Agent Plugin 标准 | ✅ |
| A2 | 更新 `docs/04-plugin-design.md` — SKILL.md 为 YAML frontmatter + Markdown | ✅ |
| A3 | 更新 `docs/00-overview.md` — 目录结构为修正版 | ✅ |
| A4 | 新增 `docs/07-gap-analysis.md` — 本调研报告 | ✅ |
| A5 | 新增 `docs/08-agent-skills-standard.md` — Agent Skills 开放标准参考 | ✅ |
| A6 | 新增 `docs/09-hermes-integration.md` — Hermes GOAP 集成方案 | ✅ |

### 编码阶段应用（B 类）

| 序号 | 任务 | 状态 |
|------|------|:---:|
| B1 | 创建 `codex-relay/plugin.json`（Agent Plugin 格式） | ⏳ Phase 1（任务 1.8） |
| B2 | 创建 `codex-relay/.mcp.json` | ⏳ Phase 1（任务 1.8） |
| B3 | 目录落地：`core/`、`adapters/` 置于项目根目录共享 | ✅ 已完成 |
| B4 | 每个软件拆为独立 skill 文件夹（9 个） | ✅ 目录已建，SKILL.md 内容待写 |
| B5 | SKILL.md 全部加 YAML frontmatter | ⏳ Phase 1（任务 1.11） |
| B6 | 实现 skill 元数据提取器（供渐进式发现使用） | ⏳ Phase 1 后续 |

---

## 12. 关键认知升级总结

| 之前的理解 | 修正后的认知 |
|-----------|------------|
| Codex 插件是一个自定义 JSON | Codex 遵循 Agent Plugin 开放标准 |
| Skill 是纯文本指南 | Skill 是有元数据的结构化文件夹，支持渐进式发现 |
| Hermes 是"另一个 Codex" | Hermes 是 LLM 模型系列，通过 prompt 实现 tool calling |
| 移植到 Hermes = 改写插件 | 移植 = 换 tool calling 协议 + 增加 GOAP 推理 |
| Skill 触发靠我们定义的触发器列表 | Skill 发现靠 name/description 匹配 + 用户 `$mention` |
