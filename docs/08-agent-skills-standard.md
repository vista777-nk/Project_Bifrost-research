# 08 — Agent Skills 开放标准参考（AI 可读版）

> **来源**：[agentskills.io](https://agentskills.io/specification)
> **用途**：确保 codex-relay 的 Skill 设计严格遵循开放标准，实现跨平台兼容

---

## 1. 什么是 Agent Skills

Agent Skills 是一个**轻量级、开放的文件格式**，用于扩展 AI Agent 的能力。
最初由 Anthropic 开发，作为开放标准发布，已被 Codex、GitHub Copilot、VS Code、Junie、fast-agent 等广泛采用。

> 我们的 codex-relay 插件中的每个 skill 都应该遵循这个标准。

---

## 2. 核心文件结构

```
my-skill/                    # ← skill 根目录（文件夹名即 skill 名）
├── SKILL.md                 # 必需：元数据 + 指令
├── scripts/                 # 可选：可执行代码
├── references/              # 可选：参考文档
├── assets/                  # 可选：模板、资源
└── agents/                  # 可选：agent 特定配置
    └── openai.yaml          # Codex 特定配置
    └── hermes.yaml          # Hermes 特定配置（未来）
```

---

## 3. SKILL.md 格式规范

### 3.1 必需的 YAML 前置元数据

```yaml
---
name: skill-name              # 必需：唯一标识符，kebab-case
description: 一句话描述         # 必需：Agent 用此判断何时激活 skill
---
```

### 3.2 可选的 YAML 前置字段

```yaml
---
name: my-skill
description: 一句话描述
version: 1.2.3                # 可选：语义化版本
author: Your Name              # 可选
tags: [tag1, tag2]             # 可选：辅助发现
license: MIT                   # 可选
---
```

### 3.3 Markdown Body

前置元数据之后的全部内容是 Markdown 格式的指令，Agent 在激活时完整读取。

---

## 4. 渐进式发现（Progressive Disclosure）

这是 Agent Skills 最核心的设计模式：

```
┌─────────────────────────────────────────────┐
│ Stage 1: Discovery                          │
│ Agent 启动时，只加载所有 skill 的:            │
│   - name                                    │
│   - description                             │
│ 成本极低，可支持数百个 skill                   │
├─────────────────────────────────────────────┤
│ Stage 2: Activation                         │
│ 满足以下任一条件时触发：                       │
│   - 用户消息匹配 skill 的 description          │
│   - 用户显式使用 $skill-name                  │
│   - 其他 skill 引用此 skill                   │
│ Agent 读取完整 SKILL.md 到上下文              │
├─────────────────────────────────────────────┤
│ Stage 3: Execution                          │
│ Agent 按照 SKILL.md 中的指令执行              │
│ 可选执行 scripts/ 中的代码                   │
│ 可选读取 references/ 中的文档                │
└─────────────────────────────────────────────┘
```

### 4.1 对我们的意义

- 我们应该为每个工业软件各写一个独立 skill
- 每个 SKILL.md 的 `description` 至关重要——它是 Agent 判断"何时激活"的唯一依据
- Skill 细分比 skill 合并更好——让 Agent 只加载需要的上下文

---

## 5. Agent Plugin 格式（插件级）

当多个 skill 需要共享 MCP Server、Apps 等基础设施时，使用 Agent Plugin 包装：

```json
{
  "$schema": "https://agentskills.io/spec/agent-plugin/v1.json",
  "name": "plugin-name",
  "version": "1.0.0",
  "description": "...",
  "author": { "name": "..." },
  "extensions": {
    "com.openai": {
      "skills": "./skills/",
      "mcpServers": "./.mcp.json"
    }
  }
}
```

### 5.1 与纯 Skill 的区别

| 特性 | 纯 Skill 文件夹 | Agent Plugin |
|------|----------------|-------------|
| 结构 | 一个 SKILL.md | 多个 skill + 共享资源 |
| MCP Server | 不支持 | 支持（.mcp.json） |
| App 集成 | 不支持 | 支持（.app.json） |
| 发行方式 | 直接放 skills 目录 | 通过 Marketplace 安装 |
| 适用场景 | 简单指南 | 复杂工具链 |

**codex-relay 明显是 Agent Plugin 级别**，因为它需要 MCP Server。

---

## 6. 对 codex-relay 的具体应用

### 6.1 Skill 拆分方案

```
skills/
├── kicad-pcb/
│   └── SKILL.md        # name: kicad-pcb
│                        # description: KiCad PCB 设计工作流 — 导出 Gerber、BOM、
│                        #   DRC 检查、产物收集。触发条件：用户提到 KiCad/PCB/Gerber。
├── multisim-reader/
│   └── SKILL.md        # name: multisim-reader
│                        # description: Multisim 电路读取与网表导出。触发条件：Multisim/仿真/网表。
├── cubeide-build/
│   └── SKILL.md        # name: cubeide-build
│                        # description: STM32CubeIDE 工程编译与烧录。触发条件：STM32/CubeIDE/固件。
├── ccs-flash/
│   └── SKILL.md        # name: ccs-flash
│                        # description: TI CCS 芯片识别、烧录与调试。触发条件：TI/CCS/C2000/烧录。
├── keil-build/
│   └── SKILL.md        # name: keil-build
│                        # description: Keil MDK 工程编译与烧录。触发条件：Keil/UV4/ARM。
├── solidworks-cad/
│   └── SKILL.md        # name: solidworks-cad
│                        # description: SolidWorks CAD 操作 — 打开文档、导出工程图/STP。
├── autocad-dwg/
│   └── SKILL.md        # name: autocad-dwg
│                        # description: AutoCAD 脚本执行与 DWG/DXF 批量导出。
├── stm32-flash/
│   └── SKILL.md        # name: stm32-flash（向后兼容，推荐 cubeide-build）
└── relay-core/
    └── SKILL.md        # name: relay-core
                         # description: Bifrost 通用中继操作 — 列出适配器、
                         #   确认高风险动作、收集日志。当需要了解系统状态时使用。
```

### 6.2 为什么拆成 9 个而非 1 个

| 对比维度 | 1 个大 skill | 9 个小 skill |
|---------|-------------|-------------|
| 上下文占用 | 每次全加载（~2000 tokens） | 只加载相关 skill（~500 tokens） |
| 发现精确度 | description 太泛，误触发概率高 | 每个 description 精准匹配 |
| 可维护性 | 一个文件越滚越大 | 每个独立维护 |
| 跨平台复用 | 耦合在一起 | 可单独迁移到其他平台 |
| $mention 可用性 | 只有一个名称 | 9 个清晰可调用的名称 |

---

## 7. 客户端兼容矩阵

| 客户端 | 支持程度 | 备注 |
|--------|---------|------|
| Codex (CLI/App/IDE) | ✅ 完整支持 | Agent Plugin + Skills + MCP |
| GitHub Copilot | ✅ 支持 Skills | 通过 `.github/copilot-instructions.md` 或 skills 目录 |
| VS Code | ✅ 支持 Skills | 通过 Copilot Chat |
| Hermes (开源模型) | ⚠️ 不原生支持 | 需通过 prompt engineering 手动注入 |
| fast-agent | ✅ 支持 Skills | 开源 Agent 框架 |
| Junie (JetBrains) | ✅ 支持 Skills | |

---

## 8. 参考链接

- [Agent Skills 规范](https://agentskills.io/specification)
- [Agent Plugin 规范](https://agentskills.io/specification/agent-plugin)
- [GitHub: agentskills/agentskills](https://github.com/agentskills/agentskills)
- [openai/plugins 范例](https://github.com/openai/plugins)
