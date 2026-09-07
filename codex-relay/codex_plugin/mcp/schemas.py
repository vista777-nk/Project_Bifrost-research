"""Pydantic input models and JSON Schema helpers for the MCP tools.

The MCP SDK can derive a schema from a function signature, but keeping the
contract in one place also lets the Hermes relay and tests inspect it without
importing the optional MCP dependency.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class _ToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ListAdaptersInput(_ToolInput):
    filter: str = Field(default="", description="Optional adapter name filter")


class RunActionInput(_ToolInput):
    app: str = Field(description="Target application adapter")
    action_name: str = Field(description="Adapter action to execute")
    parameters: dict[str, Any] = Field(default_factory=dict)
    mode: Literal["dry_run", "normal", "force"] = "normal"
    risk_level: Literal["low", "medium", "high", "critical"] = "low"
    task_id: str = ""
    timeout_seconds: int = Field(default=300, ge=1, le=3600)
    retry_on_failure: bool = True


class ValidateResultInput(_ToolInput):
    action_id: str
    checks: list[str] = Field(default_factory=list)


class CollectLogsInput(_ToolInput):
    action_id: str = ""
    task_id: str = ""
    include_raw_output: bool = False
    format: Literal["json", "text"] = "json"


class ConfirmActionInput(_ToolInput):
    action_id: str
    confirm: bool
    reason: str = ""


class PreviewActionInput(_ToolInput):
    app: str
    action_name: str
    parameters: dict[str, Any] = Field(default_factory=dict)


TOOL_INPUT_MODELS: dict[str, type[_ToolInput]] = {
    "list_adapters": ListAdaptersInput,
    "run_action": RunActionInput,
    "validate_result": ValidateResultInput,
    "collect_logs": CollectLogsInput,
    "confirm_action": ConfirmActionInput,
    "preview_action": PreviewActionInput,
}


def get_tool_input_model(tool_name: str) -> type[_ToolInput]:
    """Return the input model for a registered tool or raise ``KeyError``."""

    return TOOL_INPUT_MODELS[tool_name]


def get_tool_schemas() -> dict[str, dict[str, Any]]:
    """Return JSON Schema documents keyed by MCP tool name."""

    return {name: model.model_json_schema() for name, model in TOOL_INPUT_MODELS.items()}


__all__ = [
    "CollectLogsInput",
    "ConfirmActionInput",
    "ListAdaptersInput",
    "PreviewActionInput",
    "RunActionInput",
    "TOOL_INPUT_MODELS",
    "ValidateResultInput",
    "get_tool_input_model",
    "get_tool_schemas",
]
