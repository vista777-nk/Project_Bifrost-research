# 05 — 分阶段实现计划（AI 可读版）

> **前置阅读**：`04-plugin-design.md`
> **后续阅读**：`06-testing-strategy.md`
> **用途**：定义每个 Phase 的精确任务、验收标准、依赖关系，让 AI 可以按步骤逐条执行

---

## Phase 0：设计完成（当前）

### 状态：🔄 进行中

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
| 0.8 | 测试策略 | `docs/06-testing-strategy.md` | ⏳ |
| 0.9 | KiCad CLI 调研 | `docs/research-kicad-cli.md` | ⏳ |
| 0.10 | STM32 CLI 调研 | `docs/research-stm32-cli.md` | ⏳ |

---

## Phase 1：最小可用插件（MVP）

### 目标
跑通从 Codex → MCP Server → Core → Mock Adapter 的完整链路。
不连真实工业软件，用 mock 验证架构可行性。

### 任务清单

| # | 任务 | 文件 | 预估工时 | 验收标准 |
|---|------|------|---------|---------|
| 1.1 | 创建 `pyproject.toml` | `codex-relay/pyproject.toml` | 0.5h | `pip install -e .` 成功 |
| 1.2 | 实现 `core/domain.py` | `codex-relay/core/domain.py` | 1h | 所有 pydantic 模型可实例化、可序列化 |
| 1.3 | 实现 `core/errors.py` | `codex-relay/core/errors.py` | 0.5h | 所有错误类可构造，携带上下文字段 |
| 1.4 | 实现 `core/validators.py` | `codex-relay/core/validators.py` | 1h | 校验框架可注册规则、执行校验 |
| 1.5 | 实现 `core/actions.py` | `codex-relay/core/actions.py` | 2h | ActionExecutor 可注册 adapter、执行动作 |
| 1.6 | 实现 Mock Adapter | `codex-relay/adapters/mock_adapter.py` | 1h | 模拟 3 个动作（成功/失败/需确认） |
| 1.7 | 实现 `mcp/server.py` | `codex-relay/codex_plugin/mcp/server.py` | 1h | MCP Server 可启动，注册工具 |
| 1.8 | 实现 `mcp/tools.py` | `codex-relay/codex_plugin/mcp/tools.py` | 2h | 实现 `list_adapters` + `run_action` + `confirm_action` |
| 1.9 | 实现 `mcp/schemas.py` | `codex-relay/codex_plugin/mcp/schemas.py` | 0.5h | JSON Schema 可从 pydantic 模型自动生成 |
| 1.10 | 创建 `plugin.json` + `.mcp.json` | `codex-relay/plugin.json` + `codex-relay/.mcp.json` | 0.5h | 符合 Agent Plugin 标准 |
| 1.11 | 写各软件 SKILL.md | `codex-relay/skills/{kicad-pcb,stm32-flash,relay-core}/SKILL.md` | 2h | YAML frontmatter + 工作流 + 安全规则 |
| 1.12 | 写单元测试 | `codex-relay/tests/test_core.py` | 2h | 覆盖率 > 80% |
| 1.13 | 写集成测试 | `codex-relay/tests/test_mcp_server.py` | 2h | MCP Server 端到端测试通过 |
| 1.14 | 写 README | 根目录 `README.md`（已有） | 0.5h | 与项目结构一致 |

### Phase 1 总预估：~16h
### 产出物：可运行的最小 Codex 插件（Mock 模式）

---

## Phase 2：KiCad 适配器（第一个真实软件）

### 目标
让 Codex 能真正操作 KiCad：打开工程 → 导出 Gerber → 跑 DRC → 收集产物。

### 前置条件
- Phase 1 完成
- KiCad 8.0+ 已安装在开发机上
- `pcbnew` Python 模块可导入

### 任务清单

| # | 任务 | 文件 | 预估工时 | 验收标准 |
|---|------|------|---------|---------|
| 2.1 | 实现 KiCad adapter 基础框架 | `codex-relay/adapters/kicad/adapter.py` | 2h | 继承 BaseAdapter，check_availability 可检测 KiCad 是否安装 |
| 2.2 | 实现 `open_project` | `codex-relay/adapters/kicad/actions_open.py` | 1h | 用 pcbnew.LoadBoard() 打开 .kicad_pcb 文件 |
| 2.3 | 实现 `export_gerber` | `codex-relay/adapters/kicad/actions_export.py` | 2h | 用 pcbnew 导出 Gerber 到指定目录 |
| 2.4 | 实现 `export_bom` | `codex-relay/adapters/kicad/actions_export.py` | 1h | 导出 BOM（CSV 或 XML） |
| 2.5 | 实现 `run_drc` | `codex-relay/adapters/kicad/actions_check.py` | 2h | 运行 DRC，解析结果返回结构化数据 |
| 2.6 | 实现 `collect_artifacts` | `codex-relay/adapters/kicad/actions_collect.py` | 1h | 收集所有输出文件列表 |
| 2.7 | 写 KiCad validator | `codex-relay/adapters/kicad/validators.py` | 2h | 检查文件存在性、大小、DRC 结果 |
| 2.8 | 写集成测试 | `codex-relay/tests/test_kicad_adapter.py` | 3h | 用真实 KiCad 工程测试全流程 |
| 2.9 | 创建示例工程 | `codex-relay/examples/kicad_export_example/` | 1h | 一个最小 KiCad 工程用于测试 |
| 2.10 | 更新 SKILL.md | `codex-relay/skills/kicad-pcb/SKILL.md` | 0.5h | 更新 KiCad 工作流细节 |

### Phase 2 总预估：~15.5h

---

## Phase 3：Keil MDK + STM32CubeMX 适配器

### 目标
让 Codex 能操作 STM32 工具链：CubeMX 生成代码 → Keil 编译 → Keil 烧录 → 校验。

### 前置条件
- Phase 1 完成
- Keil MDK 5.39 已安装（`UV4.exe` 在 PATH）
- STM32CubeMX 6.15.0 已安装
- 至少一块 STM32 开发板 + ST-Link 用于测试

### 3A：STM32CubeMX 子适配器

| # | 任务 | 预估工时 |
|---|------|---------|
| 3A.1 | 调研 CubeMX CLI 脚本语法（实测验证） | 2h |
| 3A.2 | 实现 CubeMX adapter 基础框架 | 1h |
| 3A.3 | 实现 `load_ioc` — 加载 .ioc 配置文件 | 1h |
| 3A.4 | 实现 `generate_code` — 从 .ioc 生成 HAL 代码 | 2h |
| 3A.5 | 实现 `export_config_report` — 导出引脚配置 | 1h |

### 3B：Keil MDK 子适配器

| # | 任务 | 预估工时 |
|---|------|---------|
| 3B.1 | 实现 Keil adapter 基础框架 | 1h |
| 3B.2 | 实现 `build_project` — UV4.exe -b 编译 | 1.5h |
| 3B.3 | 实现 `flash_firmware`（含确认机制）— UV4.exe -f | 2h |
| 3B.4 | 实现 `clean_project` — UV4.exe -c | 0.5h |
| 3B.5 | 实现 `read_build_log` — 解析编译日志 | 1h |
| 3B.6 | 写集成测试 | 3h |
| 3B.7 | 创建示例 Keil 工程 | 1h |

### Phase 3 总预估：~16h

---

## Phase 4：SolidWorks + AutoCAD 适配器

### 目标
两大 CAD 工具适配：SolidWorks 3D 操作 + AutoCAD 2D 图纸。

### 前置条件
- Phase 1 完成
- SolidWorks 2024 SP5 + AutoCAD 2022 已安装
- Windows 环境（COM 依赖）

| # | 任务 | 预估工时 |
|---|------|---------|
| 4.1 | 实现 SolidWorks COM 基础连接 | 1h |
| 4.2 | 实现 `open_document` / `export_step` / `export_pdf` | 3h |
| 4.3 | 实现 AutoCAD COM + accoreconsole 基础连接 | 1h |
| 4.4 | 实现 `open_drawing` / `export_pdf` / `export_dxf` | 2h |
| 4.5 | 实现 SolidWorks ↔ AutoCAD 格式转换桥 | 2h |
| 4.6 | 写集成测试 | 3h |
| 4.7 | 创建示例文件 | 1h |

### Phase 4 总预估：~13h

---

## Phase 5+：Multisim 适配器

### 目标
退化为文件级操作：解析 .ms14 XML，提取电路信息和仿真结果。

（详细计划在 Phase 3/4 完成后细化。Multisim 自动化受限，仅做文件读取。）

---

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
Phase 0 (设计)
    ↓
Phase 1 (MVP: Core + MCP Server + Mock)
    ↓
Phase 2 (KiCad)  ←→  Phase 3 (STM32)  可并行
    ↓                    ↓
Phase 4 (TI + SolidWorks)
    ↓
Phase 5 (Hermes 迁移)
```
