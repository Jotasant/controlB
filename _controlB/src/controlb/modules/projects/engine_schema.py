"""Declarative, bounded configuration. Never executes user supplied expressions."""
from __future__ import annotations

import math
import re
from copy import deepcopy
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Condition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: str
    equals: str | float | bool | None


class FieldDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{0,49}$")
    label: str = Field(min_length=1, max_length=120)
    section: str = Field(default="Dados adicionais", max_length=120)
    type: Literal["text", "number", "money", "date", "datetime", "select", "multiselect", "boolean", "quantity", "reference", "table"] = "text"
    required: bool = False
    required_stages: list[str] = Field(default_factory=list, max_length=100)
    visible_when: Condition | None = None
    default: Any = None
    minimum: float | None = None
    maximum: float | None = None
    max_length: int = Field(default=4096, ge=1, le=10000)
    pattern: str | None = Field(default=None, max_length=128)
    options: list[str] = Field(default_factory=list, max_length=100)
    unit: str | None = Field(default=None, max_length=30)
    reference: Literal["contact", "customer", "user", "team", "supplier"] | None = None
    editable_roles: list[Literal["manager", "member", "observer"]] = Field(default_factory=list)
    columns: list[FieldDefinition] = Field(default_factory=list, max_length=20)
    max_rows: int = Field(default=50, ge=1, le=100)

    @model_validator(mode="after")
    def check_definition(self):
        if any(word in self.key for word in ("password", "senha", "secret", "credential", "token", "api_key")):
            raise ValueError("Campos personalizados não podem armazenar credenciais.")
        if self.minimum is not None and (not math.isfinite(self.minimum) or self.maximum is not None and self.minimum > self.maximum):
            raise ValueError("Limites inválidos.")
        if self.maximum is not None and not math.isfinite(self.maximum):
            raise ValueError("Limites inválidos.")
        if self.pattern:
            # No groups, alternation, lookarounds or backreferences (ReDoS).
            if any(char in self.pattern for char in ("(", ")", "|", "\\")) or re.search(r"[+*?}]\s*[+*?{]", self.pattern):
                raise ValueError("Use um padrão simples, sem grupos, alternativas ou escapes.")
            try:
                re.compile(self.pattern)
            except re.error as exc:
                raise ValueError("Padrão inválido.") from exc
        if self.type in ("select", "multiselect") and (not self.options or len(set(self.options)) != len(self.options)):
            raise ValueError("Informe opções distintas para a seleção.")
        if self.type == "reference" and not self.reference:
            raise ValueError("Informe a entidade referenciada.")
        if self.type == "quantity" and not self.unit:
            raise ValueError("Informe a unidade de medida.")
        if self.type == "table":
            if not self.columns or any(c.type == "table" for c in self.columns):
                raise ValueError("Tabela exige colunas; tabelas aninhadas não são permitidas.")
            validate_definitions(self.columns)
        elif self.columns:
            raise ValueError("Somente tabelas podem ter colunas.")
        return self


def validate_definitions(fields: list[FieldDefinition]) -> None:
    keys = [field.key for field in fields]
    if len(set(keys)) != len(keys):
        raise ValueError("Chaves de campos devem ser únicas.")
    for field in fields:
        if field.visible_when:
            controller = next((other for other in fields if other.key == field.visible_when.field), None)
            if not controller or controller.key == field.key or controller.visible_when or controller.type in ("table", "multiselect", "reference"):
                raise ValueError("Condição deve referenciar outro campo simples e incondicional.")
        if field.default is not None:
            validate_value(field, field.default)


class StageGate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stage_id: str
    required_fields: list[str] = Field(default_factory=list, max_length=100)
    checklist_required: bool = False
    allowed_roles: list[Literal["manager", "member", "observer"]] = Field(default_factory=list)


class TypeConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    fields: list[FieldDefinition] = Field(default_factory=list, max_length=100)
    gates: list[StageGate] = Field(default_factory=list, max_length=100)
    checklist_template_ids: list[str] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def check_configuration(self):
        validate_definitions(self.fields)
        keys = {field.key for field in self.fields}
        if len({gate.stage_id for gate in self.gates}) != len(self.gates):
            raise ValueError("Não repita o portão de uma etapa.")
        if any(set(gate.required_fields) - keys for gate in self.gates):
            raise ValueError("Portão referencia um campo inexistente.")
        return self


def empty(value: Any) -> bool:
    return value is None or value == "" or value == []


def visible(field: FieldDefinition, values: dict) -> bool:
    condition = field.visible_when
    return condition is None or values.get(condition.field) == condition.equals


def validate_value(field: FieldDefinition, value: Any) -> None:
    if empty(value):
        return
    kind = field.type
    if kind in ("number", "money", "quantity"):
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError(f"{field.label}: informe um número finito.")
        if field.minimum is not None and value < field.minimum or field.maximum is not None and value > field.maximum:
            raise ValueError(f"{field.label}: valor fora dos limites.")
    elif kind == "boolean":
        if type(value) is not bool:
            raise ValueError(f"{field.label}: informe sim ou não.")
    elif kind == "multiselect":
        if not isinstance(value, list) or any(not isinstance(v, str) for v in value) or len(value) != len(set(value)) or any(v not in field.options for v in value):
            raise ValueError(f"{field.label}: seleção inválida.")
    elif kind == "table":
        if not isinstance(value, list) or len(value) > field.max_rows:
            raise ValueError(f"{field.label}: quantidade de linhas inválida.")
        for row in value:
            validate_fields(field.columns, row)
    else:
        if not isinstance(value, str) or len(value) > field.max_length:
            raise ValueError(f"{field.label}: texto inválido ou muito longo.")
        if kind == "select" and value not in field.options:
            raise ValueError(f"{field.label}: opção inválida.")
        if field.pattern and not re.fullmatch(field.pattern, value):
            raise ValueError(f"{field.label}: formato inválido.")
        if kind in ("date", "datetime"):
            try:
                (date.fromisoformat if kind == "date" else datetime.fromisoformat)(value)
            except ValueError as exc:
                raise ValueError(f"{field.label}: data inválida.") from exc


def validate_fields(fields: list[FieldDefinition], values: dict, *, stage_id=None, creating=False, previous=None, roles=None) -> dict:
    if not isinstance(values, dict):
        raise ValueError("Campos personalizados devem ser um objeto.")
    result = deepcopy(values)
    keys = {field.key for field in fields}
    if set(result) - keys:
        raise ValueError("Há campos não definidos na versão do Tipo.")
    if creating:
        for field in fields:
            if field.key not in result and field.default is not None:
                result[field.key] = deepcopy(field.default)
    for field in fields:
        value = result.get(field.key)
        if previous is not None and value != previous.get(field.key) and field.editable_roles and not set(field.editable_roles) & set(roles or []):
            raise ValueError(f"{field.label}: seu papel não permite alterar este campo.")
        if visible(field, result) and (field.required or str(stage_id) in field.required_stages) and empty(value):
            raise ValueError(f"{field.label}: campo obrigatório nesta etapa.")
        validate_value(field, value)
    return result
