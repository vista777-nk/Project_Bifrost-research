# 05 — 分阶段实现计划（AI 可读版）

> **前置阅读**：`04-plugin-design.md`
> **后续阅读**：`06-testing-strategy.md`
> **用途**：定义每个 Phase 的精确任务、验收标准、依赖关系，让 AI 可以按步骤逐条执行

---

## Phase 0：设计完成

### 状态：✅ 已完成

### 任务清单

| # | 任务 | 产物 | 状态 |
|---|------|------|------|
| 0.1 | 技术决策：语言选择 | `docs/decisions/TDR-001-语言选择.md` | ✅ |
| 0.2 | 项目总览文档 | `docs/00-overview.md` | ✅ |
| 0.3 | 架构设计文档 | `docs/01-architecture.md` | ✅ |
| 0.4 | 数据模型定义 | `docs/02-data-models.md` | ✅ |
| 0.5 | 工具接口设计 | `docs/03-tools-design.md` | ✅ |
| 0.6 | 插件层设计 | `docs/04-plugin-design.md` | ✅ |
| 0.7 | 实现计划 | `docs/05-implementation-plan.md` | ✅（本文件） |
| 0.8 | 测试策略 | `docs/06-testing-strategy.md` | ✅ |
| 0.9 | KiCad CLI 调研 | `docs/research-kicad-cli.md` | ✅ |
| 0.10 | STM32 CLI 调研 | `docs/research-stm32-cli.md` | ✅ |

---

## Phase 1：最小可用插件（MVP）

### 目标
跑通从 Codex → MCP Server → Core → Mock Adapter 的完整链路。
不连真实工业软件，用 mock 验证架构可行性。

### 任务清单

| # | 任务 | 文件 | 预估工时 | 验收标准 |
|---|------|------|---------|---------|
| 1.1 | 实现 `core/domain.py` | `core/domain.py` | 1.5h | 所有 pydantic 模型可实例化、可序列化 |
| 1.2 | 实现 `core/errors.py` | `core/errors.py` | 0.5h | 所有错误类可构造，携带上下文字段 |
| 1.3 | 实现 `core/validators.py` | `core/validators.py` | 1h | 校验框架可注册规则、执行校验 |
| 1.4 | 实现 `core/actions.py` | `core/actions.py` | 2h | ActionExecutor 可注册 adapter、执行动作 |
| 1.5 | 实现 `adapters/base.py` | `adapters/base.py` | 1h | BaseAdapter 抽象接口 |
| 1.6 | 实现 Mock Adapter | `adapters/mock_adapter.py` | 1h | 模拟 3 种动作（成功/失败/需确认） |
| 1.7 | 实现 MCP Server | `codex-relay/codex_plugin/mcp/{server,tools,schemas}.py` | 3h | 实现 6 个工具，stdio 可启动 |
| 1.8 | 创建 `plugin.json` + `.mcp.json` | `codex-relay/plugin.json` + `codex-relay/.mcp.json` | 0.5h | 符合 Agent Plugin 标准 |
| 1.9 | 实现 KiCad adapter | `adapters/kicad/{adapter,actions_*,validators}.py` | 4h | 打开工程 / 导出 Gerber / 导出 BOM / DRC |
| 1.10 | 实现 Multisim adapter | `adapters/multisim/adapter.py` | 3h | COM Automation：读取电路 / 导出网表 / 运行仿真 |
| 1.11 | 写 Skill 文档 | `codex-relay/skills/{kicad-pcb,multisim-reader,relay-core}/SKILL.md` | 2h | YAML frontmatter + 工作流 + 安全规则 |
| 1.12 | 写单元测试 | `tests/test_core.py` + `tests/test_mock_adapter.py` | 2h | 覆盖率 > 80% |
| 1.13 | 写集成测试 | `tests/test_mcp_server.py` | 2h | MCP Server 端到端测试通过 |
| 1.14 | 创建 KiCad 示例工程 | `examples/kicad_export_example/` | 1h | 最小 KiCad 工程用于测试 |

### Phase 1 总预估：~23.5h
### 产出物：Core + MCP Server + KiCad + Multisim 可用插件

---

## Phase 2：STM32CubeIDE + CCS（MCU 开发环境）

### 目标
Codex 能操作 STM32CubeIDE 和 CCS：工程管理 → 编译 → 烧录 → 校验。

### 前置条件
- Phase 1 完成
- STM32CubeIDE 1.17+ 已安装
- CCS 12.8+ 已安装
- STM32 开发板 + TI LaunchPad 可用于测试

### 任务清单

| # | 任务 | 文件 | 预估工时 | 验收标准 |
|---|------|------|---------|---------|
| 2.1 | 实现 STM32CubeIDE adapter | `adapters/stm32cubeide/adapter.py` | 2h | Eclipse headless CLI 导入/编译/烧录 |
| 2.2 | 实现 CCS adapter | `adapters/ccs/adapter.py` | 2h | Theia CLI + DSS 识别/烧录/调试 |
| 2.3 | 写 Skill 文档 | `codex-relay/skills/{cubeide-build,ccs-flash}/SKILL.md` | 1.5h | 含 GOAP 模板 |
| 2.4 | 写集成测试 | `tests/test_stm32cubeide.py` + `tests/test_ccs.py` | 3h | 真实硬件测试 |

### Phase 2 总预估：~8.5h

> **注**：`adapters/stm32/` 仅为向后兼容占位目录，不投入开发。自 Phase 2 起，STM32 烧录能力统一由 `adapters/stm32cubeide/`（STM32CubeProgrammer CLI / pyocd 路径）提供。

---

## Phase 3：Keil MDK

### 目标
Codex 能操作 Keil MDK：编译工程 → 烧录 → 调试。

| # | 任务 | 文件 | 预估工时 |
|---|------|------|---------|
| 3.1 | 实现 Keil adapter | `adapters/keil/adapter.py` | 2h |
| 3.2 | 写 Skill 文档 | `codex-relay/skills/keil-build/SKILL.md` | 1h |
| 3.3 | 写集成测试 | `tests/test_keil.py` | 2h |

### Phase 3 总预估：~5h

---

## Phase 4：SolidWorks

| # | 任务 | 文件 | 预估工时 |
|---|------|------|---------|
| 4.1 | 实现 SolidWorks adapter（COM） | `adapters/solidworks/adapter.py` | 3h |
| 4.2 | 写 Skill 文档 | `codex-relay/skills/solidworks-cad/SKILL.md` | 1h |

### Phase 4 总预估：~4h

---

## Phase 5：AutoCAD + Hermes 迁移

| # | 任务 | 文件 | 预估工时 |
|---|------|------|---------|
| 5.1 | 实现 AutoCAD adapter | `adapters/autocad/adapter.py` | 2h |
| 5.2 | 写 Skill 文档 | `codex-relay/skills/autocad-dwg/SKILL.md` | 1h |
| 5.3 | Hermes 适配层完成 | `hermes-relay/hermes_tools/` | 2h |

## 任务执行规范（给 AI 的指令）

当你（AI）被要求执行某个 Phase 的某个任务时：

1. **先读相关文档**：确认数据模型和接口定义
2. **一次只做一个任务**：完成一个再开始下一个
3. **每个任务产出三个东西**：
   - 代码文件
   - 对应的测试
   - 一行 CHANGELOG 条目
4. **任务完成后运行测试**：`pytest tests/ -v` 确保没有回归
5. **如果测试失败**：先分析失败原因，再修复，不要猜测
6. **禁止的行为**：
   - 不要一次写多个不相关的文件
   - 不要跳过测试直接提交
   - 不要修改 Phase 范围外的代码
   - 不要在没有理解文档的情况下开始写代码

---

## 依赖关系图

```
Phase 0 (设计 ✅)
    ↓
Phase 1 (Core + MCP Server + KiCad + Multisim)
    ↓
Phase 2 (STM32CubeIDE + CCS)  ←→  Phase 3 (Keil MDK)  可并行
    ↓
Phase 4 (SolidWorks)
    ↓
Phase 5 (AutoCAD + Hermes 迁移)
```
