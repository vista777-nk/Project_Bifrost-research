# 01 — 架构设计详解（AI 可读版）

> **前置阅读**：`00-overview.md`
> **后续阅读**：`02-data-models.md`
> **用途**：定义系统的分层架构、组件职责、数据流向、依赖规则

---

## 1. 架构核心思想

### 1.1 分层隔离原则

```
Layer 0 (上层):  Codex Agent / 用户
Layer 1 (引导层): Skill 文档          ← 纯文本，告诉模型"何时用什么"
Layer 2 (接口层): MCP Server          ← 把 Core 暴露为工具
Layer 3 (核心层): Core                ← 纯 Python，零外部框架依赖
Layer 4 (适配层): Adapters            ← 每个软件一个 adapter，实现统一接口
Layer 5 (底层):   工业软件            ← 真实软件，不在本仓库内
```

**依赖方向**：上层依赖下层，下层绝不依赖上层。

```
Skill → MCP Server → Core ← Adapters → 工业软件
                       ↑        ↑
                  不依赖 Codex  不依赖 Core 之外的任何项目模块
```

### 1.2 核心原则重述

| 编号 | 原则 | 含义 |
|------|------|------|
| P1 | 优先级固定 | CLI/API > 宏 > 脚本 > GUI > 人工 |
| P2 | 单一职责 | 每个工具/函数只做一件事 |
| P3 | 输出结构化 | 所有返回都是 JSON，含必填字段 |
| P4 | 破坏性确认 | 高风险操作必须显式确认 |
| P5 | 全程可追溯 | 日志+错误+产物+版本全记录 |

---

## 2. 各层详细设计

### 2.1 Core 层 (`core/`)

**职责**：提供所有不依赖具体软件、不依赖 Codex 的通用逻辑。

> Core 位于根目录 `core/`，**框架无关**——Hermes 集成时直接从 `core/` 导入。

**子模块**：

| 文件 | 职责 | 关键类/函数 |
|------|------|------------|
| `domain.py` | 数据模型定义 | `Task`, `Action`, `ActionResult`, `ValidationReport` |
| `actions.py` | 动作执行引擎 | `ActionExecutor`, `execute_action()` |
| `workflows.py` | 工作流编排 | `Workflow`, `Step`, `run_workflow()` |
| `validators.py` | 结果校验框架 | `Validator`, `ValidationRule`, `validate()` |
| `errors.py` | 结构化错误体系 | `RelayError`, `ActionFailedError`, `ConfirmationRequiredError` 等 |

**依赖规则**：
- `domain.py` 不依赖任何其他模块
- `errors.py` 只依赖 `domain.py`
- `validators.py` 只依赖 `domain.py`
- `actions.py` 依赖 `domain.py` + `errors.py` + `validators.py`
- `workflows.py` 依赖以上所有

**Core 不做什么**：
- 不知道 Codex 的存在
- 不知道任何具体工业软件
- 不做任何 I/O（文件/网络操作由 adapter 完成）
- 不做任何进程管理

### 2.2 MCP Server 层 (`codex-relay/codex_plugin/mcp/`)

**职责**：把 Core 的能力暴露为 MCP 协议工具，供 Codex 调用。

**子模块**：

| 文件 | 职责 |
|------|------|
| `server.py` | MCP Server 入口，注册工具、启动服务 |
| `tools.py` | 每个工具的实现函数（调用 Core） |
| `schemas.py` | 工具的输入输出 JSON Schema（给 MCP 协议用） |

> **注意**：Core 和 Adapters 位于根目录 `core/` 和 `adapters/`，属框架无关代码。
> 未来 Hermes 集成时，`hermes-relay/` 直接从根目录 `core/` 和 `adapters/` 导入。

**工具列表（第一版）**：

| 工具名 | 功能 | 风险等级 |
|--------|------|---------|
| `list_adapters` | 列出可用适配器及状态 | 低 |
| `run_action` | 执行一个结构化动作 | 中～高（取决于动作） |
| `validate_result` | 校验上一次执行的结果 | 低 |
| `collect_logs` | 收集指定动作的日志 | 低 |
| `confirm_action` | 显式确认高风险动作 | 低（仅做确认） |
| `preview_action` | 预览动作效果（dry-run） | 低 |

**MCP Server 不做什么**：
- 不直接操作文件系统
- 不直接调用工业软件
- 不做业务逻辑判断（全部委托给 Core）

### 2.3 Skill 层 (`codex-relay/skills/`)

**职责**：告诉 Codex 模型"什么时候调用哪个工具""怎么组合""什么时候必须停下来问人"。

每个 Skill 是一个独立文件夹，内含 `SKILL.md`（遵循 Agent Skills 开放标准）：

```
codex-relay/skills/
├── kicad-pcb/SKILL.md          # KiCad PCB 工作流
├── multisim-reader/SKILL.md    # Multisim 电路读取/网表导出
├── cubeide-build/SKILL.md      # STM32CubeIDE 编译/烧录
├── ccs-flash/SKILL.md          # TI CCS 烧录/调试
├── keil-build/SKILL.md         # Keil MDK 编译/烧录
├── solidworks-cad/SKILL.md     # SolidWorks CAD 工作流
├── autocad-dwg/SKILL.md        # AutoCAD DWG 批处理
├── stm32-flash/SKILL.md        # STM32 烧录（向后兼容，推荐 cubeide-build）
└── relay-core/SKILL.md         # 通用中继工具（列出适配器、确认动作等）
```

**Skill 文档结构**（以 `kicad-pcb` 为例）：

```markdown
---
name: kicad-pcb
description: KiCad PCB 工作流 — 打开工程、导出 Gerber/BOM、运行 DRC、收集产物
---

# KiCad PCB 工作流

## 适用场景
- 用户提到 KiCad、PCB、Gerber、DRC、BOM
...

## 标准工作流
### 导出 Gerber + DRC 检查
1. 调用 list_adapters(filter="kicad")
2. 调用 run_action(app="kicad", action_name="open_project", ...)
3. 调用 run_action(app="kicad", action_name="export_gerber", ...)
4. 调用 run_action(app="kicad", action_name="run_drc", ...)
5. 调用 validate_result(...)
6. 调用 collect_logs(...)

## 何时停止问人
- 遇到 ConfirmationRequiredError 时
- DRC 发现错误时（不要自动忽略）
- 连续 3 次重试失败时
```

### 2.4 Adapter 层 (`adapters/`)

**职责**：每个 adapter 实现统一的 `BaseAdapter` 接口，对接具体工业软件。

**统一接口**：

```python
class BaseAdapter(ABC):
    @property
    def name(self) -> str: ...
    @property
    def version(self) -> str: ...
    @property
    def available_actions(self) -> list[str]: ...

    def check_availability(self) -> bool: ...
    def execute(self, action: Action) -> ActionResult: ...
    def validate(self, result: ActionResult) -> ValidationReport: ...
```

**每个 adapter 的内部实现策略**：

| Adapter | 主路径 | 备选路径 | 最后手段 |
|---------|--------|---------|---------|
| KiCad | pcbnew Python API | kicad-cli | ❌ 不做 GUI |
| Keil MDK | UV4 CLI | CMSIS-DAP 调试器 | ❌ 不做 GUI |
| STM32CubeIDE | Eclipse headless CLI | STM32CubeProgrammer CLI | ❌ 不做 GUI |
| CCS | DSS (JavaScript) | Theia CLI / UniFlash CLI | ❌ 不做 GUI |
| AutoCAD | accoreconsole CLI | COM (pywin32) | ❌ 不做 GUI |
| Multisim | COM Automation API (pywin32) | 命令行 netlist 仿真 | ❌ 不做 GUI（.ms14 为专有格式，不可直接解析） |
| SolidWorks | COM (pywin32) | Macro API (.swp) | ❌ 不做 GUI |

---

## 3. 数据流向

### 3.1 正常流程

```
用户 → Codex Agent
  ↓ 读取 Skill 决定调用什么工具
MCP Server.tools.run_action()
  ↓ 参数校验 (schemas.py)
Core.actions.execute_action()
  ↓ 查找 adapter、构建 Action 对象
Adapter.execute(action)
  ↓ 调用工业软件
ActionResult ← 结构化返回
  ↓
Core.validators.validate(result)
  ↓
ValidationReport ← 结构化返回
  ↓
MCP Server → Codex Agent → 用户
```

### 3.2 需要确认的流程

```
... → Adapter.execute() 检测到破坏性操作
  ↓ 抛出 ConfirmationRequiredError
Core.actions 捕获错误
  ↓
MCP Server 返回结构化错误 { "requires_confirmation": true, ... }
  ↓
Codex Agent 根据 Skill 提示，调用 confirm_action 工具
  ↓ 用户确认
MCP Server.confirm_action()
  ↓
Core.actions 重新执行（带确认标记）
  ↓
正常流程继续
```

### 3.3 失败重试流程

```
... → Adapter.execute() 失败
  ↓ 返回 ActionResult(success=False, errors=[...])
Core.actions 检查 retry_policy
  ↓ 如果是 RETRYABLE 错误
自动重试（最多 N 次）
  ↓ 如果是 FATAL 错误
立即返回错误给 Agent
  ↓ 如果是 NEEDS_HUMAN 错误
返回错误 + 建议人工介入
```

---

## 4. 错误体系设计

```python
RelayError (基类)
├── ConfigurationError        # 配置错误（adapter 未安装、路径找不到）
├── ActionFailedError         # 动作执行失败
│   ├── RetryableError        #   可重试（超时、临时故障）
│   ├── FatalError            #   致命（文件损坏、权限不足）
│   └── NeedsHumanError       #   需要人工介入
├── ValidationError           # 校验失败
├── ConfirmationRequiredError # 需要用户确认
└── AdapterNotFoundError      # 适配器不可用
```

每种错误都携带：
- `error_code`: 机器可读的错误码
- `message`: 人类可读的描述
- `suggested_action`: 建议的下一步（retry/abort/check_logs/ask_human）
- `context`: 出错时的上下文快照
- `recoverable`: 是否可自动恢复

---

## 5. 关键设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 编程语言 | Python 3.11+ | 见 TDR-001 |
| 数据校验库 | pydantic v2 | 工业级 JSON Schema，类型安全 |
| MCP 协议 | MCP Python SDK | 官方支持，API 简洁 |
| 测试框架 | pytest + pytest-mock | 最成熟 |
| CLI 框架 | typer | 类型提示驱动，比 argparse 更现代 |
| 日志 | structlog | 结构化日志，方便后续分析 |
| 配置管理 | TOML (pyproject.toml) | Python 生态标准 |

---

## 6. 安全边界

以下操作**绝不**由系统自动执行，必须有人工确认：

1. 覆盖已有工程文件
2. 删除任何文件
3. 写入硬件（烧录 Flash / EEPROM）
4. 擦除存储
5. 批量导出覆盖旧结果
6. 发送生产命令（如控制实际设备运转）

---

## 7. 下一步

读完本文档后，请继续阅读：
- `02-data-models.md` — 每个数据模型的精确字段定义
- `03-tools-design.md` — 每个工具的详细输入输出
