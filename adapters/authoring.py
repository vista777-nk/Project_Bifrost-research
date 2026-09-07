"""Shared action boundary for native schematic editors."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Protocol

from pydantic import Field

from core.circuits import Change, Circuit, StrictModel, apply_changes, publish_revision
from core.domain import Action, ActionResult, ActionStatus, Artifact, ErrorDetail, ErrorSeverity

AUTHORING_ACTIONS = ["find_components", "inspect_schematic", "create_schematic", "edit_schematic"]


class _Find(StrictModel):
    query: str = ""


class _Inspect(StrictModel):
    input_file: str


class _Create(StrictModel):
    output_file: str
    circuit: Circuit


class _Edit(_Inspect):
    output_file: str
    expected_input_sha256: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    changes: list[Change] = Field(min_length=1, max_length=256)


class NativeEditor(Protocol):
    suffix: str

    def catalog(self) -> list[dict[str, Any]]: ...
    def load(self, path: Path) -> tuple[Circuit, Any]: ...
    def render(self, circuit: Circuit, original: Any | None, path: Path) -> None: ...
    def verify(self, path: Path, circuit: Circuit) -> dict[str, Any]: ...


def execute_authoring(
    action: Action,
    editor: NativeEditor | Callable[[], NativeEditor],
    *,
    preview: bool = False,
) -> ActionResult:
    start = datetime.now()
    base = dict(
        action_id=action.action_id,
        task_id=action.task_id,
        action_name=action.action_name,
        start_time=start,
        end_time=start,
    )
    try:
        if callable(editor):
            editor = editor()
        if action.action_name == "find_components":
            query = _Find.model_validate(action.parameters).query.lower()
            entries = [item for item in editor.catalog() if query in str(item).lower()]
            return ActionResult(
                success=True,
                status=ActionStatus.SUCCESS,
                **base,
                metadata={
                    "components": entries,
                    "action_parameters": {
                        "inspect_schematic": _Inspect.model_json_schema(),
                        "create_schematic": _Create.model_json_schema(),
                        "edit_schematic": _Edit.model_json_schema(),
                    },
                },
            )
        source: Path | None = None
        original = None
        previous = None
        checksum = None
        if action.action_name == "inspect_schematic":
            request = _Inspect.model_validate(action.parameters)
            path = Path(request.input_file).expanduser().resolve()
            checksum = hashlib.sha256(path.read_bytes()).hexdigest()
            circuit, _ = editor.load(path)
            if hashlib.sha256(path.read_bytes()).hexdigest() != checksum:
                raise ValueError("The source changed during inspection; inspect it again.")
            return ActionResult(
                success=True,
                status=ActionStatus.SUCCESS,
                **base,
                metadata={
                    "circuit": circuit.model_dump(),
                    "input_sha256": checksum,
                },
            )
        if action.action_name == "create_schematic":
            create = _Create.model_validate(action.parameters)
            output = Path(create.output_file).expanduser().resolve()
            circuit = create.circuit
        elif action.action_name == "edit_schematic":
            edit = _Edit.model_validate(action.parameters)
            source = Path(edit.input_file).expanduser().resolve()
            output = Path(edit.output_file).expanduser().resolve()
            checksum = hashlib.sha256(source.read_bytes()).hexdigest()
            if checksum != edit.expected_input_sha256.lower():
                raise ValueError(
                    "The source changed since inspection; inspect it again before editing."
                )
            previous, original = editor.load(source)
            if hashlib.sha256(source.read_bytes()).hexdigest() != checksum:
                raise ValueError("The source changed during inspection; inspect it again.")
            circuit = apply_changes(previous, [change.model_dump() for change in edit.changes])
        else:
            raise ValueError(f"Unsupported authoring action: {action.action_name}")
        normalize = getattr(editor, "normalize", None)
        if normalize is not None:
            requested = circuit
            circuit = normalize(circuit)
            if previous is not None:
                prior = {c.reference: c for c in previous.components}
                normalized = circuit.model_dump()
                for component, item in zip(
                    requested.components, normalized["components"], strict=True
                ):
                    old = prior.get(component.reference)
                    if old is not None and all(
                        getattr(old, key) == getattr(component, key)
                        for key in ("kind", "rotation", "x_mm", "y_mm")
                    ):
                        item.update(x_mm=old.x_mm, y_mm=old.y_mm)
                circuit = Circuit.model_validate(normalized)
        if output.suffix.lower() != editor.suffix:
            raise ValueError(f"Output must use {editor.suffix}.")
        if source == output:
            raise ValueError(
                "Authoring requires a distinct revision path; never overwrite the source."
            )
        if output.exists() and not output.is_file():
            raise ValueError("Output must be a file, not a directory.")
        preflight = getattr(editor, "preflight", None)
        if preflight is not None:
            preflight(circuit, original, previous)
        plan = {
            "before": previous.model_dump() if previous else None,
            "circuit": circuit.model_dump(),
            "input_sha256": checksum,
            "output_file": str(output),
            "source_preserved": True,
            "native_validation_pending": True,
        }
        if preview:
            return ActionResult(
                success=True,
                status=ActionStatus.SUCCESS,
                **base,
                summary="Native revision parameters validated; no revision published.",
                metadata={"preview": plan},
            )
        if output.exists() and not action.confirmation_granted:
            raise FileExistsError(f"Explicit overwrite confirmation required: {output}")
        with TemporaryDirectory(prefix="bifrost-authoring-") as directory:
            staged = Path(directory) / output.name
            editor.render(circuit, original, staged)
            verification = editor.verify(staged, circuit)
            payload = staged.read_bytes()
            if source and hashlib.sha256(source.read_bytes()).hexdigest() != checksum:
                raise ValueError("The source changed during validation; no revision was published.")
            publish_revision(output, payload, overwrite=action.confirmation_granted)
        base["end_time"] = datetime.now()
        digest = hashlib.sha256(payload).hexdigest()
        return ActionResult(
            success=True,
            status=ActionStatus.SUCCESS,
            **base,
            summary=f"Native schematic revision created: {output.name}",
            artifacts=[
                Artifact(
                    path=str(output),
                    size_bytes=len(payload),
                    checksum=digest,
                    description="Editable native schematic revision",
                )
            ],
            metadata={
                "circuit": circuit.model_dump(),
                "input_sha256": checksum,
                "output_sha256": digest,
                "verification": verification,
                "before": previous.model_dump() if previous else None,
                "source_preserved": True,
            },
        )
    except FileExistsError as exc:
        return ActionResult(
            success=False,
            status=ActionStatus.CONFIRMATION_REQUIRED,
            **base,
            summary=str(exc),
            errors=[
                ErrorDetail(
                    error_code="ERR_CONFIRMATION_REQUIRED",
                    severity=ErrorSeverity.NEEDS_HUMAN,
                    message=str(exc),
                )
            ],
        )
    except Exception as exc:
        return ActionResult(
            success=False,
            status=ActionStatus.FAILED,
            **base,
            summary=str(exc),
            errors=[
                ErrorDetail(
                    error_code="ERR_AUTHORING_FAILED",
                    severity=ErrorSeverity.FATAL,
                    message=str(exc),
                    recoverable=False,
                )
            ],
        )
