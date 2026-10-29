# Bifrost 项目交接：DeepSeek 与 Kimi

交接日期：2026-10-30（Asia/Shanghai）。后续开发、维护、测试与技术决策由 DeepSeek 和 Kimi 负责。本文依据当前仓库、已有验收产物及本次复查编写，可作为新会话的首读文档。

## 1. 接手结论

Bifrost 是连接 AI Agent 与工业软件的 Python 中继层。当前主链路为：结构化工具调用 → MCP 服务 → 共享核心 → KiCad / Multisim 适配器 → 原生文件与验证结果。

KiCad 8.0.9 和 Multisim 14.3 已通过有限范围的原生电路创建、修改、保存及重新打开验收。支持两引脚 R、C、L、VDC；尚不能宣称覆盖两款软件的全部设计能力。接手后应继续完成电路设计目标，不要将项目缩减为读取、导出或仿真工具。

| 项目 | 交接时状态 |
|---|---|
| 仓库目录 | `F:\linux\Documents\Project_Bifrost-research` |
| 分支与实现基线 | `dev`，实现提交 `1fc85fe`：`feat(circuits): add native KiCad and Multisim authoring` |
| 本次改文档前工作区 | 干净；本地 `origin/dev` 跟踪引用与 `dev` 一致，本次未 fetch 或核实远端服务器状态 |
| 本次测试 | 2026-10-30：186 passed，1 skipped，10 deselected |
| 真实软件验收 | 2026-09-08 记录：10 项通过；本次没有启动软件重新验收 |
| 后续维护责任 | DeepSeek 与 Kimi；本次交接没有替他们创建会话、配置客户端或执行远程授权 |

## 2. 用户要求

以下要求来自用户明确纠正，后续实现应持续遵守：

- 让模型在 KiCad 和 Multisim 中设计、编辑真实电路，返回可继续编辑的原生文件。
- 禁止鼠标、键盘模拟和 GUI 控制，包括以 UIA 等方式绕过限制。采用 CLI、COM、结构化原生文件解析等路线；若确实没有可行路线，应如实告知用户。
- 截图、连接报告或独立 SPICE 文本不能替代原生电路验收。必须重新打开产物，核对元件、参数和连线；仿真结论应有真实数值。
- 变更默认保存到独立修订文件。原始输入不可覆盖，输出覆盖沿用现有明确确认机制；不得靠 `force` 绕过。
- 不能识别的器件、文档结构或版本应明确报错，不能丢弃内容或偷偷换成其他器件。
- Git 提交采用 Conventional Commits。用户提供的身份为 `vista777-nk <1687305011@qq.com>`，保持仓库本地配置，不改全局身份；未经要求不推送。

COM 或 CLI 调用可能让应用自身显示文档，这与模拟桌面输入不同。项目没有实现鼠标、键盘自动化后端。

## 3. 已实现能力和边界

| 范围 | 已实现 | 限制或待办 |
|---|---|---|
| 共享核心 | 动作执行、结果、错误、校验、工作流、产物与校验和 | 全仓库 lint / mypy 尚无全部通过的交接结论 |
| MCP | `list_adapters`、`run_action`、`preview_action`、`confirm_action`、`validate_result`、`collect_logs` | 动作记录及仿真缓存随进程结束而丢失 |
| 两款软件的原理图 | 目录查询、读取、创建；改值、添加、删除、替换、移动、旋转、连接和断开 | 两引脚 R/C/L/VDC、单页；完整拓扑编辑限 Bifrost 创建的文件 |
| KiCad 验证 | CLI 原生重开、引脚/网络比对、ERC | 发布成功不等于 ERC 通过；检查 `metadata.verification.erc_passed` 与 `erc` |
| KiCad PCB | 已有读取、信息、Gerber/BOM 导出、DRC 接口 | 原理图验收不代表 PCB 放置、布线及全部制造导出均已实机验收 |
| Multisim 分析 | COM 连接、元件/输出枚举、连接报告、DC/AC/瞬态仿真及取数 | 报告不是可执行 SPICE 网表；外部相对模型依赖不自动复制 |
| Hermes | 工具定义、提示词等基础结构 | `hermes_tools/tools.py` 执行函数仍有 TODO，未完成可用中继 |
| 其他工业软件 | 规划、研究及目录结构 | Keil、STM32CubeIDE、CCS、AutoCAD、SolidWorks 不能仅凭目录存在视为可用 |

尚不支持任意厂商库、运放/晶体管等更多器件、层次原理图和总线。支持的外部导入设计主要允许改值。经原软件另存后，Bifrost 标记可能被改写，后续拓扑编辑会按导入文件限制处理。拓扑变更会重新布线；纯改值应保留既有连线、元件记录及未改变的位置。

### 动作参数

两款软件均通过 `run_action(app="kicad" 或 "multisim", action_name=..., parameters=...)` 调用：

| 动作 | 参数 |
|---|---|
| `find_components` | 可选 `query`；返回目录及 `action_parameters` JSON Schema |
| `inspect_schematic` | `input_file`；返回 `circuit` 与 `input_sha256` |
| `create_schematic` | `output_file`、`circuit` |
| `edit_schematic` | `input_file`、不同的 `output_file`、`expected_input_sha256`、`changes` |

元件字段为 `reference`、`kind`、数值型 SI `value`、可选毫米坐标 `x_mm/y_mm`、`rotation` 和 `pins`。引脚键为字符串 `"1"/"2"`，网络 `"0"` 表示地，`null` 表示未连接；旋转为 0/90/180/270 度。最多 128 个元件，每次 1–256 项编辑。新位置按原软件网格归整；值应传 `10000`，不能传 `"10k"`。

编辑 `op` 为 `set_value`、`add`、`remove`、`replace`、`move`、`rotate`、`connect`、`disconnect`。先读取返回的 Schema：Multisim 旧读取/仿真动作用 `file_path`，原生编辑动作用 `input_file`。此前新会话曾混用并失败，目录查询已补充 Schema。

预览验证参数并返回语义前后对比，但原生验证仍需执行。编辑需要最新输入哈希；输入在检查或验证期间变化时不得发布修订。

## 4. 代码入口

| 文件或目录 | 用途 |
|---|---|
| [core/circuits.py](../core/circuits.py) | 电路/编辑模型、约束、原子发布；非覆盖路径使用排他创建 |
| [core/circuit_geometry.py](../core/circuit_geometry.py) | 基于 NetworkX 的有界正交布线、障碍物与交叉处理 |
| [adapters/authoring.py](../adapters/authoring.py) | 共享输入校验、预览、哈希检查、暂存与发布边界 |
| [adapters/kicad/schematic.py](../adapters/kicad/schematic.py) | KiCad 8 S-expression 解析、符号/连线生成、CLI/ERC 验证 |
| [adapters/multisim/schematic.py](../adapters/multisim/schematic.py) | schema 67 对象、端口、连线和修订验证 |
| [worker.ps1](../adapters/multisim/worker.ps1) | 隔离的 32 位 STA COM 进程，JSON 输入/输出 |
| [xmlio.py](../adapters/multisim/xmlio.py) | 保留原生 XML 属性内的 SPICE 换行、制表符 |
| [codec.py](../adapters/multisim/codec.py)、[codec.mjs](../adapters/multisim/codec.mjs) | 有界容器解码/编码，Node 依赖位于本机资源目录 |
| [setup_authoring.py](../adapters/multisim/setup_authoring.py)、[native_probes.py](../adapters/multisim/native_probes.py) | 本机模板生成、原生探针及其引用关系 |
| [MCP 目录](../codex-relay/codex_plugin/mcp/) | 服务、六个工具、确认状态、结果保存与重试 |
| [local_setup.py](../codex-relay/codex_plugin/local_setup.py) | 生成本机插件副本及绝对路径配置 |
| [tests/](../tests/) | 单元、发布边界、MCP、两款软件集成测试 |
| [verify_native_authoring.py](../scripts/verify_native_authoring.py) | 通过真实 MCP 配置生成两款软件的验收产物 |

电路约束、编辑能力和原生验证继续放在共享核心及适配器中，便于不同客户端复用，不要复制到各模型提示词或多套执行器中。

## 5. 本机环境和模型接入

2026-10-30 已确认运行解释器、KiCad CLI、Multisim 可执行文件、资源清单、已有 MCP 配置及历史验收报告仍存在。文件存在不代表本次验证了软件许可和连接。

| 项目 | 路径或记录 |
|---|---|
| Python | 仓库内 `.venv-codex\Scripts\python.exe`；本次测试显示 Python 3.11.5 |
| KiCad GUI / CLI | `E:\KiCad\8.0\bin\kicad.exe` / `kicad-cli.exe`；历史验收版本 8.0.9 |
| Multisim | `C:\Program Files (x86)\National Instruments\Circuit Design Suite 14.3\Multisim.exe` |
| Multisim COM | `MultisimInterface.MultisimApp`；32 位进程内 COM |
| COM 宿主 | `C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe`，STA |
| 正确本机资源包 | `.bifrost-authoring/runtime/`；`BIFROST_AUTHORING_HOME` 指向其绝对路径 |
| Node 依赖 | `runtime/node/node_modules/electronics-workbench-decoder`，既有配置固定为 `0.2.0` |
| 本机插件源 | `C:\Users\linux\plugins\codex-relay` |
| 已有 MCP 配置 | `C:\Users\linux\plugins\codex-relay\.mcp.json` |
| 插件安装历史 | `codex-relay@personal`，`0.1.0+codex.20260907215622`；本次未重新核对安装缓存 |

`.venv-codex` 基于 KiCad 自带 Python，以 `--system-site-packages` 创建。不要随意换成系统 Anaconda 解释器；根包和 `codex-relay` 分别以 editable 安装。Node 需能在进程 PATH 中找到。

DeepSeek 和 Kimi 的维护身份不依赖 Codex 插件。若实际客户端支持本地 stdio MCP，可读取已有 `.mcp.json` 中 `bifrost-codex` 的 `command`、`args`、`env`，按该客户端格式注册同一服务。服务入口仍为：

```powershell
$env:PYTHONUTF8 = '1'
$env:BIFROST_KICAD_CLI = 'E:\KiCad\8.0\bin\kicad-cli.exe'
$env:BIFROST_AUTHORING_HOME = (Resolve-Path .bifrost-authoring/runtime).Path
.\.venv-codex\Scripts\python.exe -m codex_plugin.mcp.server
```

这是等待客户端通信的 stdio 服务，不是立即结束的诊断命令。stdout 应保持协议输出，诊断走 stderr。客户端配置还应保留已有配置中的 KiCad PATH 设置。

本次没有验证具体 DeepSeek/Kimi 客户端的 MCP 支持，也未配置 API、账号或密钥。若客户端不支持本地工具调用，可先用仓库脚本开发验证，再实现桥接；不能据此声称 Hermes 已经可用。

`runtime/components/` 从用户合法安装生成，不随 Git 或 wheel 分发。旧 `.bifrost-authoring/components/` 是诊断数据，不应替代正确资源包。换机器按 [环境安装说明](CODEX_SETUP.md) 重建；已有模板不要重复初始化覆盖。

## 6. 验证方法与证据

### 本次重新验证

在仓库根目录执行：

```powershell
.\.venv-codex\Scripts\python.exe -m pytest tests/ -q -m 'not hardware'
```

2026-10-30 结果：**186 passed，1 skipped，10 deselected**。这是本机非硬件回归，不包含当天的实机操作，也不代表所有平台、lint、类型检查通过。CI 配置为 Ubuntu/Windows、Python 3.11/3.12 的非硬件测试；本次未查询远端 CI。

### 既有实机记录

2026-09-08 记录为 10 项实机测试通过。本次读取现存 [verification.json](../output/native-acceptance-verified/verification.json) 核对了以下内容：

- 两款软件各有创建、R2 改值、添加电容、删除电容四个原生修订。
- KiCad 四个修订均记录 `native_reopen=true`、`erc_passed=true`。
- Multisim 初始输出 `2.4999999875 V`，R2 修改后 `3.333333311111111 V`；添加、删除电容后的 DC 仍为后者。
- 报告记录先前修订哈希保留；本次未重新计算全部产物哈希。
- 当时另有移动、旋转、替换、断开/重连测试。KiCad 故意断开时报告 `label_dangling`，重连后 ERC 恢复通过。

本机忽略的 `output/native-acceptance-verified/` 保存最终 MCP 报告和原生修订；`output/native-acceptance-20260908/` 还有原生导出图及 `codex-verified.jsonl`。Git 新克隆不会自带这些文件。

### 接手后复跑

先复跑非硬件测试和 MCP 冒烟：

```powershell
.\.venv-codex\Scripts\python.exe -m codex_plugin.mcp.smoke --config "$HOME\plugins\codex-relay\.mcp.json"
```

需要实机验收时，使用全新输出目录；脚本会创建文件并通过 CLI/COM 调用应用：

```powershell
$handoffOutput = Join-Path 'output' ('handoff-' + [guid]::NewGuid().ToString('N'))
.\.venv-codex\Scripts\python.exe scripts/verify_native_authoring.py --config "$HOME\plugins\codex-relay\.mcp.json" --output-dir $handoffOutput
```

完整实机测试开关如下；项目的 `hardware` 标记也包含桌面软件集成：

```powershell
$env:BIFROST_KICAD_TEST_CLI = 'E:\KiCad\8.0\bin\kicad-cli.exe'
$env:BIFROST_MULTISIM_AUTHORING_TEST_HOME = (Resolve-Path .bifrost-authoring/runtime).Path
$env:BIFROST_MULTISIM_TEST_CIRCUIT = 'C:\Users\Public\Documents\National Instruments\Circuit Design Suite 14.3\samples\LabVIEW Multisim API Toolkit\Using Analyses\Using Analyses.ms14'
.\.venv-codex\Scripts\python.exe -m pytest tests/ -q -m hardware
```

仅在环境缺失时按安装文档重建，不必为了接手重装已有软件。变更后按影响补测试，记录命令、结果和原生产物。

## 7. 容易重新踩到的问题

1. **XML 属性空白。** Multisim 将 SPICE 换行字面量存入属性，普通 XML 解析会将其归一为空格，使 `.model` 与元件语句拼接，导致文件可打开但仿真错误。原生字节必须经过 `xmlio.py` 的保护/恢复，再用 lxml 做语义编辑。
2. **COM 位数。** MCP/Python 可为 64 位，Multisim COM 必须由 32 位 STA 宿主调用。子进程直接启动 SysWOW64 PowerShell，核对 `worker_bits=32`；仅设置外层 shell 路径曾未能保证位数。
3. **引脚身份。** 以 Multisim 电气 `PortID` 和完整变换矩阵为准，不能用隐藏/显示的引脚文字替代。
4. **仿真取数。** 先枚举实际输出名，再按对应动作 ID 取数。最多缓存 16 次成功仿真，重启即丢失；不能把旧动作数据认作本次结果。
5. **重开与 ERC。** COM 使用绝对文件路径。KiCad ERC 需要实际临时项目和库表；看 JSON 违规，不能仅看进程退出或文件生成。
6. **布线。** 保留坐标舍入、水平/垂直交叉处理，避免浮点边界让引脚落入障碍物，或将无连接的交叉误合并。
7. **失败路线。** 历史 `.cir` 经 Multisim `OpenFile` 导入曾触发原生失败，不是生产路径；不要反复使用它，也不要据此引入桌面控制。停止中的电路不要无条件 `StopSimulation`。
8. **许可和发布。** 本机厂商模板不进 Git；来源和许可见 [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md)。wheel 包含 `worker.ps1`、`codec.mjs` 与许可，但不能包含 NI XML 或用户设计。

## 8. 建议接手顺序

1. 阅读本文、[原生电路手册](10-circuit-authoring.md) 和 [TDR-002](decisions/TDR-002-circuit-authoring-scope.md)，复现非硬件和实机基线，保留新验收目录。
2. 在实际 DeepSeek/Kimi 开发客户端接入同一 MCP，验证六个工具、Schema、预览、创建/编辑、确认和取数；客户端接入结果单独记录。
3. 优先扩大真实工程编辑：完善原软件另存后的身份识别、导入工程拓扑编辑及未知内容保留。先选具体范围与样例，不能移除拒绝检查来伪造兼容性。
4. 按需求扩展器件、模型和引脚数。每个家族应有真实符号、持久化编辑、连接比对和电气验收；共用模型目前只有两引脚，不能只加库名。
5. 补充 KiCad PCB 制造导出的实机示例及独立验收，逐步处理 lint / 类型债务。Hermes 和其他软件适配器按用户后续优先级投入。

DeepSeek 与 Kimi 自行协调实现、审查和集成，避免同时改同一文件后互相覆盖。每项实际开发交付代码、相应验证及 CHANGELOG；提交说明写清能力范围。更早记录的 Ruff 78 项、mypy 13 项属于历史基线，本次未重新测量，不能假定仍是这些数量。

## 9. 文档优先级与历史

接手阅读顺序：本文 → [原生电路手册](10-circuit-authoring.md) → [TDR-002](decisions/TDR-002-circuit-authoring-scope.md) → [Multisim 说明](MULTISIM_SETUP.md) → [环境安装](CODEX_SETUP.md) → 对应代码和测试。

旧 [HANDOFF.md](HANDOFF.md) 保留多轮调研和恢复过程，较早的“未实现”“审批阻断”等段落不能当成当前状态。[总体计划](05-implementation-plan.md) 与 [Phase 1 顺序](decisions/Phase-1-execution-order.md) 包含实现前任务、旧路径及估算；冲突时核对代码、最新测试和用户明确要求。

关键提交：`ec9b539`（MCP/确认边界）、`0de5ba5`（本机插件/stdio）、`3ad7f23`（Multisim 32 位 COM）、`54d3b86`（恢复原生设计验收要求）、`ebe5ad1`（非 GUI XML 路线）、`1fc85fe`（两款软件原生编辑）。

可作为 DeepSeek/Kimi 的首条接手指令：

> 请先读 `docs/HANDOFF_DEEPSEEK_KIMI.md`，以 `1fc85fe` 为实现基线核对当前仓库。继续实现 KiCad 与 Multisim 原生电路设计和编辑，遵守不使用鼠标键盘/GUI 控制的约束。先复现现有测试和验收，再按交接文档推进具体任务；保留用户文件和已有修改，明确报告能力限制、测试结果及下一项工作。
