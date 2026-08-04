# 02 — 统一数据模型定义（AI 可读版）

> **前置阅读**：`01-architecture.md`
> **后续阅读**：`03-tools-design.md`
> **用途**：定义系统中所有数据结构的精确字段、类型、约束。这是整个项目的"宪法"。

---

## 1. 设计原则

1. **所有模型用 pydantic v2 定义**——自动获得 JSON Schema 导出、序列化、校验
2. **字段只增不减**——后续版本只能加字段，不能删已有字段
3. **必填字段尽量少**——用 `default` 降低调用方心智负担
4. **枚举优先于字符串**——凡是有限集合，用 `Literal` 或 `Enum`
5. **每个模型有 `model_config`**——`extra="forbid"` 防止拼写错误被静默忽略

---

## 2. 核心枚举

```python
from enum import Enum

class ActionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CONFIRMATION_REQUIRED = "confirmation_required"
    CANCELLED = "cancelled"

class ErrorSeverity(str, Enum):
    RETRYABLE = "retryable"      # 可自动重试
    FATAL = "fatal"              # 不可恢复
    NEEDS_HUMAN = "needs_human"  # 需人工介入

class ValidationStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    SKIPPED = "skipped"

class ExecutionMode(str, Enum):
    DRY_RUN = "dry_run"     # 预览，不做实际操作
    NORMAL = "normal"       # 正常执行
    FORCE = "force"         # 强制执行（跳过确认）
```

---

## 3. 数据模型定义

### 3.1 Task（任务）

> 一个用户或 Agent 提出的工程目标。一个 Task 可拆成多个 Action。

```python
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class Task(BaseModel):
    model_config = {"extra": "forbid"}

    task_id: str = Field(description="唯一任务 ID，格式: task-{uuid}")
    title: str = Field(description="任务简短标题，如'导出 KiCad Gerber 并检查'")
    target_app: str = Field(description="目标软件: kicad | keil | stm32cubeide | ccs | autocad | multisim | solidworks")
    goal: str = Field(description="自然语言描述的任务目标")
    priority: int = Field(default=5, ge=1, le=10, description="1=最高, 10=最低")
    mode: ExecutionMode = Field(default=ExecutionMode.NORMAL)
    inputs: dict = Field(default_factory=dict, description="任务输入参数")
    constraints: list[str] = Field(default_factory=list, description="约束条件列表")
    requires_confirmation: bool = Field(default=False, description="此任务是否需要人工确认")
    expected_outputs: list[str] = Field(default_factory=list, description="期望产出物列表（文件路径或描述）")
    created_at: datetime = Field(default_factory=datetime.now)
    metadata: dict = Field(default_factory=dict, description="额外元数据")
```

### 3.2 Action（动作）

> Task 被分解后的最小可执行单元。每个 Action 对应一个具体操作。

```python
class RetryPolicy(BaseModel):
    model_config = {"extra": "forbid"}

    max_retries: int = Field(default=3, ge=0, le=10)
    delay_seconds: int = Field(default=5, ge=1, le=300)
    backoff_multiplier: float = Field(default=2.0, ge=1.0, le=10.0)
    retry_on: list[ErrorSeverity] = Field(default=[ErrorSeverity.RETRYABLE])

class Action(BaseModel):
    model_config = {"extra": "forbid"}

    action_id: str = Field(description="唯一动作 ID，格式: act-{uuid}")
    task_id: str = Field(description="所属 Task 的 ID")
    action_name: str = Field(description="动作名称: open_project | export_gerber | run_drc | flash_firmware ...")
    action_type: str = Field(description="动作类型: read | write | execute | validate | collect")
    app: str = Field(description="目标软件")
    adapter: str = Field(default="", description="指定 adapter 名称，空字符串表示自动选择")
    parameters: dict = Field(default_factory=dict, description="动作参数，由 adapter 解释")
    precheck: Optional[str] = Field(default=None, description="执行前校验表达式或检查项")
    postcheck: Optional[str] = Field(default=None, description="执行后校验表达式或检查项")
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    requires_confirmation: bool = Field(default=False, description="执行前是否需要用户确认")
    timeout_seconds: int = Field(default=300, ge=1, le=3600)
    tags: list[str] = Field(default_factory=list, description="标签，方便筛选")
```

### 3.3 ActionResult（动作结果）

> 每次执行 Action 后的结构化返回。这是系统中最频繁创建的数据结构。

```python
class Artifact(BaseModel):
    model_config = {"extra": "forbid"}

    path: str = Field(description="产物文件路径")
    size_bytes: int = Field(default=0, description="文件大小")
    checksum: Optional[str] = Field(default=None, description="SHA256 校验和")
    mime_type: Optional[str] = Field(default=None)
    description: str = Field(default="")

class ErrorDetail(BaseModel):
    model_config = {"extra": "forbid"}

    error_code: str = Field(description="机器可读错误码: ERR_TIMEOUT / ERR_PERMISSION / ERR_NOT_FOUND ...")
    severity: ErrorSeverity = Field(description="错误严重程度")
    message: str = Field(description="人类可读的错误描述")
    suggested_action: str = Field(default="", description="建议的下一步操作")
    context: dict = Field(default_factory=dict, description="出错时的上下文快照")
    recoverable: bool = Field(default=False)

class ActionResult(BaseModel):
    model_config = {"extra": "forbid"}

    success: bool = Field(description="动作是否成功执行")
    action_id: str
    task_id: str
    action_name: str
    status: ActionStatus
    start_time: datetime
    end_time: datetime
    duration_ms: int = Field(default=0)
    summary: str = Field(default="", description="一句话总结")
    artifacts: list[Artifact] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[ErrorDetail] = Field(default_factory=list)
    logs: list[str] = Field(default_factory=list, description="关键日志行")
    validation: Optional["ValidationReport"] = Field(default=None, description="执行后校验结果")
    next_suggestion: str = Field(default="", description="建议的下一步操作")
    raw_output: Optional[str] = Field(default=None, description="软件原始输出（调试用）")
    metadata: dict = Field(default_factory=dict)
```

### 3.4 ValidationReport（验证报告）

> 对 ActionResult 的校验结果。判断输出是否满足预期。

```python
class CheckResult(BaseModel):
    model_config = {"extra": "forbid"}

    check_name: str = Field(description="检查项名称")
    status: ValidationStatus
    message: str = Field(default="")
    evidence: str = Field(default="", description="支撑证据（文件路径、数值等）")

class ValidationReport(BaseModel):
    model_config = {"extra": "forbid"}

    action_id: str
    passed: bool = Field(description="所有检查是否通过")
    checks: list[CheckResult] = Field(default_factory=list)
    failed_checks: list[CheckResult] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list, description="证据文件路径列表")
    recommendation: str = Field(default="", description="综合建议")
    validated_at: datetime = Field(default_factory=datetime.now)
```

### 3.5 AdapterInfo（适配器信息）

> 用于 `list_adapters` 工具的返回。

```python
class AdapterInfo(BaseModel):
    model_config = {"extra": "forbid"}

    name: str = Field(description="适配器名称: kicad / stm32 / ti / solidworks")
    display_name: str = Field(description="显示名称: 'KiCad EDA'")
    version: str = Field(description="适配器版本")
    software_version: Optional[str] = Field(default=None, description="实际软件版本")
    available: bool = Field(description="是否可用（软件已安装且可调用）")
    available_actions: list[str] = Field(default_factory=list, description="该适配器支持的动作列表")
    priority_path: str = Field(description="主集成路径: pcbnew_api | cli | com | macro")
    status_message: str = Field(default="", description="不可用时的原因说明")
    capabilities: list[str] = Field(default_factory=list, description="能力标签: export / validate / flash / program")
```

---

## 4. 模型之间的关系

```
Task (1) ──→ (*) Action
                 │
                 ↓ execute
            ActionResult (1) ──→ (*) Artifact
                 │               ──→ (*) ErrorDetail
                 │
                 ↓ validate
            ValidationReport (1) ──→ (*) CheckResult
```

---

## 5. pydantic 实现提示

### 5.1 文件组织建议

```python
# core/domain.py

# 1. 先定义 Enum
# 2. 再定义小模型 (Artifact, ErrorDetail, CheckResult, RetryPolicy)
# 3. 然后大模型 (Action, ActionResult, ValidationReport, Task)
# 4. 最后做 forward reference 更新
```

### 5.2 序列化

所有模型都使用 `.model_dump()` 输出 dict，再用 `json.dumps()` 输出 JSON 字符串。MCP Server 层用 `.model_json_schema()` 生成 JSON Schema 给 MCP 协议注册工具。

### 5.3 版本兼容

后续加字段时使用 `Field(default=...)` 保证向后兼容。永不删除或重命名字段。

---

## 6. 下一步

读完本文档后，继续阅读：
- `03-tools-design.md` — 每个工具的具体接口定义
