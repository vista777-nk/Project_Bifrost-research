# 调研报告：GitHub 可借鉴资源 — 按软件与框架分类

> **日期**：2026-08-04
> **方法**：GitHub Topics + 网页搜索，针对 7 款软件 + 2 种 Agent 框架逐一筛选
> **目的**：找出可直接学习、fork 甚至在其基础上二次开发的现有项目

---

## 🔥 直接对口的高价值项目

这些项目与 Bifrost 的目标高度重叠，值得深入研究甚至直接协作。

### CCS / TI 嵌入式

| 项目 | Stars | 语言 | 为什么重要 |
|------|:---:|------|-----------|
| **[zww666-creater/NUEDC-STM32-MSPM0-SKILL](https://github.com/zww666-creater/NUEDC-STM32-MSPM0-SKILL)** | — | Python | **Codex skill**，STM32CubeMX→Keil + MSPM0 SysConfig→CCS 双工作流。与我们的 cubeide-build + keil-build + ccs-flash 三个 skill 目标完全一致！ |
| **[logicalmove/ccs1280-ti-embedded-workflow](https://github.com/logicalmove/ccs1280-ti-embedded-workflow)** | — | — | **Codex skill** for CCS 12.8.0，支持 F28335/F28034（TI C2000 系列）。版本号与我们选定的 12.8.1 几乎一致 |
| **[uoohyo/action-ccstudio-ide](https://github.com/uoohyo/action-ccstudio-ide)** | — | Shell | CCS GitHub Action — 证明 CCS **可以 headless 运行**，可用于 CI/CD |
| **[zfb132/ccstudio](https://github.com/zfb132/ccstudio)** | — | Shell/Docker | Docker 化的 CCS headless 环境。直接可用的 CCS CLI 自动化基础设施 |

### SolidWorks

| 项目 | Stars | 语言 | 为什么重要 |
|------|:---:|------|-----------|
| **[alisamsam/Solidworks-MCP](https://github.com/alisamsam/Solidworks-MCP)** | — | Python | **MCP Server for SolidWorks** — 22 个工具（零件/草图/特征），Claude AI 可用。**与我们的 solidworks-cad skill 目标一致！** 可以研究其 COM 调用模式 |
| **[skarpsill/SWAPI](https://github.com/skarpsill/SWAPI)** | — | Python | **AI-ready SW API 知识库** — 解析过的文档、索引、图谱，专为 LLM Agent 和 Codex 设计。可以作为我们 Skill 的参考数据源 |
| **[deloarts/pyswx](https://github.com/deloarts/pyswx)** | — | Python | SolidWorks API 的 Python 包装器。可直接用于我们的 adapter |
| **[Glutenberg/swtoolkit](https://github.com/Glutenberg/swtoolkit)** | — | Python | SolidWorks Python 工具包 |
| **[xarial/codestack](https://github.com/xarial/codestack)** | — | VBA/C# | 最全面的 SW API 代码示例库（宏、add-in、standalone） |

### Keil / STM32 工具链

| 项目 | Stars | 语言 | 为什么重要 |
|------|:---:|------|-----------|
| **[Majie-xixi/MCUQuickStart](https://github.com/Majie-xixi/MCUQuickStart)** | — | Python | STM32/Keil 项目生成器。Python 实现的 Keil 工程操作逻辑，可直接参考其 UV4 调用方式 |
| **[Masihtabaei/keil-restart-tool](https://github.com/Masihtabaei/keil-restart-tool)** | — | Python | Python 工具控制 Keil µVision — 证明 Keil 可通过外部脚本操控 |

### Multisim（2026-08-05 新增）

| 项目 | Stars | 语言 | 为什么重要 |
|------|:---:|------|-----------|
| **[Last-emo-boy/Multisim-MCP](https://github.com/Last-emo-boy/Multisim-MCP)** | 12 | Python | **MCP Server for Multisim** — 61 个工具，pywin32 调用 COM Automation API。架构（MCP 层 → 会话/快照/审计 → COM 适配层）与 Bifrost 完全一致，且证明纯 Python 部分可跨平台测试 |
| **[hodini007/Elecsyn](https://github.com/hodini007/Elecsyn)** | — | Python | AI 生成 SPICE netlist 并导入 Multisim 的自动化代理 — 验证 netlist 直通路径 |

### Codex 插件生态

| 项目 | Stars | 语言 | 为什么重要 |
|------|:---:|------|-----------|
| **[matlab/matlab-agentic-toolkit](https://github.com/matlab/matlab-agentic-toolkit)** | — | MATLAB | MathWorks 官方的工程 Agent 工具包 — **工业软件 + Agent 集成的官方范例**。MCP Server + Agent Skills 模式，与我们架构完全一致 |
| **[matlab/simulink-agentic-toolkit](https://github.com/matlab/simulink-agentic-toolkit)** | — | HTML | Simulink 版本的 Agent 工具包 |
| **[SethGammon/Citadel](https://github.com/SethGammon/Citadel)** | — | JS | Codex + Claude Code 的操作层：持久记忆、意图路由、安全钩子、成本监控 |
| **[AMAP-ML/LongHorizon-Harness](https://github.com/AMAP-ML/LongHorizon-Harness)** | — | Python | 长周期桌面自动化测试框架，支持 Codex/Claude Code 集成 |

### Hermes 生态

| 项目 | Stars | 语言 | 为什么重要 |
|------|:---:|------|-----------|
| **[ruvnet/ruflo](https://github.com/ruvnet/ruflo)** | — | TS | 多 Agent swarm 框架，原生支持 Codex + **Hermes**。含自适应记忆和 RAG |
| **[NousResearch/Hermes-Function-Calling](https://github.com/NousResearch/Hermes-Function-Calling)** | 1.4k | Python | Hermes 官方 function calling 示例（之前已研究） |

---

## 📊 按软件维度的资源丰富度

| 软件 | 可借鉴项目数 | 自动化成熟度 | 对 Bifrost 的价值 |
|------|:---:|:---:|------|
| KiCad | 大量 pcbnew 示例 | ⭐⭐⭐⭐⭐ | 已有完善的 Python API 生态 |
| STM32CubeIDE | 373 个 repo（多为固件项目） | ⭐⭐⭐ | Eclipse headless build 可参考 |
| CCS | **4 个直接对口项目** | ⭐⭐⭐ | 有 Codex skill + Docker + CI Action |
| Keil MDK | 2 个 Python 工具 | ⭐⭐ | UV4 CLI 调用有先例 |
| AutoCAD | 较少 | ⭐⭐ | accoreconsole 路径需自行探索 |
| Multisim | **2 个直接对口项目** | ⭐⭐⭐ | 已有 COM Automation MCP Server 参考实现 |
| SolidWorks | **5 个高价值项目** | ⭐⭐⭐⭐ | 有 MCP Server + Python 包装器 + API 知识库 |

---

## 🏗️ 建议的"站在巨人肩膀上"策略

### 1. CCS adapter → 基于 `NUEDC-STM32-MSPM0-SKILL` + `ccs1280-ti-embedded-workflow`

这两个项目已经实现了 CCS 的 Codex skill。我们可以：
- 研究他们的 SKILL.md 格式和工具定义
- 提取 CCS headless CLI 调用方式
- 将其 DSS 脚本模式融入我们的 adapter

### 2. SolidWorks adapter → 基于 `Solidworks-MCP` + `pyswx`

`Solidworks-MCP` 已经实现了 22 个 MCP 工具。我们可以：
- 参考其 COM 调用模式（特别是进程管理、文档生命周期）
- `pyswx` 提供了更 Pythonic 的 API 包装
- `SWAPI` 知识库可以作为 Skill 文档的参考资料

### 3. Keil adapter → 参考 `MCUQuickStart` + `keil-restart-tool`

这两个项目证明了 Keil 可以通过外部 Python 脚本操控。提取 UV4.exe 的命令行模式。

### 4. Multisim adapter → 基于 `Multisim-MCP`

该项目已验证 Multisim COM Automation API 的完整能力（打开设计、枚举/修改元件、运行仿真、采集输出）。我们可以：
- 参考其 `com_adapter.py` 的 COM 封装方式（进程管理、32-bit Python 约束）
- 借鉴其 snapshot + audit log 安全模式（对应我们的"破坏性必确认"原则）
- 复用其"纯 Python 工具与 COM 层分离"的测试策略

### 5. Codex 插件架构 → 对标 `matlab-agentic-toolkit`

MathWorks 官方出品的 Agent 工具包，是工业软件 + Agent 集成的黄金标准。其 MCP Server + Skill 的组织方式值得逐行学习。

### 6. STM32CubeIDE → 参考 Eclipse headless build 通用模式

STM32CubeIDE 基于 Eclipse，headless build 语法通用。373 个 repo 中有大量 `.project`/`.cproject` 配置可参考。

---

## ⚠️ 空白领域（需要自行开拓）

| 软件 | 缺口 | 我们的机会 |
|------|------|-----------|
| **AutoCAD** | accoreconsole 自动化极少 | 首创 AutoCAD CLI 自动化 Codex skill |
| **KiCad + Codex 集成** | 无现成 MCP Server | 我们可能是第一个做 KiCad MCP Server 的 |

---

## 📎 行动计划

1. **立即 fork 并研究**：`NUEDC-STM32-MSPM0-SKILL`、`Solidworks-MCP`、`Multisim-MCP`、`matlab-agentic-toolkit`
2. **提取可复用模块**：CCS DSS 脚本、SolidWorks COM 模式、Keil UV4 CLI 调用
3. **对标架构**：`matlab-agentic-toolkit` 的 MCP Server + Skill 组织方式
4. **在文档中引用**：在相关 adapter 的 README 和 SKILL.md 中致谢上游项目
