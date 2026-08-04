# 00 — 项目总览（AI 可读版）

> **阅读对象**：AI 编程助手（Copilot、Kimi 等）
> **用途**：让 AI 在开始任何编码工作前，先理解项目的完整上下文
> **前置阅读**：ChatGPT 原始企划文档
> **后续阅读**：`01-architecture.md`

---

## 1. 一句话定义

**codex-relay** 是一层"工程中继适配层"，夹在 AI Agent（Codex）与真实工业软件（KiCad、STM32、TI、SolidWorks）之间，负责把自然语言任务翻译成结构化动作、执行、校验、收集结果。

---

## 2. 项目要解决的核心问题

| 问题 | 现状 | 目标 |
|------|------|------|
| AI 无法直接操作工业软件 | Agent 只能"说"，不能"做" | 提供标准化工具接口让 Agent 调用 |
| 工业软件自动化路径碎片化 | CLI/API/Macro/GUI 四种路径混用 | 建立优先级体系和统一抽象层 |
| 执行结果不可验证 | 只能靠人工检查 | 每次执行后自动校验输出 |
| 错误不可追溯 | 出了问题不知道哪里坏了 | 结构化日志 + 错误分类 + 产物追踪 |

---

## 3. 系统架构总览（一张图看懂）

```
┌─────────────────────────────────────────────────────────┐
│                    用户 / Codex Agent                      │
├─────────────────────────────────────────────────────────┤
│  Skill (SKILL.md)                                        │
│  "什么时候用什么工具、怎么组合、什么时候停下来问人"            │
├─────────────────────────────────────────────────────────┤
│  MCP Server (mcp/server.py)                              │
│  暴露工具: list_adapters / run_action / validate_result … │
├─────────────────────────────────────────────────────────┤
│  Core (core/)                                            │
│  数据模型 / 动作引擎 / 校验框架 / 错误体系                   │
├─────────────────────────────────────────────────────────┤
│  Adapters (adapters/)                                    │
│  kicad/ keil/ stm32cubeide/ ccs/ autocad/ multisim/ solidworks/│
│  每个 adapter 实现统一接口，对接具体软件                      │
├─────────────────────────────────────────────────────────┤
│  真实工业软件                                              │
│  KiCad 8 · Keil MDK 5 · STM32CubeIDE · CCS 12 · AutoCAD 2022 · Multisim 14 · SolidWorks 2024│
└─────────────────────────────────────────────────────────┘
```

**关键设计原则**：Core 不依赖 Codex，也不依赖任何具体软件。Codex 插件层只负责暴露 Core 的能力。Adapters 只负责翻译 Core 的标准指令到具体软件。

---

## 4. 分阶段路线图

### Phase 0 — 设计阶段（当前 ✅）
- [x] 技术决策记录（语言选择）
- [x] 统一数据模型定义
- [x] 工具接口设计
- [x] 插件层设计
- [x] KiCad / Keil / STM32CubeIDE / CCS / AutoCAD / Multisim / SolidWorks CLI/API 调研

### Phase 1 — KiCad + Multisim（第一期开发）
- [ ] 实现 Core 数据模型（pydantic）
- [ ] 实现 MCP Server（list_adapters + run_action + confirm_action）
- [ ] Mock adapter（不连真实软件）
- [ ] KiCad adapter（打开工程 / 导出 Gerber / 导出 BOM / 运行 DRC）
- [ ] Multisim adapter（读取电路 XML / 导出网表）
- [ ] 写 Skill 文档（kicad-pcb + multisim-reader + relay-core）
- [ ] 端到端测试

### Phase 2 — STM32CubeIDE + CCS（MCU 开发环境）
- [ ] STM32CubeIDE adapter（导入工程 / 编译 / 烧录）
- [ ] CCS adapter（识别 TI 设备 / 烧录 / 校验 / DSS 脚本）
- [ ] Skills: cubeide-build + ccs-flash

### Phase 3 — Keil MDK
- [ ] Keil adapter（UV4 CLI 编译 / 烧录 / 调试）
- [ ] Skill: keil-build

### Phase 4 — SolidWorks
- [ ] SolidWorks adapter（COM 接口 / 打开文档 / 导出工程图 / STP）
- [ ] Skill: solidworks-cad

### Phase 5 — AutoCAD + Hermes 迁移
- [ ] AutoCAD adapter（accoreconsole / 批量导出 DWG/DXF）
- [ ] Skill: autocad-dwg
- [ ] Hermes 适配层完成

---

## 5. 给 AI 的关键约束

以下是 AI 在写任何代码时必须遵守的铁律：

1. **优先级固定**：CLI/API > 宏 > 脚本 > GUI > 人工。绝不主动走 GUI。
2. **单一职责**：每个工具只做一件事。不要写"万能工具"。
3. **输出必结构化**：所有工具返回 JSON，包含 `success`/`action`/`summary`/`artifacts`/`warnings`/`errors` 字段。
4. **破坏性动作必确认**：覆盖文件、写入硬件、擦除 Flash 等动作必须显式确认。
5. **全程可追溯**：每次执行记录日志、错误、产物路径、版本信息。
6. **先设计后编码**：先写接口文档和数据模型，确认后再写实现。
7. **一次只做一个闭环**：一个工具 + 一个测试 + 一个示例，不一口气写完整系统。

---

## 6. 项目文件结构速查

```
bifrost/                              ← 项目根（共享 + 社区文档）
├── README.md / SECURITY.md / ...      #   社区标准文档
├── pyproject.toml                     #   共享包配置
├── requirements.txt                   #   Python 依赖
│
├── core/                              # 📁 核心引擎（框架无关，Codex + Hermes 共享）
│   ├── domain.py / actions.py / validators.py / errors.py
│
├── adapters/                          # 📁 工业软件适配器（8 个，框架无关）
│   ├── base.py                        #     BaseAdapter
│   ├── kicad/ keil/ stm32cubeide/ ccs/
│   ├── autocad/ multisim/ solidworks/ stm32/
│
├── tests/                             # 📁 统一测试
├── examples/                          # 📁 示例
│
├── codex-relay/                       # 📁 Codex 专属
│   ├── plugin.json / .mcp.json        #   Codex 插件配置
│   ├── codex_plugin/mcp/              #   MCP Server（Python 包）
│   └── skills/ (9 个 skill 文件夹)     #   Agent Skills
│
├── hermes-relay/                      # 📁 Hermes 专属
│   └── hermes_tools/                  #   Function calling + GOAP
│
└── docs/                              # 📁 技术文档体系
    ├── 00-overview.md … 09-hermes-integration.md
    ├── decisions/ + research-*.md

---

## 7. 当前状态与下一步

| 项目 | 状态 |
|------|------|
| 技术决策 TDR-001（语言） | ✅ 已完成 |
| 架构设计文档 | 🔄 进行中 |
| 数据模型定义 | ⏳ 待开始 |
| 工具接口设计 | ⏳ 待开始 |
| KiCad CLI 调研 | ⏳ 待开始 |
| STM32 CLI 调研 | ⏳ 待开始 |
| 代码实现 | ⏳ 待开始（Phase 1 文档完成后） |

**AI 协作规则**：每当你（AI）被要求写代码时，先确认当前 Phase 的目标文档已经阅读完毕。如果用户跳过设计直接要求实现，请先提醒用户回到设计阶段。
