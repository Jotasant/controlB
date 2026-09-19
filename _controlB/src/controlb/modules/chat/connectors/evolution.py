"""Adaptador do contrato de Chat para a Evolution API."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

import httpx

from controlb.modules.chat.connectors.base import (
    ChatConnector,
    ConnectorConnectionState,
    ConnectorError,
    ConnectorMessageResult,
    ConnectorWebhookEvent,
    InboundMessage,
)

EVOLUTION_WEBHOOK_EVENTS = (
    "MESSAGES_UPSERT",
    "MESSAGES_UPDATE",
    "SEND_MESSAGE",
    "CONNECTION_UPDATE",
)


class EvolutionConnector(ChatConnector):
    provider = "EVOLUTION"

    def __init__(
        self,
        *,
        base_url: str,
        instance_name: str,
        api_key: str,
        timeout_seconds: float = 20.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not base_url.strip():
            raise ValueError("Informe a URL da Evolution API.")
        if not instance_name.strip():
            raise ValueError("Informe o nome da instância Evolution API.")
        if not api_key:
            raise ValueError("Informe a chave da Evolution API.")

        self.base_url = base_url.rstrip("/")
        self.instance_name = instance_name.strip()
        self._client = client or httpx.AsyncClient(timeout=timeout_seconds)
        self._owns_client = client is None
        self._headers = {"apikey": api_key, "Content-Type": "application/json"}

    @property
    def _encoded_instance(self) -> str:
        return quote(self.instance_name, safe="")

    def chat_id_for_phone(self, phone: str) -> str:
        return f"{_normalize_number(phone)}@s.whatsapp.net"

    async def _request(
        self, method: str, path: str, *, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        try:
            response = await self._client.request(
                method,
                f"{self.base_url}{path}",
                headers=self._headers,
                json=payload,
                follow_redirects=False,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ConnectorError(
                f"A Evolution API recusou a operação (HTTP {exc.response.status_code}).",
                status_code=exc.response.status_code,
            ) from exc
        except httpx.HTTPError as exc:
            raise ConnectorError("Não foi possível comunicar com a Evolution API.") from exc

        if not response.content:
            return {}
        try:
            result = response.json()
        except ValueError as exc:
            raise ConnectorError("A Evolution API retornou uma resposta inválida.") from exc
        if not isinstance(result, dict):
            raise ConnectorError("A Evolution API retornou uma resposta inválida.")
        return result

    async def send_text(self, number: str, text: str) -> ConnectorMessageResult:
        normalized_number = _normalize_number(number)
        normalized_text = text.strip()
        if not normalized_text:
            raise ValueError("A mensagem não pode estar vazia.")

        result = await self._request(
            "POST",
            f"/message/sendText/{self._encoded_instance}",
            payload={"number": normalized_number, "text": normalized_text},
        )
        key = result.get("key") if isinstance(result.get("key"), dict) else {}
        external_id = str(key.get("id") or "").strip()
        if not external_id:
            raise ConnectorError("A Evolution API não retornou o identificador da mensagem.")
        external_chat_id = str(key.get("remoteJid") or normalized_number)
        return ConnectorMessageResult(
            external_message_id=external_id,
            external_chat_id=external_chat_id,
            status=_delivery_status(result.get("status")) or "PENDING",
        )

    async def get_connection_state(self) -> ConnectorConnectionState:
        result = await self._request("GET", f"/instance/connectionState/{self._encoded_instance}")
        instance = result.get("instance") if isinstance(result.get("instance"), dict) else {}
        raw_state = str(instance.get("state") or result.get("state") or "unknown").lower()
        normalized = {
            "open": "CONNECTED",
            "connected": "CONNECTED",
            "connecting": "CONNECTING",
            "close": "DISCONNECTED",
            "closed": "DISCONNECTED",
            "disconnected": "DISCONNECTED",
        }.get(raw_state, "ERROR")
        return ConnectorConnectionState(state=normalized, raw_payload=result)

    async def configure_webhook(self, url: str, secret: str) -> None:
        if not url.startswith(("https://", "http://")):
            raise ValueError("Informe uma URL pública válida para o webhook.")
        if not secret:
            raise ValueError("Informe o segredo de autenticação do webhook.")
        await self._request(
            "POST",
            f"/webhook/set/{self._encoded_instance}",
            payload={
                "webhook": {
                    "enabled": True,
                    "url": url,
                    "events": list(EVOLUTION_WEBHOOK_EVENTS),
                    "headers": {"X-ControlB-Webhook-Token": secret},
                    "base64": False,
                    "byEvents": False,
                }
            },
        )

    def parse_webhooks(self, payload: dict[str, Any]) -> list[ConnectorWebhookEvent]:
        data = payload.get("data")
        if isinstance(data, list):
            if len(data) > 100:
                raise ValueError("O lote excede 100 eventos.")
            return [self.parse_webhook({**payload, "data": item}) for item in data]
        return [self.parse_webhook(payload)]

    def parse_webhook(self, payload: dict[str, Any]) -> ConnectorWebhookEvent:
        event_type = (
            str(payload.get("event") or "UNKNOWN").upper().replace(".", "_").replace("-", "_")
        )
        if len(event_type) > 100 or not isinstance(payload.get("data"), dict):
            raise ValueError("Evento inválido.")
        instance = payload.get("instance") or payload.get("instanceName")
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        key = data.get("key") if isinstance(data.get("key"), dict) else {}
        external_id = str(key.get("id") or data.get("keyId") or "").strip()
        remote_jid = str(key.get("remoteJid") or data.get("remoteJid") or "").strip()
        if len(external_id) > 255 or len(remote_jid) > 255:
            raise ValueError("Identificador inválido.")

        message = None
        # Esta versão cobre conversas individuais. Grupos e LIDs sem número
        # resolvido não devem ser interpretados como telefones de clientes.
        personal = bool(re.fullmatch(r"[1-9][0-9]{7,14}@s\.whatsapp\.net", remote_jid))
        if event_type in {"MESSAGES_UPSERT", "SEND_MESSAGE"} and external_id and personal:
            direction = "OUTBOUND" if bool(key.get("fromMe")) else "INBOUND"
            message = InboundMessage(
                external_message_id=external_id,
                external_chat_id=remote_jid,
                remote_phone=_phone_from_jid(remote_jid),
                direction=direction,
                message_type=_message_type(data),
                content=_message_content(data),
                occurred_at=_message_datetime(data),
                sender_name=str(data.get("pushName") or "")[:255] or None,
            )

        # A criação da mensagem é idempotente pelo ID externo. Atualizações de
        # entrega/leitura usam o payload completo, pois o mesmo ID evolui por
        # vários estados legítimos (SENT -> DELIVERED -> READ).
        event_key_source = (
            f"{event_type}:{remote_jid}:{external_id}"
            if event_type in {"MESSAGES_UPSERT", "SEND_MESSAGE"} and external_id
            else _canonical_json({"event": event_type, "data": data})
        )
        event_key = hashlib.sha256(event_key_source.encode("utf-8")).hexdigest()
        return ConnectorWebhookEvent(
            event_key=event_key,
            event_type=event_type,
            external_instance_id=_optional_string(instance),
            message=message,
            external_message_id=external_id or None,
            external_chat_id=remote_jid or None,
            delivery_status=_delivery_status(data.get("status"))
            if event_type == "MESSAGES_UPDATE"
            else None,
            connection_state={
                "open": "CONNECTED",
                "connecting": "CONNECTING",
                "close": "DISCONNECTED",
            }.get(data.get("state"))
            if event_type == "CONNECTION_UPDATE"
            else None,
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()


def _normalize_number(number: str) -> str:
    value = number.strip()
    if value.endswith("@s.whatsapp.net"):
        value = value.split("@", 1)[0]
    if re.search(r"[^0-9+() .-]", value):
        raise ValueError("Informe um telefone individual válido.")
    normalized = re.sub(r"\D", "", value)
    if not re.fullmatch(r"[1-9][0-9]{7,14}", normalized):
        raise ValueError("Informe um número de WhatsApp válido, incluindo o código do país.")
    return normalized


def _phone_from_jid(remote_jid: str) -> str:
    return remote_jid.split("@", 1)[0].split(":", 1)[0]


def _message_type(data: dict[str, Any]) -> str:
    message = data.get("message") if isinstance(data.get("message"), dict) else {}
    if "conversation" in message or "extendedTextMessage" in message:
        return "TEXT"
    mapping = {
        "imageMessage": "IMAGE",
        "videoMessage": "VIDEO",
        "audioMessage": "AUDIO",
        "documentMessage": "DOCUMENT",
        "stickerMessage": "STICKER",
        "locationMessage": "LOCATION",
        "contactMessage": "CONTACT",
    }
    return next((kind for field, kind in mapping.items() if field in message), "UNKNOWN")


def _message_content(data: dict[str, Any]) -> str | None:
    message = data.get("message") if isinstance(data.get("message"), dict) else {}
    direct = message.get("conversation")
    if isinstance(direct, str):
        return direct
    extended = message.get("extendedTextMessage")
    if isinstance(extended, dict) and isinstance(extended.get("text"), str):
        return extended["text"]
    for field in ("imageMessage", "videoMessage", "documentMessage"):
        content = message.get(field)
        if isinstance(content, dict):
            caption = content.get("caption") or content.get("fileName")
            if isinstance(caption, str):
                return caption
    return None


def _message_datetime(data: dict[str, Any]) -> datetime:
    raw = data.get("messageTimestamp")
    try:
        return datetime.fromtimestamp(float(raw), tz=UTC)
    except (TypeError, ValueError, OSError, OverflowError):
        return datetime.now(UTC)


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _delivery_status(value: Any) -> str | None:
    return {
        "0": "FAILED",
        "ERROR": "FAILED",
        "FAILED": "FAILED",
        "1": "PENDING",
        "PENDING": "PENDING",
        "2": "SENT",
        "SERVER_ACK": "SENT",
        "SENT": "SENT",
        "3": "DELIVERED",
        "DELIVERY_ACK": "DELIVERED",
        "DELIVERED": "DELIVERED",
        "4": "READ",
        "5": "READ",
        "READ": "READ",
        "PLAYED": "READ",
    }.get(str(value).upper())
