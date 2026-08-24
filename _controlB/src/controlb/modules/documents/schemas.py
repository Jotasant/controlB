"""Contratos da API de documentos, cadeia, relacionamentos e timeline documental."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DocumentBase(BaseModel):
    category: str = Field(..., description="Categoria de negócio do documento (ex: crm.lead, sales.order, purchase.request)")
    document_type: str = Field(..., description="Tipo legado do documento (ex: LEAD, SALES_ORDER)")
    document_number: str | None = Field(None, description="Número legível do documento gerado automaticamente se omitido")
    title: str = Field(..., description="Título ou objeto do documento")
    current_status: str = Field(default="DRAFT", description="Status do ciclo de vida")
    priority: str = Field(default="MEDIUM", description="Prioridade: LOW, MEDIUM, HIGH, URGENT")
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    origin_module: str = Field(default="DOCUMENTS", description="Módulo originador")
    responsible_id: uuid.UUID | None = None
    payload: dict[str, Any] = Field(default_factory=dict, description="Dados específicos da categoria")
    issued_at: datetime | None = None
    completed_at: datetime | None = None


class DocumentCreate(DocumentBase):
    native_id: uuid.UUID | None = None


class DocumentUpdate(BaseModel):
    title: str | None = None
    current_status: str | None = None
    priority: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    responsible_id: uuid.UUID | None = None
    payload: dict[str, Any] | None = None
    completed_at: datetime | None = None


class DocumentResponse(DocumentBase):
    id: uuid.UUID
    organization_id: uuid.UUID
    native_id: uuid.UUID
    created_by_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentNodeResponse(BaseModel):
    id: uuid.UUID
    category: str = "generic"
    document_type: str
    native_id: uuid.UUID
    document_number: str
    title: str = ""
    current_status: str
    priority: str = "MEDIUM"
    origin_module: str = "DOCUMENTS"
    issued_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentRelationCreate(BaseModel):
    parent_document_id: uuid.UUID
    child_document_id: uuid.UUID
    relation_type: str = Field(..., description="Tipo de relação: originated_from, generated, depends_on, replaces, cancels, references")
    relation_metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentRelationResponse(BaseModel):
    id: uuid.UUID
    parent_document_id: uuid.UUID
    child_document_id: uuid.UUID
    relation_type: str
    relation_metadata: dict[str, Any]
    created_by_id: uuid.UUID | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentEventCreate(BaseModel):
    event_type: str = Field(..., description="Tipo de evento: CREATED, STATUS_CHANGED, APPROVED, REJECTED, CANCELLED, COMMENT, etc.")
    previous_status: str | None = None
    new_status: str | None = None
    event_metadata: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = None


class DocumentEventResponse(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    event_type: str
    previous_status: str | None = None
    new_status: str | None = None
    event_metadata: dict[str, Any]
    created_by_id: uuid.UUID | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentChainResponse(BaseModel):
    root_document_id: uuid.UUID
    documents: list[DocumentNodeResponse]
    relations: list[DocumentRelationResponse]
    events: list[DocumentEventResponse]


class DocumentTreeResponse(BaseModel):
    document: DocumentResponse
    origin: list[DocumentNodeResponse] = Field(default_factory=list)
    previous: list[DocumentNodeResponse] = Field(default_factory=list)
    derived: list[DocumentNodeResponse] = Field(default_factory=list)
    related: list[DocumentNodeResponse] = Field(default_factory=list)
    dependencies: list[DocumentNodeResponse] = Field(default_factory=list)
    timeline: list[DocumentEventResponse] = Field(default_factory=list)


class DocumentFilterParams(BaseModel):
    category: str | None = None
    origin_module: str | None = None
    current_status: str | None = None
    responsible_id: uuid.UUID | None = None
    search: str | None = None
    tag: str | None = None
    limit: int = 100
    offset: int = 0
