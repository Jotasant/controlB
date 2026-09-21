"""Contrato independente de fornecedor para canais de comunicação."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


class ConnectorError(RuntimeError):
    """Erro controlado ao comunicar com um provedor externo."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True, slots=True)
class ConnectorAudio:
    content: bytes
    mime_type: str


@dataclass(frozen=True, slots=True)
class ConnectorMedia:
    content: bytes
    mime_type: str
    filename: str | None = None


@dataclass(frozen=True, slots=True)
class ConnectorMessageResult:
    external_message_id: str
    external_chat_id: str
    status: str
    raw_payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ConnectorConnectionState:
    state: str
    raw_payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ConnectorInstanceResult:
    created: bool
    already_existed: bool = False
    state: str = "CONNECTING"
    qr_code_base64: str | None = None
    pairing_code: str | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ConnectorPairingSession:
    state: str
    qr_code_base64: str | None = None
    pairing_code: str | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class InboundMessage:
    external_message_id: str
    external_chat_id: str
    remote_phone: str
    direction: str
    message_type: str
    content: str | None
    occurred_at: datetime
    sender_name: str | None = None
    contact_name: str | None = None
    contact_lookup_done: bool = False
    is_group: bool = False
    group_name: str | None = None
    sender_phone: str | None = None
    sender_external_id: str | None = None
    media_mime_type: str | None = None
    media_filename: str | None = None
    reply: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class ConnectorWebhookEvent:
    event_key: str
    event_type: str
    external_instance_id: str | None
    message: InboundMessage | None
    raw_payload: dict[str, Any] = field(default_factory=dict)
    external_message_id: str | None = None
    external_chat_id: str | None = None
    delivery_status: str | None = None
    connection_state: str | None = None
    contact_phone: str | None = None
    contact_name: str | None = None
    group_id: str | None = None
    group_name: str | None = None

    reaction: dict[str, Any] | None = None


class ChatConnector(ABC):
    """Porta usada pelo domínio de Chat sem conhecer o fornecedor concreto."""

    provider: str

    async def fetch_avatar(self, destination: str) -> ConnectorMedia | None:
        raise ConnectorError("Este conector não consulta fotos de perfil.")

    async def send_reaction(self, key: dict[str, Any], emoji: str) -> None:
        raise ConnectorError("Este conector não oferece reações.")

    async def fetch_group_name(self, group_id: str) -> str | None:
        raise ConnectorError("Este conector não consulta nomes de grupos.")

    async def fetch_media(
        self,
        external_message_id: str,
        external_chat_id: str,
        *,
        from_me: bool,
        participant: str | None = None,
    ) -> ConnectorMedia:
        raise ConnectorError("Este conector não oferece download de mídia.")

    async def send_media(
        self,
        destination: str,
        content: bytes,
        mime_type: str,
        filename: str,
        caption: str,
        message_type: str,
        *, quoted: dict[str, Any] | None = None,
    ) -> ConnectorMessageResult:
        raise ConnectorError("Este conector não oferece envio de anexos.")

    async def delete_for_everyone(
        self, external_message_id: str, external_chat_id: str, *, participant: str | None = None
    ) -> None:
        raise ConnectorError("Este conector não permite apagar mensagens no provedor.")

    async def fetch_groups(self) -> list[dict[str, str]]:
        raise ConnectorError("Este conector não oferece consulta de grupos.")

    async def configure_groups(self, enabled: bool) -> None:
        raise ConnectorError("Este conector não oferece configuração de grupos.")

    async def send_group_text(self, group_id: str, text: str, *, quoted: dict[str, Any] | None = None) -> ConnectorMessageResult:
        raise ConnectorError("Este conector não oferece envio a grupos.")

    async def fetch_contact_name(self, phone: str) -> str | None:
        raise ConnectorError("Este conector não oferece consulta de contatos.")

    async def fetch_audio(
        self,
        external_message_id: str,
        external_chat_id: str,
        *,
        from_me: bool,
        participant: str | None = None,
    ) -> ConnectorAudio:
        raise ConnectorError("Este provedor não oferece download autenticado de áudio.")

    async def get_instance_details(self) -> ConnectorInstanceDetails:
        raise ConnectorError("Este provedor não oferece detalhes da instância.")

    async def fetch_history(
        self, page: int, page_size: int, snapshot_at: datetime
    ) -> ConnectorHistoryPage:
        raise ConnectorError("Este provedor não oferece importação de histórico.")

    @abstractmethod
    def chat_id_for_phone(self, phone: str) -> str:
        """Resolve o endereço do contato no provedor."""

    def parse_webhooks(self, payload: dict[str, Any]) -> list[ConnectorWebhookEvent]:
        return [self.parse_webhook(payload)]

    @abstractmethod
    async def send_text(self, number: str, text: str, *, quoted: dict[str, Any] | None = None) -> ConnectorMessageResult:
        """Envia texto e devolve identificadores normalizados."""

    @abstractmethod
    async def get_connection_state(self) -> ConnectorConnectionState:
        """Consulta o estado da instância no provedor."""

    @abstractmethod
    async def configure_webhook(self, url: str, secret: str) -> None:
        """Configura os eventos necessários com autenticação do callback."""

    async def create_instance(self) -> ConnectorInstanceResult:
        """Cria a instância no provedor. Outros conectores podem recusar."""
        raise ConnectorError("Este provedor não cria instâncias pelo ControlB.")

    async def get_pairing_session(self) -> ConnectorPairingSession:
        """Obtém QR Code ou código de pareamento, quando o provedor oferecer."""
        raise ConnectorError("Este provedor não oferece pareamento pelo ControlB.")

    @abstractmethod
    def parse_webhook(self, payload: dict[str, Any]) -> ConnectorWebhookEvent:
        """Transforma o evento proprietário em uma estrutura do domínio."""

    async def aclose(self) -> None:
        """Libera recursos do adaptador, quando houver."""


@dataclass(frozen=True, slots=True)
class ConnectorInstanceDetails:
    instance_id: str | None
    instance_name: str
    phone: str | None
    profile_name: str | None
    integration: str | None
    state: str
    message_count: int | None
    chat_count: int | None


@dataclass(frozen=True, slots=True)
class ConnectorHistoryPage:
    events: list[ConnectorWebhookEvent]
    total: int
    has_more: bool
