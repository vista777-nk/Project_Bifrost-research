# 🌈 Bifrost — 工业软件中继适配层

> *Bifrost is an open-source Agentic Manufacturing Interface Layer — bridging AI agents with industrial software.*
>
> *Bifrost：北欧神话中连接神域与人类世界的彩虹桥。本项目是 AI 世界与工业软件世界之间的那道桥。*

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-3776AB.svg)](https://www.python.org/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

**Product scope:** Codex must be able to create and edit native circuits in both
KiCad and Multisim. Native R/C/L/VDC schematic creation and editing now pass the
divider acceptance case on KiCad 8.0.9 and Multisim 14.3, without desktop input
automation. Broader libraries and imported topology editing remain unfinished.
Start with the [native circuit user manual](docs/10-circuit-authoring.md). See
[Circuit Authoring Scope](docs/decisions/TDR-002-circuit-authoring-scope.md).

---

## 🎯 理念：联合一体化 — "机器人制造机器人"

传统工业软件各自为政：KiCad 只管 PCB，Keil 只管固件，SolidWorks 只管结构。工程师在七套软件之间手动搬运数据，效率低、易出错、不可追溯。

**Bifrost 的核心理念是联合一体化**——将七款工业软件统一到一层中继适配层之下，让 AI Agent 像"联合参谋部"一样，跨软件、跨领域、跨阶段地调度工程能力：

```
                    ┌─────────────────────────────┐
                    │    🌈  Bifrost 联合参谋部      │
                    │  统一数据模型 · 统一动作接口      │
                    │  统一校验框架 · 统一日志追踪      │
                    └──────┬────────────┬─────────┘
           ┌───────────────┼────────────┼───────────────┐
    ┌──────┴──────┐ ┌──────┴──────┐ ┌──┴────────┐ ┌────┴─────┐
    │  PCB 设计    │ │  电路仿真    │ │  MCU 开发  │ │  CAD 结构 │
    │  KiCad      │ │  Multisim  │ │ CubeIDE   │ │ SolidWorks│
    │             │ │            │ │  CCS      │ │ AutoCAD  │
    │             │ │            │ │  Keil     │ │          │
    └─────────────┘ └─────────────┘ └───────────┘ └──────────┘
```

**机器人制造机器人**：AI 从电路设计 → 仿真验证 → 固件部署 → 结构外壳，**全栈、全链、全自动**。

---

## 🎯 一句话说清楚

**Bifrost** 是一层"工程中继适配层"，夹在 AI Agent（Codex、Hermes 等）与真实工业软件（KiCad、Keil MDK、STM32CubeIDE、CCS、AutoCAD、Multisim、SolidWorks）之间，负责把自然语言任务翻译成结构化动作 → 执行 → 校验 → 收集结果。

```
你："把这 KiCad 工程导出 Gerber 并检查有没有错误"
        ↓
     AI Agent (Codex / Hermes)
        ↓
  🌈  Bifrost  Skill 层（告诉模型何时用什么工具）
        ↓
  🌈  Bifrost  MCP Server（暴露工具接口）
        ↓
  🌈  Bifrost  Core（统一数据模型 + 动作引擎 + 校验框架）
        ↓
  🌈  Bifrost  Adapters（KiCad pcbnew / Keil UV4 / STM32CubeIDE / CCS / AutoCAD accoreconsole / Multisim COM / SolidWorks COM）
        ↓
    真实工业软件
```

---

## 🏗️ 架构总览

```
bifrost/                              ← 项目根（社区文档 + 许可证）
├── README.md                         #   项目主文档
├── CODE_OF_CONDUCT.md                #   社区行为准则
├── SECURITY.md                       #   安全策略
├── requirements.txt                  #   Python 依赖
│
├── core/                             # 📁 核心引擎（框架无关，Codex + Hermes 共享）
│   ├── domain.py                     #     数据模型
│   ├── actions.py                    #     动作引擎
│   ├── validators.py                 #     校验框架
│   └── errors.py                     #     错误体系
│
├── adapters/                         # 📁 工业软件适配器（8 个，框架无关）
│   ├── base.py                       #     BaseAdapter 抽象接口
│   ├── kicad/                        #     KiCad 8.0.9（pcbnew Python API）
│   ├── keil/                         #     Keil MDK 5.39（UV4 CLI）
│   ├── stm32cubeide/                 #     STM32CubeIDE 1.17（Eclipse CLI）
│   ├── ccs/                          #     CCS 12.8（Theia CLI + DSS）
│   ├── autocad/                      #     AutoCAD 2022（accoreconsole + COM）
│   ├── multisim/                     #     Multisim 14.3（COM Automation API）
│   └── solidworks/                   #     SolidWorks 2024 SP5（COM / Macro）
│
├── tests/                            # 📁 统一测试
├── examples/                         # 📁 使用示例
│
├── codex-relay/                      # 📁 Codex 插件（仅 Codex 专属文件）
│   ├── plugin.json                   #   Agent Plugin 清单
│   ├── .mcp.json                     #   MCP Server 配置
│   ├── codex_plugin/                 #   Python 包（MCP Server）
│   │   └── mcp/
│   │       ├── server.py
│   │       ├── tools.py
│   │       └── schemas.py
│   └── skills/                       #   Skill 集合（9 个 skill）
│       ├── kicad-pcb/SKILL.md
│       ├── keil-build/SKILL.md
│       ├── cubeide-build/SKILL.md
│       ├── ccs-flash/SKILL.md
│       ├── autocad-dwg/SKILL.md
│       ├── multisim-reader/SKILL.md
│       ├── solidworks-cad/SKILL.md
│       ├── stm32-flash/SKILL.md      #   向后兼容
│       └── relay-core/SKILL.md
│
├── hermes-relay/                     # 📁 Hermes 适配（仅 Hermes 专属文件）
│   └── hermes_tools/
│       ├── tools.py                  #   Hermes/OpenAI 工具定义
│       ├── prompts.py                #   ChatML 系统提示生成
│       └── goap_templates.py         #   GOAP 推理模板
│
└── docs/                             # 📁 技术文档体系（AI 可读版）
    ├── 00-overview.md … 09-hermes-integration.md
    ├── decisions/                    #   技术决策记录
    └── research-*.md                 #   调研报告
```

**核心设计原则**：
- **Core 零依赖** — 不依赖 Codex、不依赖任何工业软件、不依赖任何 AI 框架
- **Adapter 单一职责** — 每个软件一个 adapter，实现统一接口
- **CLI/API 优先** — 优先级：API > CLI > 宏 > 脚本 > GUI > 人工
- **输出必结构化** — 所有工具返回 JSON：`success` / `action` / `artifacts` / `errors`
- **破坏性必确认** — 写入硬件、覆盖文件、擦除 Flash 等操作需显式确认

---

## 🚀 快速开始

### 前置条件

- Python 3.11+
- Codex CLI（如需在 Codex 中使用）
- 目标工业软件（按需安装）：
  - KiCad 8.0.9
  - Keil MDK 5.39
  - STM32CubeIDE（推荐 1.17.0）
  - Code Composer Studio（推荐 12.8.1）
  - AutoCAD 2022
  - Multisim 14.3
  - SolidWorks 2024 SP5

### 安装

```bash
# 克隆仓库
git clone https://github.com/vista777-nk/Project_Bifrost-research.git
cd bifrost

# 安装依赖
pip install -r requirements.txt

# 进入 Codex 插件目录，开发模式安装
cd codex-relay
pip install -e .
```

### 在 Codex 中使用

```bash
# 方式 1：本地插件开发（从项目根目录）
# See docs/CODEX_SETUP.md for runtime setup and personal marketplace creation.
codex plugin add codex-relay@personal

# 方式 2：通过 marketplace（发布后）
# 在 Codex 中输入：$kicad-pcb
# Agent 自动激活 Skill 并加载 MCP Server
```

### 独立运行 MCP Server

```bash
cd codex-relay
python -m codex_plugin.mcp.server
```

---

## 🛠️ 支持的工具

| 工具 | 功能 | 风险级别 |
|------|------|:---:|
| `list_adapters` | 列出可用工业软件适配器 | 🟢 低 |
| `run_action` | 执行结构化动作 | 🟡 中 ~ 🔴 高 |
| `validate_result` | 校验执行结果 | 🟢 低 |
| `collect_logs` | 收集日志与产物 | 🟢 低 |
| `confirm_action` | 显式确认高风险动作 | 🟢 低 |
| `preview_action` | 预览动作效果（dry-run） | 🟢 低 |

---

## 🏭 支持的工业软件

| Phase | 软件 | 版本 | 集成路径 | 首批动作 |
|:---:|------|------|---------|---------|
| **P1** | **KiCad** | 8.0.9 | pcbnew Python API | 打开工程、导出 Gerber/BOM、DRC |
| **P1** | **Multisim** | 14.3 | COM Automation API | 读取电路、导出网表、仿真 |
| **P2** | **STM32CubeIDE** | 1.17.0 | Eclipse CLI | 配置/编译/烧录 STM32 |
| **P2** | **CCS** (TI) | 12.8.1 | Theia CLI + DSS | 识别设备、烧录、调试 TI 芯片 |
| **P3** | **Keil MDK** | 5.39 | UV4 CLI | 编译工程、烧录、调试 |
| **P4** | **SolidWorks** | 2024 SP5 | COM / Macro API | 打开文档、导出工程图/STP |
| **P5** | **AutoCAD** | 2022 | accoreconsole + COM | 脚本执行、批量导出 DWG/DXF |

---

## 📚 文档导航

| 文档 | 说明 |
|------|------|
| [`docs/00-overview.md`](docs/00-overview.md) | 项目总览（AI 可读版） |
| [`docs/01-architecture.md`](docs/01-architecture.md) | 架构设计详解 |
| [`docs/02-data-models.md`](docs/02-data-models.md) | 统一数据模型定义 |
| [`docs/03-tools-design.md`](docs/03-tools-design.md) | 工具接口设计 |
| [`docs/04-plugin-design.md`](docs/04-plugin-design.md) | Codex 插件层设计 |
| [`docs/05-implementation-plan.md`](docs/05-implementation-plan.md) | 分阶段实现计划 |
| [`docs/06-testing-strategy.md`](docs/06-testing-strategy.md) | 测试策略 |
| [`docs/07-gap-analysis.md`](docs/07-gap-analysis.md) | 调研与差距分析 |
| [`docs/08-agent-skills-standard.md`](docs/08-agent-skills-standard.md) | Agent Skills 开放标准 |
| [`docs/09-hermes-integration.md`](docs/09-hermes-integration.md) | Hermes 集成方案 |

---

## 🤝 贡献

我们欢迎所有形式的贡献！请先阅读：

- [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) — 社区行为准则
- [`docs/05-implementation-plan.md`](docs/05-implementation-plan.md) — 了解当前阶段

---

## 📄 许可证

本项目采用 [MIT License](LICENSE)。

---

## 🙏 致谢

### 上游项目（站在巨人肩膀上）

本项目受益于以下开源项目的先驱工作：

| 项目 | 领域 | 借鉴价值 |
|------|------|---------|
| **[NUEDC-STM32-MSPM0-SKILL](https://github.com/zww666-creater/NUEDC-STM32-MSPM0-SKILL)** | Codex Skill / 嵌入式 | Keil + CCS 双工作流 Codex Skill 范例 |
| **[ccs1280-ti-embedded-workflow](https://github.com/logicalmove/ccs1280-ti-embedded-workflow)** | Codex Skill / TI | CCS 12.8.0 Codex Skill，TI C2000 系列 |
| **[Solidworks-MCP](https://github.com/alisamsam/Solidworks-MCP)** | MCP Server / CAD | SolidWorks MCP Server，22 工具参考实现 |
| **[pyswx](https://github.com/deloarts/pyswx)** | Python / CAD | SolidWorks API Python 包装器 |
| **[SWAPI](https://github.com/skarpsill/SWAPI)** | AI 知识库 / CAD | AI-ready SolidWorks API 知识库 |
| **[codestack](https://github.com/xarial/codestack)** | API 示例 / CAD | 最全面的 SolidWorks API 代码示例库 |
| **[MCUQuickStart](https://github.com/Majie-xixi/MCUQuickStart)** | Python / 嵌入式 | Keil 工程 Python 生成器 |
| **[keil-restart-tool](https://github.com/Masihtabaei/keil-restart-tool)** | Python / 嵌入式 | 外部 Python 操控 Keil µVision |
| **[matlab-agentic-toolkit](https://github.com/matlab/matlab-agentic-toolkit)** | Agent 集成 / 工程 | MathWorks 官方，工业软件 Agent 集成黄金标准 |
| **[Citadel](https://github.com/SethGammon/Citadel)** | Codex 操作层 | 持久记忆、意图路由、安全钩子 |
| **[ruflo](https://github.com/ruvnet/ruflo)** | Agent Swarm / Hermes | 多 Agent 框架，原生 Codex + Hermes |
| **[Hermes-Function-Calling](https://github.com/NousResearch/Hermes-Function-Calling)** | Hermes / LLM | Hermes 官方 function calling 示例 |
| **[action-ccstudio-ide](https://github.com/uoohyo/action-ccstudio-ide)** | CI/CD / CCS | CCS headless GitHub Action |
| **[Multisim-MCP](https://github.com/Last-emo-boy/Multisim-MCP)** | MCP Server / 电路仿真 | Multisim COM Automation 参考实现，61 工具 + snapshot/audit log 安全模式 |

### 标准与协议

- [Agent Skills 开放标准](https://agentskills.io/) — Skill 格式遵循此标准
- [Model Context Protocol](https://modelcontextprotocol.io/) — 工具接口基于 MCP
- [Conventional Commits](https://www.conventionalcommits.org/) — Commit 规范

### 工业软件

- [KiCad](https://www.kicad.org/) · [STMicroelectronics](https://www.st.com/) · [Texas Instruments](https://www.ti.com/) · [Dassault Systèmes](https://www.solidworks.com/) · [Autodesk](https://www.autodesk.com/) · [Arm Keil](https://www.keil.com/) · [NI Multisim](https://www.ni.com/)

---

<p align="center">
  <em>🌈 Bifrost — 联合一体化，机器人制造机器人。桥接 AI 与工业，让每一行指令都落进现实。</em>
</p>
