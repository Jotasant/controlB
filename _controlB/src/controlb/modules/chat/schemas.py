"""Contratos HTTP neutros de provedor para o módulo Chat."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any
from urllib.parse import urlsplit

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, SecretStr, field_validator


def validate_url(value: str) -> str:
    value = value.strip().rstrip("/")
    parts = urlsplit(value)
    if (
        parts.scheme not in {"http", "https"}
        or not parts.hostname
        or parts.username
        or parts.password
        or parts.query
        or parts.fragment
    ):
        raise ValueError("Informe URL HTTP/HTTPS sem credenciais, consulta ou fragmento.")
    return value


class ChatInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("configuration", check_fields=False)
    @classmethod
    def validate_configuration(cls, value):
        if value is None:
            return value
        if set(value) - {"timeout_seconds"}:
            raise ValueError("Configuração não reconhecida. Credenciais têm campos próprios.")
        if "timeout_seconds" in value:
            try:
                seconds = float(value["timeout_seconds"])
            except (TypeError, ValueError):
                raise ValueError("Timeout inválido.") from None
            if not 1 <= seconds <= 60:
                raise ValueError("Timeout deve ser entre 1 e 60 segundos.")
            value = {"timeout_seconds": seconds}
        return value

    @field_validator("api_key", "webhook_secret", check_fields=False)
    @classmethod
    def validate_secret(cls, value):
        if value is not None and not 16 <= len(value.get_secret_value().strip()) <= 4096:
            raise ValueError("O segredo deve conter entre 16 e 4096 caracteres.")
        return value


class ChatConnectionCreate(ChatInput):
    groups_enabled: bool = True
    member_ids: list[uuid.UUID] = Field(min_length=1, max_length=500)
    transcription_enabled: bool = False
    provider: str = "EVOLUTION"
    name: str = Field(..., min_length=2, max_length=120)
    base_url: str = Field(..., min_length=8, max_length=500)
    external_instance_id: str = Field(..., min_length=1, max_length=200)
    api_key: SecretStr
    webhook_secret: SecretStr | None = None
    configuration: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True

    @field_validator("provider")
    @classmethod
    def normalize_provider(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("Informe o provedor do conector.")
        return normalized

    @field_validator("base_url")
    @classmethod
    def normalize_base_url(cls, value: str) -> str:
        return validate_url(value)

    @field_validator("name", "external_instance_id")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        return value.strip()


class ChatConnectionUpdate(ChatInput):
    groups_enabled: bool | None = None
    member_ids: list[uuid.UUID] | None = Field(None, min_length=1, max_length=500)
    transcription_enabled: bool | None = None
    name: str | None = Field(None, min_length=2, max_length=120)
    base_url: str | None = Field(None, min_length=8, max_length=500)
    external_instance_id: str | None = Field(None, min_length=1, max_length=200)
    api_key: SecretStr | None = None
    webhook_secret: SecretStr | None = None
    configuration: dict[str, Any] | None = None
    is_active: bool | None = None

    @field_validator("base_url")
    @classmethod
    def normalize_base_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_url(value)

    @field_validator("name", "external_instance_id")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class ChatConnectionResponse(BaseModel):
    groups_enabled: bool
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    team_id: uuid.UUID | None
    member_ids: list[uuid.UUID]
    instance_phone: str | None
    provider_instance_id: str | None
    transcription_enabled: bool
    recovery_pending: bool
    sync_checkpoint_at: datetime | None
    organization_id: uuid.UUID
    provider: str
    name: str
    base_url: str
    external_instance_id: str
    credentials_hint: str | None
    configuration: dict[str, Any]
    status: str
    last_error: str | None
    last_synced_at: datetime | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ChatInstanceProvisionResponse(BaseModel):
    created: bool
    already_existed: bool
    qr_code_base64: str | None = None
    pairing_code: str | None = None
    connection: ChatConnectionResponse


class ChatPairingResponse(BaseModel):
    qr_code_base64: str | None = None
    pairing_code: str | None = None
    state: str
    connection: ChatConnectionResponse


class ChatInstanceDetailsResponse(BaseModel):
    instance_id: str | None
    instance_name: str
    phone: str | None
    profile_name: str | None
    integration: str | None
    state: str
    message_count: int | None
    chat_count: int | None
    local_message_count: int
    local_conversation_count: int
    last_webhook_at: datetime | None


class ChatHistoryRequest(ChatInput):
    page: int = Field(1, ge=1, le=1000000)
    page_size: int = Field(100, ge=1, le=100)
    snapshot_at: AwareDatetime | None = None


class ChatHistoryResponse(BaseModel):
    imported: int
    skipped: int
    existing: int
    scanned: int
    total: int
    next_page: int | None
    snapshot_at: datetime


class ChatConversationLinkCreate(ChatInput):
    business_document_id: uuid.UUID
    link_type: str = Field("RELATED", pattern="^(ORIGIN|RELATED)$")
    is_primary: bool = False


class ChatConversationCreate(ChatInput):
    connection_id: uuid.UUID
    business_document_id: uuid.UUID | None = None
    remote_phone: str
    display_name: str | None = Field(None, max_length=255)
    contact_id: uuid.UUID | None = None
    customer_id: uuid.UUID | None = None

    @field_validator("remote_phone")
    @classmethod
    def normalize_phone(cls, value: str) -> str:
        if re.search(r"[^0-9+() .-]", value):
            raise ValueError("Informe telefone com DDI e DDD.")
        number = re.sub(r"\D", "", value)
        if not re.fullmatch(r"[1-9][0-9]{7,14}", number):
            raise ValueError("Informe telefone com DDI e DDD.")
        return number


class ChatConversationStart(ChatInput):
    connection_id: uuid.UUID
    contact_id: uuid.UUID


class ChatConversationUpdate(ChatInput):
    status: str | None = Field(None, pattern="^(OPEN|CLOSED)$")
    is_archived: bool | None = None
    assigned_user_id: uuid.UUID | None = None
    contact_id: uuid.UUID | None = None
    customer_id: uuid.UUID | None = None


class ChatContactOriginUpdate(ChatInput):
    origin_id: uuid.UUID | None = None
    name: str | None = Field(None, min_length=1, max_length=100)


class ChatLinkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    business_document_id: uuid.UUID
    link_type: str
    is_primary: bool


class ChatConversationResponse(BaseModel):
    is_group: bool
    assigned_user_name: str | None
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    team_id: uuid.UUID | None
    instance_phone: str | None
    is_archived: bool
    closed_at: datetime | None
    closed_by_id: uuid.UUID | None
    organization_id: uuid.UUID
    connection_id: uuid.UUID
    external_chat_id: str
    remote_phone: str
    display_name: str | None
    avatar_url: str | None
    contact_id: uuid.UUID | None
    customer_id: uuid.UUID | None
    assigned_user_id: uuid.UUID | None
    status: str
    unread_count: int
    last_message_preview: str | None
    last_message_at: datetime | None
    created_at: datetime
    updated_at: datetime
    document_links: list[ChatLinkResponse] = Field(default_factory=list)


class SendTextMessageRequest(ChatInput):
    client_request_id: uuid.UUID
    reply_to_message_id: uuid.UUID | None = None
    text: str = Field(..., min_length=1, max_length=10000)

    @field_validator("text")
    @classmethod
    def strip_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("A mensagem não pode estar vazia.")
        return normalized


class ChatMessageResponse(BaseModel):
    reply_to_message_id: uuid.UUID | None
    reply_snapshot: dict[str, Any] | None
    reactions: list[dict[str, Any]] = Field(default_factory=list)
    deleted_at: datetime | None
    revoke_status: str | None
    sender_external_id: str | None
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_by_id: uuid.UUID | None
    author_name: str | None
    team_id: uuid.UUID | None
    instance_phone: str | None
    transcription: str | None
    transcription_status: str
    organization_id: uuid.UUID
    conversation_id: uuid.UUID
    external_message_id: str | None
    client_request_id: uuid.UUID | None
    direction: str
    message_type: str
    content: str | None
    media_url: str | None
    media_mime_type: str | None
    media_filename: str | None
    status: str
    sender_name: str | None
    sender_phone: str | None
    error_message: str | None
    occurred_at: datetime
    delivered_at: datetime | None
    read_at: datetime | None
    created_at: datetime


class ConversationPage(BaseModel):
    items: list[ChatConversationResponse]
    total: int
    page: int
    page_size: int


class ChatReactionRequest(ChatInput):
    client_request_id: uuid.UUID
    emoji: str = Field(pattern="^(👍|❤️|😂|😮|😢|🙏|)$")


class MessagePage(BaseModel):
    items: list[ChatMessageResponse]
    total: int
    page: int
    page_size: int
