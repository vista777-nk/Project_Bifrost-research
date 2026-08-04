# 🌈 Bifrost — 工业软件中继适配层

> *Bifrost：北欧神话中连接神域与人类世界的彩虹桥。本项目是 AI 世界与工业软件世界之间的那道桥。*

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-3776AB.svg)](https://www.python.org/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

---

## 🎯 一句话说清楚

**Bifrost** 是一层"工程中继适配层"，夹在 AI Agent（Codex、Hermes 等）与真实工业软件（KiCad、STM32、TI、SolidWorks）之间，负责把自然语言任务翻译成结构化动作 → 执行 → 校验 → 收集结果。

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
  🌈  Bifrost  Adapters（KiCad pcbnew / STM32 pyocd / TI UniFlash / SolidWorks COM）
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
├── codex-relay/                      # 📁 Codex 中继实现
│   ├── plugin.json                   #   Agent Plugin 清单
│   ├── .mcp.json                     #   MCP Server 配置
│   ├── skills/                       #   Skill 集合（每软件一个 skill）
│   │   ├── kicad-pcb/SKILL.md
│   │   ├── stm32-flash/SKILL.md
│   │   ├── ti-flash/SKILL.md
│   │   └── solidworks-cad/SKILL.md
│   ├── mcp/                          #   MCP Server（Python）
│   │   ├── server.py
│   │   ├── tools.py
│   │   └── schemas.py
│   ├── core/                         #   核心引擎（零外部框架依赖）
│   │   ├── domain.py                 #     数据模型
│   │   ├── actions.py                #     动作引擎
│   │   ├── validators.py             #     校验框架
│   │   └── errors.py                 #     错误体系
│   ├── adapters/                     #   工业软件适配器
│   │   ├── base.py                   #     BaseAdapter 抽象接口
│   │   ├── kicad/                    #     KiCad（pcbnew Python API）
│   │   ├── stm32/                    #     STM32（pyocd / CubeProgrammer）
│   │   ├── ti/                       #     TI（UniFlash / DSLite）
│   │   └── solidworks/               #     SolidWorks（COM / Macro）
│   ├── examples/                     #   使用示例
│   └── tests/                        #   测试
│
├── hermes-relay/                     # 📁 Hermes 中继实现（未来）
│   └── (复用 codex-relay/core/ 和 adapters/，仅加薄包装层)
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
- 目标工业软件（按需安装：KiCad 8.0+ / STM32CubeProgrammer / etc.）

### 安装

```bash
# 克隆仓库
git clone https://github.com/YOUR_USERNAME/bifrost.git
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
codex plugin install --local ./codex-relay

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

| 软件 | 状态 | 集成路径 | 首批动作 |
|------|:---:|---------|---------|
| **KiCad** | 🚧 规划中 | pcbnew Python API | 打开工程、导出 Gerber/BOM、DRC |
| **STM32** | 🚧 规划中 | pyocd / CubeProgrammer CLI | 识别设备、烧录、校验 |
| **TI** | ⏳ 后续 | UniFlash CLI / DSLite | 识别设备、烧录、校验 |
| **SolidWorks** | ⏳ 后续 | COM / Macro API | 打开文档、导出工程图 |

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
- [`CONVENTIONS.md`](CONVENTIONS.md) — 项目规范与约定
- [`docs/05-implementation-plan.md`](docs/05-implementation-plan.md) — 了解当前阶段

---

## 📄 许可证

本项目采用 [MIT License](LICENSE)。

---

## 🙏 致谢

- [Agent Skills 开放标准](https://agentskills.io/) — 本项目的 Skill 格式遵循此标准
- [Model Context Protocol](https://modelcontextprotocol.io/) — 本项目的工具接口基于 MCP
- [KiCad](https://www.kicad.org/) / [STMicroelectronics](https://www.st.com/) / [Texas Instruments](https://www.ti.com/) / [Dassault Systèmes](https://www.solidworks.com/)

---

<p align="center">
  <em>🌈 Bifrost — 桥接 AI 与工业，让每一行指令都落进现实。</em>
</p>
