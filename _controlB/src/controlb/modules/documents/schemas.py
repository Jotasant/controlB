"""Contratos da API de cadeia e timeline documental."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class DocumentNodeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_type: str
    native_id: uuid.UUID
    document_number: str
    current_status: str
    issued_at: datetime | None = None
    created_at: datetime


class DocumentRelationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    parent_document_id: uuid.UUID
    child_document_id: uuid.UUID
    relation_type: str
    relation_metadata: dict[str, Any]
    created_at: datetime


class DocumentEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    event_type: str
    previous_status: str | None = None
    new_status: str | None = None
    event_metadata: dict[str, Any]
    created_by_id: uuid.UUID | None = None
    created_at: datetime


class DocumentChainResponse(BaseModel):
    root_document_id: uuid.UUID
    documents: list[DocumentNodeResponse]
    relations: list[DocumentRelationResponse]
    events: list[DocumentEventResponse]
