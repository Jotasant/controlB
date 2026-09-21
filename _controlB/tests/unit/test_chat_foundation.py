"""Testes da fundação multiconector do módulo Chat."""

from __future__ import annotations

import asyncio
import base64
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
        member_ids=[uuid.uuid4()],
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
    assert result.status == "SENT"


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


def test_evolution_creates_instance_and_normalizes_qr_code():
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["payload"] = json.loads(request.content) if request.content else None
        return httpx.Response(
            200,
            json={
                "instance": {"instanceName": "comercial", "status": "created"},
                "qrcode": {"base64": "iVBORw0KGgo=", "pairingCode": "XYZ1"},
            },
        )

    async def run():
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        connector = EvolutionConnector(
            base_url="https://evolution.example.test",
            instance_name="comercial",
            api_key="api-key",
            client=client,
        )
        try:
            return await connector.create_instance()
        finally:
            await client.aclose()

    result = asyncio.run(run())
    assert captured["path"] == "/instance/create"
    assert captured["payload"] == {
        "instanceName": "comercial",
        "qrcode": True,
        "integration": "WHATSAPP-BAILEYS",
    }
    assert result.created is True
    assert result.qr_code_base64 == "data:image/png;base64,iVBORw0KGgo="
    assert result.pairing_code == "XYZ1"


def test_evolution_reuses_existing_instance_without_leaking_provider_error():
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/instance/create"):
            return httpx.Response(403, json={"response": {"message": ["already in use"]}})
        return httpx.Response(200, json={"instance": {"state": "close"}})

    async def run():
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        connector = EvolutionConnector(
            base_url="https://evolution.example.test",
            instance_name="comercial",
            api_key="api-key",
            client=client,
        )
        try:
            return await connector.create_instance()
        finally:
            await client.aclose()

    result = asyncio.run(run())
    assert result.created is False
    assert result.already_existed is True
    assert result.state == "DISCONNECTED"


def test_evolution_pairing_uses_connect_endpoint():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert "/instance/connect/" in request.url.path
        return httpx.Response(200, json={"base64": "abc123", "pairingCode": "PAIR99"})

    async def run():
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        connector = EvolutionConnector(
            base_url="https://evolution.example.test",
            instance_name="comercial",
            api_key="api-key",
            client=client,
        )
        try:
            return await connector.get_pairing_session()
        finally:
            await client.aclose()

    result = asyncio.run(run())
    assert result.qr_code_base64 == "data:image/png;base64,abc123"
    assert result.pairing_code == "PAIR99"
    assert result.state == "CONNECTING"


@pytest.mark.parametrize("name", [None, "Nome salvo"])
def test_contact_lookup_is_scoped_to_instance_and_exact_recipient(name):
    async def handler(request):
        assert request.url.path == "/chat/findContacts/comercial"
        assert json.loads(request.content)["where"] == {"remoteJid": "5571999999999@s.whatsapp.net"}
        rows = [{"remoteJid": "5571888888888@s.whatsapp.net", "pushName": "Outro contato"}]
        if name:
            rows.append({"remoteJid": "5571999999999@s.whatsapp.net", "pushName": name})
        return httpx.Response(200, json=rows)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            adapter = EvolutionConnector(
                base_url="https://evolution.test",
                instance_name="comercial",
                api_key="key",
                client=client,
            )
            return await adapter.fetch_contact_name("5571999999999")

    assert asyncio.run(run()) == name


def test_registry_rejects_unregistered_provider():
    with pytest.raises(ValueError, match="não suportado"):
        create_connector("unknown", configuration={}, credentials={})


def test_local_transcription_requires_complete_model_without_network_fallback(
    tmp_path, monkeypatch
):
    from controlb.config import get_settings
    from controlb.modules.chat import audio

    monkeypatch.setattr(get_settings(), "chat_stt_model_path", str(tmp_path))
    monkeypatch.setattr(audio.importlib.util, "find_spec", lambda _: object())
    assert audio.transcription_ready() is False
    (tmp_path / "model.bin").write_bytes(b"fake-model-for-path-validation")
    (tmp_path / "config.json").write_text("{}")
    assert audio.transcription_ready() is False
    with pytest.raises(ValueError, match="Complete local model required"):
        audio._model(str(tmp_path))
    (tmp_path / "tokenizer.json").write_text("{}")
    assert audio.transcription_ready() is True
    monkeypatch.setattr(audio.importlib.util, "find_spec", lambda _: None)
    assert audio.transcription_ready() is False


@pytest.mark.parametrize("outbound", [False, True])
@pytest.mark.parametrize("wrapper", [None, "ephemeralMessage", "viewOnceMessageV2"])
def test_audio_envelopes_and_sender_names(outbound, wrapper):
    adapter = EvolutionConnector(
        base_url="https://evolution.test", instance_name="test", api_key="key"
    )
    message = {"audioMessage": {"mimetype": "audio/ogg; codecs=opus", "ptt": True}}
    if wrapper:
        message = {wrapper: {"message": message}}
    payload = {
        "event": "messages.upsert",
        "instance": "test",
        "data": {
            "key": {"id": "audio", "remoteJid": "5571999999999@s.whatsapp.net", "fromMe": outbound},
            "pushName": " ",
            "profileName": "Cliente correto",
            "message": message,
        },
    }
    try:
        parsed = adapter.parse_webhook(payload).message
        assert parsed.message_type == "AUDIO"
        assert parsed.sender_name == (None if outbound else "Cliente correto")
        payload["data"]["message"] = {
            "ephemeralMessage": {
                "message": {
                    "extendedTextMessage": {"text": "Veja https://exemplo.test/pagina?a=1&b=2"}
                }
            }
        }
        assert (
            adapter.parse_webhook(payload).message.content
            == "Veja https://exemplo.test/pagina?a=1&b=2"
        )
    finally:
        asyncio.run(adapter.aclose())


@pytest.mark.parametrize(
    "case", ["valid", "html", "invalid_base64", "oversized", "redirect", "wrong_shape"]
)
def test_audio_download_is_bounded_and_scoped_to_instance(case, monkeypatch):
    from controlb.modules.chat.connectors import evolution

    monkeypatch.setattr(evolution, "MAX_MEDIA_RESPONSE_BYTES", 256)

    async def handler(request):
        assert request.url.path == "/chat/getBase64FromMediaMessage/comercial"
        assert json.loads(request.content) == {
            "message": {
                "key": {
                    "id": "audio-1",
                    "remoteJid": "5571999999999@s.whatsapp.net",
                    "fromMe": False,
                }
            },
            "convertToMp4": False,
        }
        if case == "redirect":
            return httpx.Response(302, headers={"Location": "http://private.test/audio"})
        if case == "oversized":
            return httpx.Response(200, content=b"x" * 257)
        if case == "wrong_shape":
            return httpx.Response(200, json=[])
        return httpx.Response(
            200,
            json={
                "base64": "!!!!"
                if case == "invalid_base64"
                else base64.b64encode(b"OggS-test").decode(),
                "mimetype": "text/html" if case == "html" else "audio/ogg; codecs=opus",
            },
        )

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            adapter = EvolutionConnector(
                base_url="https://evolution.test",
                instance_name="comercial",
                api_key="key",
                client=client,
            )
            return await adapter.fetch_audio(
                "audio-1", "5571999999999@s.whatsapp.net", from_me=False
            )

    if case == "valid":
        media = asyncio.run(run())
        assert media.content == b"OggS-test"
        assert media.mime_type == "audio/ogg"
    else:
        with pytest.raises(ConnectorError):
            asyncio.run(run())


def test_lid_alias_is_resolved_but_groups_are_not_phones():
    connector = EvolutionConnector(
        base_url="https://evolution.test", instance_name="test", api_key="key"
    )
    payload = {
        "event": "messages.upsert",
        "instance": "test",
        "data": {
            "key": {
                "id": "msg",
                "remoteJid": "123@lid",
                "remoteJidAlt": "5571999999999@s.whatsapp.net",
            },
            "message": {"conversation": "Olá"},
        },
    }
    try:
        assert connector.parse_webhook(payload).message.remote_phone == "5571999999999"
        payload["data"]["key"]["remoteJid"] = "123@g.us"
        assert connector.parse_webhook(payload).message is None
        payload["data"]["key"] = {"id": "msg", "remoteJid": "123@lid"}
        assert connector.parse_webhook(payload).message is None
    finally:
        asyncio.run(connector.aclose())


def test_pairing_accepts_created_state_without_qr_and_rejects_unsafe_images():
    from controlb.modules.chat.connectors.evolution import _pairing_from_payload

    session = _pairing_from_payload({"instance": {"status": "created"}})
    assert session.state == "DISCONNECTED"
    assert session.qr_code_base64 is None
    for value in (
        "https://external.test/qr",
        "data:image/svg+xml;base64,aaa",
        "data:text/html;base64,aaa",
    ):
        assert _pairing_from_payload({"base64": value}).qr_code_base64 is None
