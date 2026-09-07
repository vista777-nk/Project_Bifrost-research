"""Validated, software-independent circuit specifications and edit batches."""

from __future__ import annotations

import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, TypeAdapter, model_validator

Reference = Annotated[str, Field(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,31}$")]
Net = Annotated[str, Field(pattern=r"^(0|[A-Za-z_][A-Za-z0-9_]{0,63})$")]
Kind = Literal["R", "C", "L", "VDC"]
Rotation = Literal[0, 90, 180, 270]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Component(StrictModel):
    reference: Reference
    kind: Kind
    value: FiniteFloat
    x_mm: Annotated[FiniteFloat, Field(ge=0, le=2000)] | None = None
    y_mm: Annotated[FiniteFloat, Field(ge=0, le=2000)] | None = None
    rotation: Rotation = 0
    pins: dict[Literal["1", "2"], Net | None] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_component(self) -> Component:
        if self.kind != "VDC" and self.value <= 0:
            raise ValueError("R, C, and L values must be positive SI values.")
        if abs(self.value) > 1e15:
            raise ValueError("Component value is outside the supported range.")
        self.pins = {"1": None, "2": None, **self.pins}
        return self


class Circuit(StrictModel):
    title: str = Field(default="Bifrost Circuit", max_length=120)
    components: list[Component] = Field(default_factory=list, max_length=128)

    @model_validator(mode="after")
    def validate_circuit(self) -> Circuit:
        refs = [component.reference.lower() for component in self.components]
        if len(refs) != len(set(refs)):
            raise ValueError("Component references must be unique, ignoring case.")
        for index, component in enumerate(self.components):
            if component.x_mm is None:
                component.x_mm = 20 + 40 * (index % 4)
            if component.y_mm is None:
                component.y_mm = 20 + 30 * (index // 4)
        return self


class _Target(StrictModel):
    reference: Reference


class _Value(_Target):
    op: Literal["set_value"]
    value: FiniteFloat


class _Add(StrictModel):
    op: Literal["add"]
    component: Component


class _Remove(_Target):
    op: Literal["remove"]


class _Replace(_Target):
    op: Literal["replace"]
    kind: Kind
    value: FiniteFloat


class _Move(_Target):
    op: Literal["move"]
    x_mm: Annotated[FiniteFloat, Field(ge=0, le=2000)]
    y_mm: Annotated[FiniteFloat, Field(ge=0, le=2000)]


class _Rotate(_Target):
    op: Literal["rotate"]
    rotation: Rotation


class _Connect(_Target):
    op: Literal["connect"]
    pin: Literal["1", "2"]
    net: Net


class _Disconnect(_Target):
    op: Literal["disconnect"]
    pin: Literal["1", "2"]


Change = Annotated[
    _Value | _Add | _Remove | _Replace | _Move | _Rotate | _Connect | _Disconnect,
    Field(discriminator="op"),
]
_CHANGES = TypeAdapter(list[Change])


def apply_changes(circuit: Circuit, changes: list[dict[str, Any]]) -> Circuit:
    if not 1 <= len(changes) <= 256:
        raise ValueError("An edit batch must contain 1 to 256 changes.")
    operations = _CHANGES.validate_python(changes)
    data = circuit.model_dump()
    items = data["components"]
    for change in operations:
        operation = change.model_dump()
        if change.op == "add":
            items.append(operation["component"])
        else:
            target = next((item for item in items if item["reference"] == change.reference), None)
            if target is None:
                raise ValueError(f"Unknown component: {change.reference}")
            if change.op == "remove":
                items.remove(target)
            elif change.op in {"connect", "disconnect"}:
                target["pins"][change.pin] = operation.get("net")
            else:
                target.update(
                    {
                        key: value
                        for key, value in operation.items()
                        if key not in {"op", "reference"}
                    }
                )
        data = Circuit.model_validate(data).model_dump()
        items = data["components"]
    return Circuit.model_validate(data)


def publish_revision(path: Path, payload: bytes, *, overwrite: bool) -> None:
    """Atomically publish a fully validated artifact; never truncate a target."""
    if not payload:
        raise ValueError("Cannot publish an empty native artifact.")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with NamedTemporaryFile(dir=path.parent, prefix=".bifrost-", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        if overwrite:
            os.replace(temporary, path)
        else:
            os.link(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
