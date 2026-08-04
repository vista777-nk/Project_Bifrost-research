# Phase 1 推荐执行顺序

> 生成日期：2026-08-05
> 来源：全流程全要素检查报告 → 阻断性问题修复后的最终版执行计划
> 总预估工时：~24.5h

---

## Step 1: 环境准备（5 min）

```bash
pip install -e ".[dev]"          # 安装 pytest/ruff/mypy
pip install -e ".[codex]"        # 安装 MCP SDK v2 + typer
pytest tests/test_smoke.py -v    # 确认冒烟测试通过
```

---

## Step 2: Core 层（严格按依赖顺序，TDD）

每个模块：先写测试 → 测试失败 → 写实现 → 测试通过 → 下一个

| 顺序 | 模块 | 测试先行 | 关键产出 |
|:---:|------|---------|---------|
| 2a | `tests/test_core.py` — TestDomainModels | ✅ | Task/Action/ActionResult/Artifact/ValidationReport/AdapterInfo + 4 枚举 |
| 2b | `core/domain.py` | ← 2a | 5 个 pydantic 模型可实例化、可序列化。**注意**：Action 含 `risk_level`(RiskLevel枚举) + `permission_note`；Artifact 为一级公民（name/artifact_type/created_by 字段） |
| 2c | `core/errors.py` | ← 扩展 2a | RelayError/ConfirmationRequiredError 等 6+ 错误类 |
| 2d | `core/validators.py` | ← 扩展 2a | Validator/ValidationRule/validate() |
| 2e | `core/actions.py` | ← 扩展 2a | ActionExecutor（注册 adapter、执行、重试） |
| 2f | `core/workflows.py` | ← 扩展 2a | Workflow/Step/run_workflow()。Step 含 input_artifacts/output_artifacts |

依赖链：`domain → errors → validators → actions → workflows`

---

## Step 3: Adapter 层

| 顺序 | 模块 | 说明 |
|:---:|------|------|
| 3a | `adapters/base.py` | BaseAdapter 抽象接口（含 prepare/execute/validate/rollback 生命周期） |
| 3b | `adapters/mock_adapter.py` | 模拟 3 种动作（成功/失败/需确认） |
| 3c | `tests/test_mock_adapter.py` | Mock adapter 测试 |
| 3d | `adapters/kicad/adapter.py` | pcbnew + kicad-cli：open_project / export_gerber / export_bom / run_drc |
| 3e | `adapters/multisim/adapter.py` | COM Automation：read_circuit / export_netlist / run_simulation |

---

## Step 4: MCP Server 层

| 顺序 | 模块 | 说明 |
|:---:|------|------|
| 4a | `codex_plugin/mcp/schemas.py` | pydantic → JSON Schema 导出 |
| 4b | `codex_plugin/mcp/tools.py` | 6 个 MCP 工具（`@mcp.tool()` v2 API） |
| 4c | `codex_plugin/mcp/server.py` | `MCPServer("bifrost-codex")` + `mcp.run()` |
| 4d | `tests/test_mcp_server.py` | MCP 端到端集成测试 |

---

## Step 5: 示例 + 最终验证

| 顺序 | 任务 | 说明 |
|:---:|------|------|
| 5a | `examples/kicad_export_example/` | 最小 KiCad 工程（一个电阻 + 一条走线） |
| 5b | `pytest tests/ -v` | 全量测试 |
| 5c | `ruff check . && mypy core/` | Lint + 类型检查 |

---

## AI 协作规则（每步必遵守）

1. 先读相关文档，确认数据模型和接口定义
2. 一次只做一个任务，完成一个再下一个
3. 每个任务产出三件套：代码 + 测试 + CHANGELOG 行
4. 完成后运行 `pytest tests/ -v` 确保无回归
5. 测试失败则分析原因再修复，不要猜测
6. 禁止：一次写多个不相关文件 / 跳过测试 / 跨 Phase 修改
