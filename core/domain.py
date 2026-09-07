"""
Bifrost Core — 统一数据模型

本模块定义系统中所有数据结构的精确字段、类型、约束。
这是整个项目的"宪法"——所有其他模块的数据交换均基于此处定义的类型。

设计原则：
- 所有模型用 pydantic v2 定义（自动获得 JSON Schema 导出、序列化、校验）
- 字段只增不减（后续版本只能加字段，不能删已有字段）
- 必填字段尽量少（用 default 降低调用方心智负担）
- 枚举优先于字符串（凡是有限集合，用 Enum 或 Literal）
- 每个模型有 model_config extra="forbid"（防止拼写错误被静默忽略）

参考: docs/02-data-models.md
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

# ═══════════════════════════════════════════════════════════════
# 核心枚举
# ═══════════════════════════════════════════════════════════════


class ActionStatus(StrEnum):
    """动作执行状态"""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CONFIRMATION_REQUIRED = "confirmation_required"
    CANCELLED = "cancelled"


class ErrorSeverity(StrEnum):
    """错误严重程度"""

    RETRYABLE = "retryable"        # 可自动重试
    FATAL = "fatal"                # 不可恢复
    NEEDS_HUMAN = "needs_human"    # 需人工介入


class ValidationStatus(StrEnum):
    """校验结果状态"""

    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    SKIPPED = "skipped"


class ExecutionMode(StrEnum):
    """动作执行模式"""

    DRY_RUN = "dry_run"   # 预览，不做实际操作
    NORMAL = "normal"     # 正常执行
    FORCE = "force"       # 强制执行（跳过确认）


class RiskLevel(StrEnum):
    """Action risk level used by relay permission gates."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ═══════════════════════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════════════════════


class Task(BaseModel):
    """一个用户或 Agent 提出的工程目标。一个 Task 可拆成多个 Action。"""

    model_config = {"extra": "forbid"}

    task_id: str = Field(description="唯一任务 ID，格式: task-{uuid}")
    title: str = Field(description="任务简短标题，如'导出 KiCad Gerber 并检查'")
    target_app: str = Field(
        description="目标软件: kicad | keil | stm32cubeide | ccs | autocad | multisim | solidworks"
    )
    goal: str = Field(description="自然语言描述的任务目标")
    priority: int = Field(default=5, ge=1, le=10, description="1=最高, 10=最低")
    mode: ExecutionMode = Field(default=ExecutionMode.NORMAL)
    inputs: dict = Field(default_factory=dict, description="任务输入参数")
    constraints: list[str] = Field(default_factory=list, description="约束条件列表")
    requires_confirmation: bool = Field(
        default=False, description="此任务是否需要人工确认"
    )
    expected_outputs: list[str] = Field(
        default_factory=list, description="期望产出物列表（文件路径或描述）"
    )
    created_at: datetime = Field(default_factory=datetime.now)
    metadata: dict = Field(default_factory=dict, description="额外元数据")


class RetryPolicy(BaseModel):
    """动作重试策略"""

    model_config = {"extra": "forbid"}

    max_retries: int = Field(default=3, ge=0, le=10)
    delay_seconds: int = Field(default=5, ge=1, le=300)
    backoff_multiplier: float = Field(default=2.0, ge=1.0, le=10.0)
    retry_on: list[ErrorSeverity] = Field(
        default_factory=lambda: [ErrorSeverity.RETRYABLE]
    )


class Action(BaseModel):
    """Task 被分解后的最小可执行单元。每个 Action 对应一个具体操作。"""

    model_config = {"extra": "forbid"}

    action_id: str = Field(description="唯一动作 ID，格式: act-{uuid}")
    task_id: str = Field(description="所属 Task 的 ID")
    action_name: str = Field(
        description="动作名称: open_project | export_gerber | run_drc | flash_firmware ..."
    )
    action_type: str = Field(
        description="动作类型: read | write | execute | validate | collect"
    )
    app: str = Field(description="目标软件")
    risk_level: RiskLevel = Field(
        default=RiskLevel.LOW,
        description="Risk level: low | medium | high | critical",
    )
    adapter: str = Field(
        default="", description="指定 adapter 名称，空字符串表示自动选择"
    )
    parameters: dict = Field(
        default_factory=dict, description="动作参数，由 adapter 解释"
    )
    precheck: str | None = Field(
        default=None, description="执行前校验表达式或检查项"
    )
    postcheck: str | None = Field(
        default=None, description="执行后校验表达式或检查项"
    )
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    requires_confirmation: bool = Field(
        default=False, description="执行前是否需要用户确认"
    )
    confirmation_granted: bool = Field(
        default=False, description="Set by the relay only after explicit confirmation"
    )
    permission_note: str = Field(
        default="", description="Human-readable reason confirmation is required"
    )
    timeout_seconds: int = Field(default=300, ge=1, le=3600)
    tags: list[str] = Field(default_factory=list, description="标签，方便筛选")


class Artifact(BaseModel):
    """动作产出的文件描述"""

    model_config = {"extra": "forbid"}

    path: str = Field(description="产物文件路径")
    size_bytes: int = Field(default=0, description="文件大小")
    checksum: str | None = Field(default=None, description="SHA256 校验和")
    mime_type: str | None = Field(default=None)
    description: str = Field(default="")


class ErrorDetail(BaseModel):
    """结构化错误信息"""

    model_config = {"extra": "forbid"}

    error_code: str = Field(
        description="机器可读错误码: ERR_TIMEOUT / ERR_PERMISSION / ERR_NOT_FOUND ..."
    )
    severity: ErrorSeverity = Field(description="错误严重程度")
    message: str = Field(description="人类可读的错误描述")
    suggested_action: str = Field(default="", description="建议的下一步操作")
    context: dict = Field(default_factory=dict, description="出错时的上下文快照")
    recoverable: bool = Field(default=False)


class CheckResult(BaseModel):
    """单个校验检查项的结果"""

    model_config = {"extra": "forbid"}

    check_name: str = Field(description="检查项名称")
    status: ValidationStatus
    message: str = Field(default="")
    evidence: str = Field(default="", description="支撑证据（文件路径、数值等）")


class ValidationReport(BaseModel):
    """对 ActionResult 的校验结果。判断输出是否满足预期。"""

    model_config = {"extra": "forbid"}

    action_id: str
    passed: bool = Field(description="所有检查是否通过")
    checks: list[CheckResult] = Field(default_factory=list)
    failed_checks: list[CheckResult] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list, description="证据文件路径列表")
    recommendation: str = Field(default="", description="综合建议")
    validated_at: datetime = Field(default_factory=datetime.now)


class ActionResult(BaseModel):
    """每次执行 Action 后的结构化返回。这是系统中最频繁创建的数据结构。"""

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
    validation: ValidationReport | None = Field(
        default=None, description="执行后校验结果"
    )
    next_suggestion: str = Field(default="", description="建议的下一步操作")
    raw_output: str | None = Field(default=None, description="软件原始输出（调试用）")
    metadata: dict = Field(default_factory=dict)


class AdapterInfo(BaseModel):
    """适配器信息（list_adapters 工具返回）"""

    model_config = {"extra": "forbid"}

    name: str = Field(
        description=(
            "适配器名称: kicad | keil | stm32cubeide | "
            "ccs | autocad | multisim | solidworks"
        )
    )
    display_name: str = Field(description="显示名称: 'KiCad EDA'")
    version: str = Field(description="适配器版本")
    software_version: str | None = Field(default=None, description="实际软件版本")
    available: bool = Field(description="是否可用（软件已安装且可调用）")
    available_actions: list[str] = Field(
        default_factory=list, description="该适配器支持的动作列表"
    )
    priority_path: str = Field(description="主集成路径: pcbnew_api | cli | com | macro")
    status_message: str = Field(default="", description="不可用时的原因说明")
    capabilities: list[str] = Field(
        default_factory=list, description="能力标签: export / validate / flash / program"
    )
