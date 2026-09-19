"""Exercita o gateway HTTP em PostgreSQL isolado, com transporte externo simulado."""

import asyncio
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from controlb.config import get_settings
from controlb.db import SessionLocal, get_db
from controlb.main import app
from controlb.modules.chat import schemas, service
from controlb.modules.chat.connectors import registry
from controlb.modules.chat.connectors.evolution import EvolutionConnector
from controlb.modules.chat.crypto import decrypt_credentials
from controlb.modules.chat.models import (
    ChatConnection,
    ChatConversationLink,
    ChatWebhookEvent,
)
from controlb.modules.documents.models import BusinessDocument
from controlb.modules.identity.models import Organization, Permission, Role, User
from controlb.modules.identity.security import get_current_user


@pytest.fixture
def gateway(monkeypatch):
    with SessionLocal() as db:
        org = Organization(name="Chat test")
        other_org = Organization(name="Other Chat test")
        db.add_all([org, other_org])
        db.flush()
        codes = [
            "chat:view",
            "chat:link",
            "chat:send",
            "chat:manage_connectors",
            "sales:view",
            "projects:view",
        ]
        perms = []
        for code in codes:
            perm = db.scalar(select(Permission).where(Permission.code == code))
            if not perm:
                perm = Permission(code=code, name=code, module="test")
                db.add(perm)
                db.flush()
            perms.append(perm)
        role = Role(organization_id=org.id, name="Chat operator", permissions=perms)
        reader = Role(
            organization_id=org.id,
            name="Reader",
            permissions=[p for p in perms if p.code in {"chat:view", "sales:view"}],
        )
        db.add_all([role, reader])
        db.flush()
        user = User(
            organization_id=org.id,
            role_id=role.id,
            email=f"{uuid.uuid4()}@test.example",
            full_name="Chat",
            hashed_password="hash",
        )
        user.role = role
        db.add(user)
        db.flush()
        doc = BusinessDocument(
            organization_id=org.id,
            native_id=uuid.uuid4(),
            document_type="SALES_QUOTE",
            document_number=str(uuid.uuid4()),
            current_status="DRAFT",
            title="Proposta",
        )
        project = BusinessDocument(
            organization_id=org.id,
            native_id=uuid.uuid4(),
            document_type="PROJECT",
            document_number=str(uuid.uuid4()),
            current_status="DRAFT",
            title="Projeto",
        )
        other_doc = BusinessDocument(
            organization_id=other_org.id,
            native_id=uuid.uuid4(),
            document_type="SALES_QUOTE",
            document_number=str(uuid.uuid4()),
            current_status="DRAFT",
            title="Outra proposta",
        )
        db.add_all([doc, project, other_doc])
        db.commit()
        state = SimpleNamespace(
            db=db,
            user=user,
            org=org,
            other_org=other_org,
            doc=doc,
            project=project,
            other_doc=other_doc,
            reader=reader,
            calls=[],
            transport_status=200,
            timeout=False,
        )
        monkeypatch.setattr(get_settings(), "chat_allowed_base_urls", ["https://evolution.test"])
        monkeypatch.setattr(get_settings(), "chat_public_base_url", "https://controlb.test/api")

        def transport(request):
            body = json.loads(request.content) if request.content else None
            state.calls.append((request.url.path, body))
            if state.timeout:
                raise httpx.ReadTimeout("simulated", request=request)
            if state.transport_status != 200:
                return httpx.Response(
                    state.transport_status, json={"message": "secret-key-must-not-leak"}
                )
            if "sendText" in request.url.path:
                return httpx.Response(
                    200,
                    json={
                        "key": {"id": "sent-1", "remoteJid": "5571999999999@s.whatsapp.net"},
                        "status": "PENDING",
                    },
                )
            if "connectionState" in request.url.path:
                return httpx.Response(200, json={"instance": {"state": "open"}})
            return httpx.Response(200, json={"enabled": True})

        def factory(configuration, credentials):
            adapter = EvolutionConnector(
                base_url=configuration["base_url"],
                instance_name=configuration["instance_name"],
                api_key=credentials["api_key"],
                client=httpx.AsyncClient(transport=httpx.MockTransport(transport)),
            )
            adapter._owns_client = True
            return adapter

        monkeypatch.setitem(registry._CONNECTOR_FACTORIES, "EVOLUTION", factory)

        def db_dependency():
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise

        app.dependency_overrides[get_db] = db_dependency
        app.dependency_overrides[get_current_user] = lambda: state.user
        with TestClient(app) as client:
            state.client = client
            response = client.post(
                "/chat/connections",
                json={
                    "name": "Comercial",
                    "base_url": "https://evolution.test",
                    "external_instance_id": "comercial",
                    "api_key": "secret-key-must-not-leak",
                    "webhook_secret": "webhook-secret-must-not-leak",
                },
            )
            assert response.status_code == 201, response.text
            state.connection_id = response.json()["id"]
            yield state
        app.dependency_overrides.clear()


def create_conversation(g):
    response = g.client.post(
        "/chat/conversations",
        json={
            "connection_id": g.connection_id,
            "business_document_id": str(g.doc.id),
            "remote_phone": "+55 (71) 99999-9999",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def webhook(g, data, event="messages.upsert", **extras):
    return g.client.post(
        f"/chat/webhooks/{g.connection_id}",
        headers={"X-ControlB-Webhook-Token": "webhook-secret-must-not-leak"},
        json={"event": event, "instance": "comercial", "data": data, **extras},
    )


def incoming(identifier="in-1"):
    return {
        "key": {"id": identifier, "remoteJid": "5571999999999@s.whatsapp.net", "fromMe": False},
        "pushName": "Cliente",
        "messageTimestamp": 1700000000,
        "message": {"conversation": "Olá"},
    }


def test_configuration_encrypts_secrets_and_uses_v2_contract(gateway):
    g = gateway
    stored = g.db.get(ChatConnection, uuid.UUID(g.connection_id))
    assert "secret-key-must-not-leak" not in stored.credentials_ciphertext
    assert (
        decrypt_credentials(stored.credentials_ciphertext)["api_key"] == "secret-key-must-not-leak"
    )
    result = g.client.get(f"/chat/connections/{g.connection_id}")
    assert "secret-key-must-not-leak" not in result.text
    assert "webhook-secret-must-not-leak" not in result.text
    assert (
        g.client.post(f"/chat/connections/{g.connection_id}/check").json()["status"] == "CONNECTED"
    )
    assert g.client.post(f"/chat/connections/{g.connection_id}/webhook").status_code == 200
    _, body = g.calls[-1]
    assert body["webhook"]["url"] == f"https://controlb.test/api/chat/webhooks/{g.connection_id}"
    assert body["webhook"]["byEvents"] is False
    assert body["webhook"]["headers"]["X-ControlB-Webhook-Token"] == "webhook-secret-must-not-leak"


def test_connections_and_validation_do_not_leak_credentials(gateway):
    g = gateway
    response = g.client.post("/chat/connections", json={"name": "x", "api_key": "short-secret"})
    assert response.status_code == 422
    assert "short-secret" not in response.text
    response = g.client.patch(
        f"/chat/connections/{g.connection_id}", json={"configuration": {"api_key": "leak"}}
    )
    assert response.status_code == 422
    response = g.client.patch(
        f"/chat/connections/{g.connection_id}", json={"base_url": "http://169.254.169.254"}
    )
    assert response.status_code == 422
    assert not g.calls
    g.user.role = g.reader
    assert g.client.get("/chat/connections").status_code == 403
    assert g.client.get("/chat/channels").status_code == 200
    assert "base_url" not in g.client.get("/chat/channels").text


def test_document_links_are_scoped_and_applied_to_list_detail_and_send(gateway):
    g = gateway
    conv = create_conversation(g)
    assert (
        g.client.post(
            f"/chat/conversations/{conv}/links", json={"business_document_id": str(g.other_doc.id)}
        ).status_code
        == 404
    )
    assert (
        g.client.post(
            f"/chat/conversations/{conv}/links", json={"business_document_id": str(g.project.id)}
        ).status_code
        == 200
    )
    g.user.role = g.reader
    assert g.client.get("/chat/conversations").json()["total"] == 0
    assert g.client.get(f"/chat/conversations/{conv}").status_code == 404
    assert g.client.get(f"/chat/conversations/{conv}/messages").status_code == 404
    assert (
        g.client.post(
            f"/chat/conversations/{conv}/messages",
            json={"client_request_id": str(uuid.uuid4()), "text": "Oi"},
        ).status_code
        == 403
    )


def test_cross_organization_reads_and_foreign_keys_are_blocked(gateway):
    g = gateway
    conv = create_conversation(g)
    with g.db.begin_nested():
        bad = ChatConversationLink(
            organization_id=g.org.id,
            conversation_id=uuid.UUID(conv),
            business_document_id=g.other_doc.id,
        )
        with pytest.raises(IntegrityError), g.db.begin_nested():
            g.db.add(bad)
            g.db.flush()
    g.user = SimpleNamespace(id=g.user.id, organization_id=g.other_org.id, role=g.user.role)
    assert g.client.get(f"/chat/conversations/{conv}").status_code == 404
    assert g.client.get(f"/chat/connections/{g.connection_id}").status_code == 404
    assert g.client.get("/chat/conversations").json()["total"] == 0


def test_send_request_replay_does_not_send_twice(gateway):
    g = gateway
    conv = create_conversation(g)
    body = {"client_request_id": str(uuid.uuid4()), "text": "Olá cliente"}
    result = g.client.post(f"/chat/conversations/{conv}/messages", json=body)
    assert result.status_code == 200, result.text
    repeated = g.client.post(f"/chat/conversations/{conv}/messages", json=body)
    assert repeated.json()["id"] == result.json()["id"]
    assert g.calls == [
        ("/message/sendText/comercial", {"number": "5571999999999", "text": "Olá cliente"})
    ]
    assert (
        g.client.post(
            f"/chat/conversations/{conv}/messages", json={**body, "text": "diferente"}
        ).status_code
        == 409
    )
    assert g.client.get(f"/chat/conversations/{conv}/messages").json()["total"] == 1


@pytest.mark.parametrize(
    ("transport_status", "timeout", "expected"),
    [(401, False, "FAILED"), (500, False, "PENDING"), (200, True, "PENDING")],
)
def test_failed_or_ambiguous_send_is_durable_without_automatic_retry(
    gateway, transport_status, timeout, expected
):
    g = gateway
    conv = create_conversation(g)
    g.transport_status, g.timeout = transport_status, timeout
    body = {"client_request_id": str(uuid.uuid4()), "text": "Mensagem"}
    result = g.client.post(f"/chat/conversations/{conv}/messages", json=body)
    assert result.status_code == 200, result.text
    assert result.json()["status"] == expected
    assert "secret-key-must-not-leak" not in result.text
    assert (
        g.client.post(f"/chat/conversations/{conv}/messages", json=body).json()["id"]
        == result.json()["id"]
    )
    assert len(g.calls) == 1


def test_webhook_auth_duplicates_and_secret_scrubbing(gateway):
    g = gateway
    assert g.client.post(f"/chat/webhooks/{g.connection_id}", json={}).status_code == 401
    result = webhook(g, incoming(), apikey="secret-key-must-not-leak")
    assert result.status_code == 200, result.text
    assert webhook(g, incoming()).json()["events"] == 0
    rows = g.client.get("/chat/conversations?unlinked=true").json()
    assert rows["total"] == 1
    conv = rows["items"][0]
    assert conv["unread_count"] == 1
    assert not conv["document_links"]
    inbox = g.db.scalar(
        select(ChatWebhookEvent).where(ChatWebhookEvent.connection_id == uuid.UUID(g.connection_id))
    )
    assert "secret-key-must-not-leak" not in json.dumps(inbox.payload)
    assert (
        g.client.post(
            f"/chat/conversations/{conv['id']}/messages",
            json={"client_request_id": str(uuid.uuid4()), "text": "Oi"},
        ).status_code
        == 409
    )
    assert (
        g.client.post(
            f"/chat/conversations/{conv['id']}/links", json={"business_document_id": str(g.doc.id)}
        ).status_code
        == 200
    )
    g.user.role = g.reader
    assert g.client.get("/chat/conversations").json()["total"] == 1


def test_webhook_status_before_message_and_no_regression(gateway):
    g = gateway
    update = {"keyId": "sent-1", "remoteJid": "5571999999999@s.whatsapp.net", "status": "READ"}
    assert webhook(g, update, "messages.update").status_code == 200
    conv = create_conversation(g)
    result = g.client.post(
        f"/chat/conversations/{conv}/messages",
        json={"client_request_id": str(uuid.uuid4()), "text": "Mensagem"},
    )
    assert result.json()["status"] == "READ", result.text
    assert webhook(g, {**update, "status": "DELIVERY_ACK"}, "messages.update").status_code == 200
    echo = incoming("sent-1")
    echo["key"]["fromMe"] = True
    assert webhook(g, echo).status_code == 200
    result = g.client.get(f"/chat/conversations/{conv}/messages").json()
    assert result["total"] == 1
    assert result["items"][0]["status"] == "READ"
    assert result["items"][0]["read_at"] is not None


def test_webhook_batches_and_disabled_connections(gateway):
    g = gateway
    assert webhook(g, [incoming("a"), incoming("b")]).json()["events"] == 2
    assert webhook(g, incoming(), instance="wrong").status_code == 403
    assert webhook(g, "invalid").status_code == 422
    assert (
        g.client.patch(
            f"/chat/connections/{g.connection_id}", json={"is_active": False}
        ).status_code
        == 200
    )
    assert webhook(g, incoming()).status_code == 401


def test_creation_requires_origin_and_foreign_contacts_are_rejected(gateway):
    g = gateway
    assert (
        g.client.post(
            "/chat/conversations",
            json={"connection_id": g.connection_id, "remote_phone": "5571999999999"},
        ).status_code
        == 422
    )
    result = g.client.post(
        "/chat/conversations",
        json={
            "connection_id": g.connection_id,
            "business_document_id": str(g.doc.id),
            "remote_phone": "5571999999999",
            "contact_id": str(uuid.uuid4()),
        },
    )
    assert result.status_code == 422


def test_pagination_and_shared_read_marker(gateway):
    g = gateway
    conv = create_conversation(g)
    assert webhook(g, [incoming("a"), incoming("b")]).status_code == 200
    page = g.client.get(f"/chat/conversations/{conv}/messages?page_size=1").json()
    second = g.client.get(f"/chat/conversations/{conv}/messages?page_size=1&page=2").json()
    assert page["total"] == second["total"] == 2
    assert page["items"][0]["id"] != second["items"][0]["id"]
    assert g.client.post(f"/chat/conversations/{conv}/read").json()["unread_count"] == 0
    assert g.client.get("/chat/conversations?page_size=101").status_code == 422


def test_concurrent_send_reuses_durable_request(gateway):
    g = gateway
    conv = uuid.UUID(create_conversation(g))
    user_id = g.user.id
    data = schemas.SendTextMessageRequest(client_request_id=uuid.uuid4(), text="Um envio")
    barrier = Barrier(2)

    def send():
        with SessionLocal() as db:
            user = db.get(User, user_id)
            barrier.wait(timeout=10)
            message = asyncio.run(service.send_text(db, user, conv, data))
            identifier = message.id
            db.commit()
            return identifier

    with ThreadPoolExecutor(max_workers=2) as executor:
        first, second = list(executor.map(lambda _: send(), range(2)))
    assert first == second
    assert len(g.calls) == 1
    assert g.client.get(f"/chat/conversations/{conv}/messages").json()["total"] == 1


def test_concurrent_callbacks_increment_unread_once(gateway):
    g = gateway
    conv = create_conversation(g)
    connection_id = uuid.UUID(g.connection_id)
    barrier = Barrier(2)

    def receive():
        with SessionLocal() as db:
            barrier.wait(timeout=10)
            result = asyncio.run(
                service.receive_webhook(
                    db,
                    connection_id,
                    "webhook-secret-must-not-leak",
                    {"event": "messages.upsert", "instance": "comercial", "data": incoming()},
                )
            )
            db.commit()
            return result["events"]

    with ThreadPoolExecutor(max_workers=2) as executor:
        counts = list(executor.map(lambda _: receive(), range(2)))
    assert sum(counts) == 1
    assert g.client.get(f"/chat/conversations/{conv}").json()["unread_count"] == 1
