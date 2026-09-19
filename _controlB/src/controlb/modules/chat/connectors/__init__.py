"""Contratos e adaptadores dos provedores suportados pelo Chat."""

from controlb.modules.chat.connectors.base import (
    ChatConnector,
    ConnectorConnectionState,
    ConnectorError,
    ConnectorMessageResult,
    ConnectorWebhookEvent,
    InboundMessage,
)
from controlb.modules.chat.connectors.registry import create_connector

__all__ = [
    "ChatConnector",
    "ConnectorConnectionState",
    "ConnectorError",
    "ConnectorMessageResult",
    "ConnectorWebhookEvent",
    "InboundMessage",
    "create_connector",
]
