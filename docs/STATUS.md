# Bifrost 当前状态（唯一事实源）

> **权威性**：本文件是仓库“当前能力、验证结果与工程债”的唯一事实源。
> 最近核实：2026-10-30（DeepSeek）。接手基线：`b7a7042`（`dev`，与本地 `origin/dev` 一致）；
> 本治理提交之后的 HEAD 以 `git log -1` 为准。
> 更新规则：任何能力声明必须附命令、日期与证据路径；没有当天实机运行就写“未验证”。
> 历史记录：[HANDOFF_DEEPSEEK_KIMI.md](HANDOFF_DEEPSEEK_KIMI.md)（2026-10-30 快照）、
> [HANDOFF.md](HANDOFF.md)（更早记录）。两者不再代表当前状态。

## 1. 项目与产品门槛

Bifrost 是 AI Agent 与工业软件之间的中继适配层：
结构化动作 → MCP Server → 共享核心 → 适配器 → 原生文件与验证结果。

产品门槛由 [TDR-002](decisions/TDR-002-circuit-authoring-scope.md) 定义：
必须在 **KiCad 与 Multisim 中创建、编辑并重新打开真实原生电路**。
当前结论：**有限范围已通过，整体目标未完成**。不得表述为两款软件的全部设计能力已自动化。

## 2. 2026-10-30 复核事实

| 项目 | 结果 | 命令 / 证据 |
|---|---|---|
| 非硬件测试 | **186 passed, 1 skipped, 10 deselected**（5.19s） | `.\.venv-codex\Scripts\python.exe -m pytest tests/ -m "not hardware"` |
| 实现基线 | `1fc85fe` `feat(circuits): add native KiCad and Multisim authoring` | `git log --oneline` |
| 文档交接提交 | `b7a7042` `docs: hand over project to DeepSeek and Kimi` | 当前 `dev` HEAD |
| 工作区 | 干净，`dev...origin/dev` 无差异 | `git status --short --branch` |
| Ruff | **75 findings**：hermes-relay 46 / tests 26 / adapters 2 / core 1；15 项可自动修复 | `.\.venv-codex\Scripts\ruff.exe check . --output-format concise` |
| mypy（core） | **29 errors / 7 files**（检查 8 个源文件） | `.\.venv-codex\Scripts\python.exe -m mypy core/` |
| 构建产物跟踪 | `build/`、`*.egg-info/`、`output/` 均未被 Git 跟踪 | `git ls-files` 过滤 |
| 实机验收 | **本次未重跑**；引用 2026-09-08 的 10 项记录 | `output/native-acceptance-verified/verification.json` |
| 远端 CI | 未查询当日结果 | `.github/workflows/test.yml`（Ubuntu/Windows × Python 3.11/3.12，非硬件） |

## 3. 能力矩阵

| 范围 | 状态 | 已验证内容 | 边界 / 未验证 |
|---|---|---|---|
| 共享核心 `core/` | ✅ | 动作执行、结果、错误、校验、工作流、产物校验和、原子发布 | mypy 29 项债务；全仓库 lint 未清零 |
| MCP 六个工具 | ✅ | `list_adapters`、`run_action`、`preview_action`、`confirm_action`、`validate_result`、`collect_logs`；单测与进程内集成 | 动作记录与仿真缓存随进程结束丢失；未在 DeepSeek/Kimi 客户端做当日接入记录 |
| KiCad 原理图 | ✅ 有限 | 两引脚 R/C/L/VDC、单页；创建、检查、改值、增删、替换、移动、旋转、连断；CLI 重开、网络比对、ERC | 任意厂商库、运放/晶体管、层次图、总线未支持；导入工程仅支持改值 |
| Multisim 原理图 | ✅ 有限 | 同左，schema 67；32 位 COM 验证元件、RLC 值与连通性 | 同上；依赖本机生成的组件/探针包，不随仓库分发 |
| Multisim 分析 | ✅ | COM 连接、元件/输出枚举、连接报告、DC/AC/瞬态仿真与取数 | 报告不是可执行 SPICE 网表；相对外部模型不自动复制；最多缓存 16 次成功仿真 |
| KiCad PCB | ⚠️ 接口存在 | 读取、信息、Gerber/BOM 导出、DRC 接口 | 本轮未做实机验收；不等于已有布局/布线自动化 |
| Hermes | ❌ | 工具定义、提示词、GOAP 模板等脚手架 | `hermes_tools/tools.py` 执行函数仍有 TODO，不可宣称可用 |
| Keil / STM32CubeIDE / CCS / AutoCAD / SolidWorks | ❌ | 目录、研究与规划 | 仅目录存在，不能视为可用适配器 |

## 4. 已知工程债

1. **Ruff 75 项**：主要在 Hermes 脚手架（46）与测试（26）；core/adapters 仅 3 项。
2. **mypy 29 项**：`core/` 的泛型参数与返回注解缺失为主。
3. **实机回归未在今日重跑**：10 个 `hardware` 标记测试被 deselect；历史验收不能替代今日结论。
4. **`.gitattributes` 把 `*.kicad_sch`、`*.kicad_pro` 标为 binary**：
   会隐藏原生原理图的文本 diff，影响审查；需要单独评估并验证重新规范化。
5. **`examples/` 仍保留 `.gitkeep`**：实际已有 `voltage-divider.json` 与 `divider.cir`，可清理。
6. **命名遗留**：`codex-relay/` 与文档中的 Codex 表述是历史客户端命名，
   当前 DeepSeek/Kimi 通过同一 stdio MCP 入口复用，不代表范围缩小。
7. **文档密度高**：`docs/` 中另有 23 份历史文档（交接、计划与调研）。
   本文件与 `WORKBOARD.md` 是唯一当前入口，其余按历史资料对待。

## 5. 环境事实（本机）

| 项目 | 路径 / 值 |
|---|---|
| Python | `.venv-codex\Scripts\python.exe`（3.11.5，基于 KiCad 自带解释器） |
| KiCad CLI | `E:\KiCad\8.0\bin\kicad-cli.exe`（历史验收版本 8.0.9） |
| Multisim | `C:\Program Files (x86)\National Instruments\Circuit Design Suite 14.3\Multisim.exe` |
| Multisim COM | `MultisimInterface.MultisimApp`，必须由 32 位 STA 宿主调用 |
| 本机 MCP 配置 | `C:\Users\linux\plugins\codex-relay\.mcp.json` |
| 本机资源包 | `.bifrost-authoring/runtime/`（`BIFROST_AUTHORING_HOME` 指向其绝对路径） |

文件存在不等于许可有效或软件可用；实机结论必须重新运行。

## 6. 后续优先级

| 优先级 | 事项 | 理由 |
|---|---|---|
| P1 | 在 DeepSeek/Kimi 实际客户端接入同一 MCP，记录六个工具、Schema 与创建/编辑/取数 | 交接文档 §8.2；目前只有 Codex 历史接入记录 |
| P1 | 明确“导入工程拓扑编辑”的范围、样例与失败模式 | 最接近真实工程价值；必须保持未知内容不丢失 |
| P2 | 分批清理 Ruff 与 mypy 债务（先 core/adapters，再 tests，最后 Hermes） | 降低回归与审查成本，不改变行为 |
| P2 | KiCad PCB 制造导出的独立实机验收 | 原理图验收不代表 PCB 能力 |
| P3 | 器件家族扩展（先由用户指定真实需求） | 不能只加库名；每个家族需符号、持久化、连通性与电气验收 |
| P3 | Hermes 执行层：完成或明确冻结 | 目前是半成品，需用户决定投入或降级 |

## 7. 需用户决策

1. 先做 P1 的哪一项：客户端 MCP 接入，还是导入工程拓扑编辑？
2. 是否允许把当前本地提交推送到 `origin/dev`（默认不推送）。
3. Kimi 的客户端是否支持本地 stdio MCP；若不支持，采用何种桥接方式。
4. Hermes 是继续投入还是明确冻结。

## 8. 本文件的维护规则

- 只写**已复现**的事实；每条能力变化附日期、命令、结果与产物路径。
- 不复制历史过程；过程留在 `WORKBOARD.md` 与提交信息中。
- 与代码或测试冲突时，以可复现命令为准，并立即修正本文件。
- 结构性改写需 DeepSeek 与 Kimi 双方同意；纪律文件（`AGENTS.md`、
  `COLLABORATION.md`）的修改需用户批准。
