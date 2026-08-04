"""
Bifrost Core — 工作流编排

提供多步骤工作流的定义与执行能力。
一个 Workflow 包含多个 Step，按顺序执行。

核心概念：
- Step: 工作流中的一个步骤（指向一个 Action）
- Workflow: 有序的 Step 序列
- run_workflow(): 执行一个工作流并收集所有步骤结果

参考: docs/01-architecture.md §2.1 (workflows.py)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from core.actions import ActionExecutor

# ── Step ────────────────────────────────────────────────────────


@dataclass
class Step:
    """工作流中的一个步骤。

    每个 Step 定义了要执行的一个动作（哪个软件、什么操作、什么参数）。
    """

    step_id: str
    name: str                      # 人类可读的步骤名称
    app: str                       # 目标软件
    action_name: str               # 动作名称
    parameters: dict = field(default_factory=dict)
    requires_confirmation: bool = False
    stop_on_failure: bool = True   # 此步骤失败时是否终止整个工作流

    def to_action(self, task_id: str) -> Any:
        """将 Step 转换为 Action 对象（延迟导入避免循环依赖）"""
        import uuid as _uuid

        from core.domain import Action

        return Action(
            action_id=f"act-{_uuid.uuid4().hex[:8]}",
            task_id=task_id,
            action_name=self.action_name,
            action_type="execute",
            app=self.app,
            parameters=self.parameters,
            requires_confirmation=self.requires_confirmation,
        )


# ── Workflow ────────────────────────────────────────────────────


@dataclass
class Workflow:
    """一个有序的多步骤工作流。

    Usage:
        wf = Workflow(workflow_id="wf-001", title="导出+DRC", steps=[...])
        report = wf.run(executor)
    """

    workflow_id: str
    title: str
    steps: list[Step]

    def run(self, executor: ActionExecutor) -> dict[str, Any]:
        """按顺序执行所有步骤。

        Args:
            executor: 已注册适配器的 ActionExecutor 实例

        Returns:
            dict: {
                "workflow_id": str,
                "title": str,
                "completed": bool,       # 是否所有步骤成功完成
                "failed_steps": int,      # 失败的步骤数
                "results": list[dict],   # 每个步骤的执行摘要
                "started_at": str,
                "finished_at": str,
            }
        """
        import uuid as _uuid

        task_id = f"task-{_uuid.uuid4().hex[:8]}"
        started = datetime.now()
        results: list[dict] = []
        failed_count = 0

        for step in self.steps:
            result = executor.execute(step.to_action(task_id))
            results.append({
                "step_id": step.step_id,
                "step_name": step.name,
                "success": result.success,
                "status": result.status.value,
                "summary": result.summary,
                "errors": [e.message for e in result.errors],
            })

            if not result.success:
                failed_count += 1
                if step.stop_on_failure:
                    break

        return {
            "workflow_id": self.workflow_id,
            "title": self.title,
            "completed": failed_count == 0,
            "failed_steps": failed_count,
            "results": results,
            "started_at": started.isoformat(),
            "finished_at": datetime.now().isoformat(),
        }


# ── 便捷函数 ────────────────────────────────────────────────────


def run_workflow(workflow: Workflow, executor: ActionExecutor) -> dict[str, Any]:
    """执行一个工作流的便捷函数。

    Args:
        workflow: 待执行的工作流
        executor: 已配置的 ActionExecutor

    Returns:
        dict: 同 Workflow.run() 的返回格式
    """
    return workflow.run(executor)
