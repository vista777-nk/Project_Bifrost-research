# 06 — 测试策略（AI 可读版）

> **前置阅读**：`05-implementation-plan.md`
> **用途**：定义测试分层、测试方法、必须覆盖的场景、CI 配置

---

## 1. 测试分层

```
┌─────────────────────────────┐
│    E2E 测试 (端到端)          │  ← 真实软件 + 真实 Codex Agent
├─────────────────────────────┤
│    集成测试                   │  ← MCP Server + Core + Adapter (可 Mock)
├─────────────────────────────┤
│    单元测试                   │  ← 每个模块独立测试
└─────────────────────────────┘
```

---

## 2. 单元测试

### 2.1 Core 层测试

**文件**：`tests/test_core.py`

| 测试类 | 测试内容 | 关键场景 |
|--------|---------|---------|
| `TestDomainModels` | 数据模型创建和序列化 | 所有字段正确赋值、model_dump 输出正确 JSON、非法字段被拒绝 |
| `TestErrors` | 错误体系 | 每种 Error 类可构造、context/suggested_action 字段不丢失 |
| `TestValidators` | 校验框架 | 正常通过、单项失败、全部失败、空产物列表 |
| `TestActionExecutor` | 动作执行引擎 | 成功执行、失败执行、需确认、超时、重试 |
| `TestWorkflows` | 工作流编排 | 单步工作流、多步顺序执行、步骤失败时终止 |

> **Phase 1 TDD 执行顺序**：上述测试类严格按 Core 层依赖顺序编写——
> `domain → errors → validators → actions → workflows`。
> 每个模块的实现代码必须与对应测试**同一次提交**中完成。

### 2.2 Adapter 层测试

| 测试类 | 文件 | 内容 |
|--------|------|------|
| `TestMockAdapter` | `tests/test_mock_adapter.py` | mock 的三类动作（成功/失败/确认） |
| `TestKiCadAdapter` | `tests/test_kicad_adapter.py` | KiCad 各动作的独立测试 |
| `TestSTM32Adapter` | `tests/test_stm32_adapter.py` | STM32 各动作的独立测试 |

### 2.3 MCP 层测试

| 测试类 | 文件 | 内容 |
|--------|------|------|
| `TestMCPServer` | `tests/test_mcp_server.py` | Server 启动、工具注册 |
| `TestMCPTools` | `tests/test_mcp_tools.py` | 每个工具的输入输出验证 |

---

## 3. 集成测试

### 3.1 最小集成（Phase 1 完成后）

```
MCP Server → run_action → Core → Mock Adapter → 返回结果
```

### 3.2 KiCad 集成（Phase 2 完成后）

```
MCP Server → run_action → Core → KiCad Adapter → pcbnew → 真实文件
```

测试用数据：
- 一个最小 KiCad 工程放在 `examples/kicad_export_example/`
- 只包含最基本的 PCB（一个电阻 + 一条走线）

### 3.3 确认流程集成

```
run_action (破坏性动作) → ConfirmationRequiredError
  → Agent 调用 confirm_action (confirm=true)
    → 动作继续执行 → 成功
```

---

## 4. 必须覆盖的错误路径

| 错误路径 | 测试方法 |
|---------|---------|
| Adapter 不可用 | Mock adapter 返回 `available=False` |
| 软件未安装 | 在 CI 环境中自然触发 |
| 文件不存在 | 传入不存在的工程路径 |
| 权限不足 | Mock 返回 PermissionError |
| 执行超时 | 设置极短 timeout |
| 重试耗尽 | Mock 持续失败 |
| 用户拒绝确认 | confirm_action(confirm=false) |
| 校验失败 | 产物不符合预期 |
| 空产物 | 导出到空目录 |
| 异常大的产物 | Mock 返回超大文件 |

---

## 5. 测试工具链

```toml
# pyproject.toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-mock>=3.12",
    "pytest-asyncio>=0.23",
    "pytest-cov>=5.0",
    "coverage>=7.4",
]
```

### 运行命令

```bash
# 单元测试
pytest tests/ -v

# 带覆盖率
pytest tests/ -v --cov=core --cov=codex_plugin --cov-report=term-missing

# 只跑 Core 测试
pytest tests/test_core.py -v

# 跳过需要真实硬件的测试
pytest tests/ -v -m "not hardware"

# 只跑需要真实硬件的测试
pytest tests/ -v -m "hardware"
```

---

## 6. 测试标记（Markers）

```python
# pytest.ini 或 pyproject.toml
[tool.pytest.ini_options]
markers = [
    "hardware: 需要真实硬件（STM32 开发板等）",
    "kicad: 需要 KiCad 安装",
    "slow: 耗时较长的测试",
    "integration: 集成测试",
]
```

---

## 7. 测试命名规范

```
test_{模块}_{功能}_{场景}.py

示例：
test_domain_task_creation.py
test_actions_execute_success.py
test_actions_execute_confirmation_required.py
test_actions_execute_timeout.py
test_kicad_export_gerber.py
test_mcp_run_action_invalid_params.py
```

---

## 8. CI 配置

> ✅ 已落地为 `.github/workflows/test.yml`（2026-08-05）。COM 类 adapter（SolidWorks/AutoCAD/Multisim）的测试仅允许在 windows runner 上通过 marker 启用，ubuntu runner 永不执行依赖 pywin32 的测试。

参考配置如下：

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest]
        python-version: ["3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - run: pip install -e ".[dev]"
      - run: pytest tests/ -v -m "not hardware"
```

---

## 9. 测试第一原则

> 在任何实现代码之前，先写测试。测试即规格。

对于每个新工具或新 adapter 动作：
1. 先写测试（描述期望行为）
2. 运行测试 → 失败（红色）
3. 写实现代码
4. 运行测试 → 通过（绿色）
5. 重构（保持绿色）
