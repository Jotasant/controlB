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
class InboundMessage:
    external_message_id: str
    external_chat_id: str
    remote_phone: str
    direction: str
    message_type: str
    content: str | None
    occurred_at: datetime
    sender_name: str | None = None


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


class ChatConnector(ABC):
    """Porta usada pelo domínio de Chat sem conhecer o fornecedor concreto."""

    provider: str

    @abstractmethod
    def chat_id_for_phone(self, phone: str) -> str:
        """Resolve o endereço do contato no provedor."""

    def parse_webhooks(self, payload: dict[str, Any]) -> list[ConnectorWebhookEvent]:
        return [self.parse_webhook(payload)]

    @abstractmethod
    async def send_text(self, number: str, text: str) -> ConnectorMessageResult:
        """Envia texto e devolve identificadores normalizados."""

    @abstractmethod
    async def get_connection_state(self) -> ConnectorConnectionState:
        """Consulta o estado da instância no provedor."""

    @abstractmethod
    async def configure_webhook(self, url: str, secret: str) -> None:
        """Configura os eventos necessários com autenticação do callback."""

    @abstractmethod
    def parse_webhook(self, payload: dict[str, Any]) -> ConnectorWebhookEvent:
        """Transforma o evento proprietário em uma estrutura do domínio."""

    async def aclose(self) -> None:
        """Libera recursos do adaptador, quando houver."""
