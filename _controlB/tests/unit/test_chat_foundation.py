"""Testes da fundação multiconector do módulo Chat."""

from __future__ import annotations

import asyncio
import json
import uuid

import httpx
import pytest

from controlb.modules.chat import schemas
from controlb.modules.chat.connectors.base import ConnectorError
from controlb.modules.chat.connectors.evolution import EvolutionConnector
from controlb.modules.chat.connectors.registry import create_connector
from controlb.modules.chat.crypto import decrypt_credentials, encrypt_credentials
from controlb.modules.chat.models import ChatConnection
from controlb.modules.identity.security import discover_system_permissions


def test_connector_credentials_are_encrypted_and_recoverable():
    credentials = {"api_key": "evolution-secret", "webhook_secret": "callback-secret"}

    ciphertext = encrypt_credentials(credentials)

    assert "evolution-secret" not in ciphertext
    assert "callback-secret" not in ciphertext
    assert decrypt_credentials(ciphertext) == credentials


def test_chat_permissions_are_discovered_by_identity_module():
    codes = {permission["code"] for permission in discover_system_permissions()}

    assert {"chat:view", "chat:send", "chat:link", "chat:manage_connectors"} <= codes


def test_connection_schema_normalizes_provider_url_and_hides_secret():
    payload = schemas.ChatConnectionCreate(
        provider=" evolution ",
        name=" WhatsApp Comercial ",
        base_url="https://evolution.example.test/",
        external_instance_id=" comercial ",
        api_key="super-secret-long-key",
    )

    assert payload.provider == "EVOLUTION"
    assert payload.base_url == "https://evolution.example.test"
    assert payload.external_instance_id == "comercial"
    assert "super-secret" not in repr(payload)


def test_chat_connection_keeps_provider_open_for_future_adapters():
    connection = ChatConnection(
        organization_id=uuid.uuid4(),
        provider="FUTURE_PROVIDER",
        name="Canal futuro",
        base_url="https://connector.example.test",
        external_instance_id="channel-1",
        credentials_ciphertext="ciphertext",
    )

    assert connection.provider == "FUTURE_PROVIDER"


def test_evolution_send_text_uses_official_endpoint_and_normalizes_response():
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.raw_path.decode("ascii")
        captured["apikey"] = request.headers.get("apikey")
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "key": {
                    "id": "MESSAGE-123",
                    "remoteJid": "5571999999999@s.whatsapp.net",
                },
                "status": "PENDING",
            },
        )

    async def run():
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        connector = EvolutionConnector(
            base_url="https://evolution.example.test",
            instance_name="comercial principal",
            api_key="api-key",
            client=client,
        )
        try:
            return await connector.send_text("+55 (71) 99999-9999", "Olá")
        finally:
            await client.aclose()

    result = asyncio.run(run())

    assert captured == {
        "path": "/message/sendText/comercial%20principal",
        "apikey": "api-key",
        "payload": {
            "number": "5571999999999",
            "text": "Olá",
        },
    }
    assert result.external_message_id == "MESSAGE-123"
    assert result.external_chat_id == "5571999999999@s.whatsapp.net"
    assert result.status == "PENDING"


def test_evolution_webhook_is_normalized_without_leaking_provider_shape():
    connector = EvolutionConnector(
        base_url="https://evolution.example.test",
        instance_name="comercial",
        api_key="api-key",
        client=httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200))),
    )
    payload = {
        "event": "messages.upsert",
        "instance": "comercial",
        "data": {
            "key": {
                "id": "MESSAGE-456",
                "remoteJid": "5571888888888@s.whatsapp.net",
                "fromMe": False,
            },
            "pushName": "Cliente",
            "messageTimestamp": 1_700_000_000,
            "message": {"conversation": "Tenho interesse na proposta"},
        },
    }

    event = connector.parse_webhook(payload)
    asyncio.run(connector._client.aclose())

    assert event.event_type == "MESSAGES_UPSERT"
    assert event.external_instance_id == "comercial"
    assert event.message is not None
    assert event.message.external_message_id == "MESSAGE-456"
    assert event.message.remote_phone == "5571888888888"
    assert event.message.direction == "INBOUND"
    assert event.message.content == "Tenho interesse na proposta"


def test_evolution_delivery_updates_keep_distinct_idempotency_keys():
    connector = EvolutionConnector(
        base_url="https://evolution.example.test",
        instance_name="comercial",
        api_key="api-key",
        client=httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200))),
    )
    base_payload = {
        "event": "messages.update",
        "instance": "comercial",
        "data": {
            "key": {"id": "MESSAGE-789", "remoteJid": "5571888888888@s.whatsapp.net"},
            "status": "DELIVERY_ACK",
        },
    }

    delivered = connector.parse_webhook(base_payload)
    read = connector.parse_webhook(
        {**base_payload, "data": {**base_payload["data"], "status": "READ"}}
    )
    duplicate = connector.parse_webhook(base_payload)
    asyncio.run(connector._client.aclose())

    assert delivered.event_key != read.event_key
    assert delivered.event_key == duplicate.event_key


def test_evolution_http_error_becomes_safe_connector_error():
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "Invalid API key"}})

    async def run():
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        connector = EvolutionConnector(
            base_url="https://evolution.example.test",
            instance_name="comercial",
            api_key="must-not-leak",
            client=client,
        )
        try:
            return await connector.get_connection_state()
        finally:
            await client.aclose()

    with pytest.raises(ConnectorError, match="HTTP 401") as exc_info:
        asyncio.run(run())

    assert exc_info.value.status_code == 401
    assert "must-not-leak" not in str(exc_info.value)


def test_registry_rejects_unregistered_provider():
    with pytest.raises(ValueError, match="não suportado"):
        create_connector("unknown", configuration={}, credentials={})
