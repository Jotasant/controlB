"""Exercita o gateway HTTP em PostgreSQL isolado, com transporte externo simulado."""

import asyncio
import base64
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
    ChatMessage,
    ChatTeam,
    ChatWebhookEvent,
)
from controlb.modules.documents.models import BusinessDocument
from controlb.modules.identity.models import (
    Contact,
    ContactOrigin,
    Organization,
    Permission,
    Role,
    Team,
    User,
)
from controlb.modules.identity.security import get_current_user
from controlb.modules.purchasing.models import Supplier


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
        team = Team(organization_id=org.id, name="Atendimento", members=[user])
        db.add(team)
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
            team=team,
            sales_team=team,
            other_org=other_org,
            doc=doc,
            project=project,
            other_doc=other_doc,
            reader=reader,
            calls=[],
            transport_status=200,
            timeout=False,
            instance_state="open",
            provider_name="comercial",
            provider_phone="5571000000000",
            webhook_failure=False,
            contact_name="Cliente",
            media_bytes=b"\x89PNG\r\n\x1a\ntest-image",
            media_mime="image/png",
            send_id="sent-1",
            history_status="READ",
            history_rows=None,
            group_settings={
                "groupsIgnore": True,
                "readMessages": False,
                "alwaysOnline": True,
                "rejectCall": True,
                "msgCall": "Retornaremos",
            },
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
            if state.webhook_failure and "/webhook/" in request.url.path:
                return httpx.Response(500, json={"message": "simulated callback failure"})
            if "findContacts" in request.url.path:
                return httpx.Response(
                    200,
                    json=[{"remoteJid": body["where"]["remoteJid"], "pushName": state.contact_name}]
                    if state.contact_name
                    else [],
                )
            if "/settings/find/" in request.url.path:
                return httpx.Response(200, json=state.group_settings)
            if "fetchAllGroups" in request.url.path:
                return httpx.Response(
                    200, json=[{"id": "120363123456789@g.us", "subject": "Obra Centro"}]
                )
            if "findGroupInfos" in request.url.path:
                return httpx.Response(
                    200,
                    json={"id": request.url.params["groupJid"], "subject": "Nome correto do grupo"},
                )
            if "sendMedia" in request.url.path:
                return httpx.Response(
                    200,
                    json={
                        "key": {"id": state.send_id, "remoteJid": body["number"]},
                        "status": "PENDING",
                    },
                )
            if "sendText" in request.url.path:
                return httpx.Response(
                    200,
                    json={
                        "key": {"id": state.send_id, "remoteJid": "5571999999999@s.whatsapp.net"},
                        "status": "PENDING",
                    },
                )
            if "getBase64FromMediaMessage" in request.url.path:
                return httpx.Response(
                    200,
                    json={
                        "base64": base64.b64encode(
                            state.media_bytes
                            if body["message"]["key"]["id"].startswith("media-")
                            else b"OggS-test-audio"
                        ).decode(),
                        "mimetype": state.media_mime
                        if body["message"]["key"]["id"].startswith("media-")
                        else "audio/ogg; codecs=opus",
                    },
                )
            if "fetchInstances" in request.url.path:
                return httpx.Response(
                    200,
                    json=[
                        {
                            "id": "provider-id",
                            "name": state.provider_name,
                            "connectionStatus": state.instance_state,
                            "ownerJid": f"{state.provider_phone}@s.whatsapp.net"
                            if state.provider_phone
                            else None,
                            "profileName": "Comercial",
                            "integration": "WHATSAPP-BAILEYS",
                            "token": "must-never-leak",
                            "_count": {"Message": 4, "Chat": 1},
                        }
                    ],
                )
            if "findMessages" in request.url.path:
                if state.history_rows is not None:
                    return httpx.Response(
                        200,
                        json={
                            "messages": {
                                "total": len(state.history_rows),
                                "pages": 1,
                                "currentPage": body["page"],
                                "records": state.history_rows,
                            }
                        },
                    )
                rows = [incoming("history-1"), incoming("history-2")]
                rows[0]["key"]["remoteJid"] = "123456789@lid"
                rows[0]["key"]["remoteJidAlt"] = "5571999999999@s.whatsapp.net"
                rows[1]["key"]["fromMe"] = True
                rows[1]["MessageUpdate"] = [{"status": state.history_status}]
                return httpx.Response(
                    200,
                    json={
                        "messages": {
                            "total": 4,
                            "pages": 2,
                            "currentPage": body["page"],
                            "records": rows,
                        }
                    },
                )
            if request.url.path.endswith("/instance/create"):
                return httpx.Response(
                    200,
                    json={
                        "instance": {"instanceName": "comercial", "status": "created"},
                        "qrcode": {
                            "base64": "data:image/png;base64,aaa",
                            "pairingCode": None,
                        },
                    },
                )
            if "/instance/connect/" in request.url.path:
                return httpx.Response(
                    200,
                    json={"base64": "data:image/png;base64,bbb", "pairingCode": "ABCD1234"},
                )
            if "connectionState" in request.url.path:
                return httpx.Response(200, json={"instance": {"state": state.instance_state}})
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
                    "member_ids": [str(user.id)],
                    "name": "Comercial",
                    "base_url": "https://evolution.test",
                    "external_instance_id": "comercial",
                    "api_key": "secret-key-must-not-leak",
                    "webhook_secret": "webhook-secret-must-not-leak",
                },
            )
            assert response.status_code == 201, response.text
            state.connection_id = response.json()["id"]
            stored = db.get(ChatConnection, uuid.UUID(state.connection_id))
            state.team = stored.team
            stored.instance_phone = state.provider_phone
            stored.provider_instance_id = "provider-id"
            db.commit()
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


def group_message(identifier="group-1", participant="5571999999999@s.whatsapp.net", name="Maria"):
    data = incoming(identifier)
    data["key"]["remoteJid"] = "120363123456789@g.us"
    data["key"]["participant"] = participant
    data["pushName"] = name
    return data


def test_group_members_are_distinct_from_group_and_individual_channel(gateway):
    g = gateway
    assert (
        webhook(
            g, {"id": "120363123456789@g.us", "subject": "Obra Centro"}, "groups.upsert"
        ).status_code
        == 200
    )
    assert webhook(g, group_message()).status_code == 200
    assert (
        webhook(g, group_message("group-2", "5571888888888@s.whatsapp.net", "José")).status_code
        == 200
    )
    assert webhook(g, incoming("group-1")).status_code == 200
    conversations = g.client.get("/chat/conversations").json()["items"]
    assert len(conversations) == 2
    group = next(c for c in conversations if c["is_group"])
    assert group["display_name"] == "Obra Centro"
    assert group["contact_id"] is None and group["remote_phone"] == ""
    assert group["unread_count"] == 2
    messages = g.client.get(f"/chat/conversations/{group['id']}/messages").json()["items"]
    assert {m["sender_name"] for m in messages} == {"Maria", "José"}
    assert {m["sender_phone"] for m in messages} == {"5571999999999", "5571888888888"}
    assert {m["sender_external_id"] for m in messages} == {
        "5571999999999@s.whatsapp.net",
        "5571888888888@s.whatsapp.net",
    }
    contacts = list(g.db.scalars(select(Contact).where(Contact.organization_id == g.org.id)))
    assert len(contacts) == 1  # Only the participant who also sent a direct message.
    assert all(c.normalized_phone for c in contacts)
    body = {"client_request_id": str(uuid.uuid4()), "text": "Bom dia, grupo"}
    sent = g.client.post(f"/chat/conversations/{group['id']}/messages", json=body)
    assert sent.status_code == 200, sent.text
    assert sent.json()["author_name"] == "Chat"
    assert g.calls[-1] == (
        "/message/sendText/comercial",
        {"number": group["external_chat_id"], "text": body["text"]},
    )
    g.client.post(f"/chat/conversations/{group['id']}/messages", json=body)
    assert sum("sendText" in path for path, _ in g.calls) == 1


def test_group_lid_participant_is_not_saved_as_phone(gateway):
    g = gateway
    webhook(g, group_message(participant="99887766@lid", name="Perfil"))
    group = g.client.get("/chat/conversations").json()["items"][0]
    message = g.client.get(f"/chat/conversations/{group['id']}/messages").json()["items"][0]
    assert message["sender_external_id"] == "99887766@lid"
    assert message["sender_phone"] is None
    assert not list(g.db.scalars(select(Contact).where(Contact.organization_id == g.org.id)))
    data = group_message("resolved", "99887766@lid", "Perfil")
    data["key"]["participantAlt"] = "5571999999999@s.whatsapp.net"
    webhook(g, data)
    messages = g.client.get(f"/chat/conversations/{group['id']}/messages").json()["items"]
    assert (
        next(m for m in messages if m["external_message_id"] == "resolved")["sender_phone"]
        == "5571999999999"
    )


def test_group_configuration_preserves_settings_and_can_disable_without_deleting(gateway):
    g = gateway
    result = g.client.post(f"/chat/connections/{g.connection_id}/groups")
    assert result.status_code == 200, result.text
    assert result.json() == {"groups_enabled": True, "synced": 1}
    settings = next(body for path, body in g.calls if "/settings/set/" in path)
    assert settings == {**g.group_settings, "groupsIgnore": False}
    webhook_config = next(body for path, body in g.calls if "/webhook/set/" in path)
    assert "GROUPS_UPDATE" in webhook_config["webhook"]["events"]
    group = g.client.get("/chat/conversations").json()["items"][0]
    assert group["display_name"] == "Obra Centro"
    webhook(g, group_message())
    g.client.patch(f"/chat/connections/{g.connection_id}", json={"groups_enabled": False})
    assert webhook(g, group_message("disabled")).json()["skipped"] == 1
    assert (
        g.client.post(
            f"/chat/conversations/{group['id']}/messages",
            json={"client_request_id": str(uuid.uuid4()), "text": "Não enviar"},
        ).status_code
        == 409
    )
    result = g.client.post(f"/chat/connections/{g.connection_id}/groups")
    assert result.json()["groups_enabled"] is False
    assert g.client.get(f"/chat/conversations/{group['id']}/messages").json()["total"] == 1
    g.client.patch(f"/chat/connections/{g.connection_id}", json={"groups_enabled": True})
    assert webhook(g, group_message("disabled")).json()["imported"] == 1
    g.user.role = g.reader
    assert g.client.post(f"/chat/connections/{g.connection_id}/groups").status_code == 403


def test_group_history_is_deduplicated_and_does_not_notify(gateway):
    g = gateway
    g.history_rows = [group_message("historical-group")]
    baseline = g.client.get("/chat/notifications").json()["until"]
    for _ in range(2):
        result = g.client.post(f"/chat/connections/{g.connection_id}/sync", json={})
        assert result.status_code == 200, result.text
    group = g.client.get("/chat/conversations").json()["items"][0]
    assert group["is_group"] and group["unread_count"] == 0
    assert g.client.get(f"/chat/conversations/{group['id']}/messages").json()["total"] == 1
    assert g.client.get("/chat/notifications", params={"since": baseline}).json()["items"] == []
    webhook(g, group_message("historical-group"))
    assert g.client.get("/chat/notifications", params={"since": baseline}).json()["items"] == []
    assert g.calls and all(
        "sendText" not in path and "findContacts" not in path for path, _ in g.calls
    )


def test_assignee_tag_uses_profile_and_releases(gateway):
    g = gateway
    conv = create_conversation(g)
    assigned = g.client.patch(
        f"/chat/conversations/{conv}", json={"assigned_user_id": str(g.user.id)}
    )
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["assigned_user_name"] == "Chat"
    assert g.client.get("/chat/conversations").json()["items"][0]["assigned_user_name"] == "Chat"
    released = g.client.patch(f"/chat/conversations/{conv}", json={"assigned_user_id": None})
    assert released.json()["assigned_user_name"] is None


def test_notifications_bootstrap_replay_archive_and_authorization(gateway):
    g = gateway
    webhook(g, incoming("old"))
    initial = g.client.get("/chat/notifications")
    assert initial.headers["cache-control"] == "no-store"
    assert initial.json()["items"] == [] and initial.json()["unread_count"] == 1
    params = {"since": initial.json()["until"]}
    webhook(g, incoming("new"))
    webhook(g, incoming("new"))
    feed = g.client.get("/chat/notifications", params=params)
    assert feed.status_code == 200, feed.text
    assert len(feed.json()["items"]) == 1 and feed.json()["unread_count"] == 2
    conv = feed.json()["items"][0]["conversation_id"]
    g.client.patch(f"/chat/conversations/{conv}", json={"is_archived": True})
    assert g.client.get("/chat/notifications", params=params).json()["items"] == []
    g.client.patch(f"/chat/conversations/{conv}", json={"is_archived": False})
    g.team.members = []
    g.db.commit()
    hidden = g.client.get("/chat/notifications", params=params).json()
    assert hidden["items"] == [] and hidden["unread_count"] == 0


def test_notification_feed_pages_all_live_messages_without_history_alerts(gateway):
    g = gateway
    initial = g.client.get("/chat/notifications").json()
    assert webhook(g, [incoming(f"batch-{i}") for i in range(100)]).status_code == 200
    webhook(g, incoming("last"))
    g.client.post(f"/chat/connections/{g.connection_id}/sync", json={})
    first = g.client.get("/chat/notifications", params={"since": initial["until"]}).json()
    assert len(first["items"]) == 100 and first["next_page"] == 2
    second = g.client.get(
        "/chat/notifications",
        params={"since": initial["until"], "until": first["until"], "page": 2},
    ).json()
    assert len(second["items"]) == 1 and second["next_page"] is None
    assert len({m["id"] for m in first["items"] + second["items"]}) == 101
    assert first["unread_count"] == 101


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


def test_instance_details_are_allowlisted_and_scoped(gateway):
    g = gateway
    result = g.client.get(f"/chat/connections/{g.connection_id}/details")
    assert result.status_code == 200, result.text
    assert result.json()["phone"] == g.provider_phone
    assert result.json()["instance_id"] == "provider-id"
    assert result.json()["local_message_count"] == 0
    assert "must-never-leak" not in result.text
    assert result.headers["cache-control"] == "no-store"
    g.user = SimpleNamespace(id=g.user.id, organization_id=g.other_org.id, role=g.user.role)
    assert g.client.get(f"/chat/connections/{g.connection_id}/details").status_code == 404


def test_history_sync_deduplicates_without_inflating_unread(gateway):
    g = gateway
    url = f"/chat/connections/{g.connection_id}/sync"
    result = g.client.post(url, json={"page_size": 2})
    assert result.status_code == 200, result.text
    data = result.json()
    assert data["imported"] == 2
    assert data["next_page"] == 2
    assert (
        "messageTimestamp"
        in next(body for path, body in g.calls if "findMessages" in path)["where"]
    )
    snapshot = data["snapshot_at"]
    repeated = g.client.post(url, json={"page_size": 2, "snapshot_at": snapshot})
    assert repeated.json()["imported"] == 0
    assert repeated.json()["existing"] == 2
    conv = g.client.get("/chat/conversations?unlinked=true").json()["items"][0]
    assert conv["unread_count"] == 0
    assert conv["remote_phone"] == "5571999999999"
    assert g.client.get(f"/chat/conversations/{conv['id']}/messages").json()["total"] == 2
    messages = g.client.get(f"/chat/conversations/{conv['id']}/messages").json()["items"]
    outbound = next(message for message in messages if message["direction"] == "OUTBOUND")
    assert outbound["status"] == "READ"
    webhook(g, incoming("history-1"))
    assert g.client.get(f"/chat/conversations/{conv['id']}").json()["unread_count"] == 0
    webhook(g, incoming("new-live"))
    assert g.client.get(f"/chat/conversations/{conv['id']}").json()["unread_count"] == 1
    g.user = SimpleNamespace(id=g.user.id, organization_id=g.org.id, role=g.reader)
    assert g.client.get("/chat/conversations").json()["total"] == 1
    assert g.client.post(url, json={}).status_code == 403


def test_history_failure_leaves_no_partial_import(gateway):
    g = gateway
    g.transport_status = 500
    result = g.client.post(f"/chat/connections/{g.connection_id}/sync", json={})
    assert result.status_code == 502
    assert g.client.get("/chat/conversations").json()["total"] == 0


def test_instance_provision_and_pairing_stay_in_connector_contract(gateway):
    g = gateway
    created = g.client.post(f"/chat/connections/{g.connection_id}/instance")
    assert created.status_code == 200, created.text
    assert created.headers["cache-control"] == "no-store"
    body = created.json()
    assert body["created"] is True
    assert body["qr_code_base64"] == "data:image/png;base64,aaa"
    assert body["connection"]["status"] == "CONNECTING"
    assert "/instance/create" in g.calls[-1][0]
    g.instance_state = "connecting"
    pairing = g.client.post(f"/chat/connections/{g.connection_id}/pairing")
    assert pairing.status_code == 200, pairing.text
    assert pairing.headers["cache-control"] == "no-store"
    payload = pairing.json()
    assert payload["qr_code_base64"] == "data:image/png;base64,bbb"
    assert payload["pairing_code"] == "ABCD1234"
    assert payload["state"] == "CONNECTING"
    g.instance_state = "open"
    connected = g.client.post(f"/chat/connections/{g.connection_id}/pairing")
    assert connected.json()["state"] == "CONNECTED"
    assert connected.json()["qr_code_base64"] is None
    assert g.calls[-1][0].endswith("/connectionState/comercial")
    g.user = SimpleNamespace(id=g.user.id, organization_id=g.org.id, role=g.reader)
    assert g.client.post(f"/chat/connections/{g.connection_id}/instance").status_code == 403
    assert g.client.post(f"/chat/connections/{g.connection_id}/pairing").status_code == 403


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


def test_system_sender_is_internal_and_send_does_not_wait_for_contact_lookup(gateway, monkeypatch):
    g = gateway

    async def forbidden_lookup(*args):
        pytest.fail("O envio e o recebimento não devem aguardar consulta de nome remoto")

    monkeypatch.setattr(service, "_lookup_contact_name", forbidden_lookup)
    g.contact_name = None
    assert webhook(g, incoming()).status_code == 200
    conv = g.client.get("/chat/conversations").json()["items"][0]
    assert conv["display_name"] == "Cliente"
    body = {"client_request_id": str(uuid.uuid4()), "text": "Mensagem sem assinatura"}
    result = g.client.post(f"/chat/conversations/{conv['id']}/messages", json=body)
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "SENT"
    assert result.json()["created_by_id"] == str(g.user.id)
    assert result.json()["author_name"] == "Chat"
    assert g.calls == [
        ("/message/sendText/comercial", {"number": "5571999999999", "text": body["text"]})
    ]
    echo = incoming("sent-1")
    echo["key"]["fromMe"] = True
    echo["pushName"] = "Nome do dono da instância"
    assert webhook(g, echo).status_code == 200
    messages = g.client.get(f"/chat/conversations/{conv['id']}/messages").json()["items"]
    sent = next(m for m in messages if m["external_message_id"] == "sent-1")
    assert sent["author_name"] == "Chat"
    assert sent["content"] == body["text"]
    assert g.client.get(f"/chat/conversations/{conv['id']}").json()["display_name"] == "Cliente"


def test_different_attendants_and_phone_sends_have_distinct_attribution(gateway):
    g = gateway
    conv = create_conversation(g)
    first_id = g.user.id
    response = g.client.post(
        f"/chat/conversations/{conv}/messages",
        json={"client_request_id": str(uuid.uuid4()), "text": "Primeiro"},
    )
    assert response.json()["author_name"] == "Chat"
    second = User(
        organization_id=g.org.id,
        role=g.user.role,
        full_name="Outra atendente",
        email=f"{uuid.uuid4()}@test.example",
        hashed_password="hash",
    )
    g.db.add(second)
    g.team.members.append(second)
    g.db.commit()
    g.user = second
    g.send_id = "sent-2"
    response = g.client.post(
        f"/chat/conversations/{conv}/messages",
        json={"client_request_id": str(uuid.uuid4()), "text": "Segundo"},
    )
    assert response.json()["author_name"] == "Outra atendente"
    assert response.json()["created_by_id"] == str(second.id)
    direct = incoming("phone-send")
    direct["key"]["fromMe"] = True
    webhook(g, direct)
    messages = g.client.get(f"/chat/conversations/{conv}/messages").json()["items"]
    assert len(messages) == 3
    first = next(m for m in messages if m["external_message_id"] == "sent-1")
    phone = next(m for m in messages if m["external_message_id"] == "phone-send")
    assert first["created_by_id"] == str(first_id)
    assert first["author_name"] == "Chat"
    assert phone["created_by_id"] is None and phone["author_name"] is None


def test_history_replays_update_receipts_without_resending_or_losing_author(gateway):
    g = gateway
    conv = create_conversation(g)
    g.send_id = "history-2"
    sent = g.client.post(
        f"/chat/conversations/{conv}/messages",
        json={"client_request_id": str(uuid.uuid4()), "text": "Mensagem do sistema"},
    ).json()
    g.calls.clear()
    url = f"/chat/connections/{g.connection_id}/sync"
    for receipt, expected in [("DELIVERY_ACK", "DELIVERED"), ("READ", "READ"), ("PENDING", "READ")]:
        g.history_status = receipt
        result = g.client.post(url, json={"page_size": 2})
        assert result.status_code == 200, result.text
        messages = g.client.get(f"/chat/conversations/{conv}/messages").json()["items"]
        assert len(messages) == 2
        outbound = next(m for m in messages if m["id"] == sent["id"])
        assert outbound["status"] == expected
        assert outbound["author_name"] == "Chat"
        assert outbound["content"] == "Mensagem do sistema"
    assert not any("sendText" in path for path, _ in g.calls)
    assert g.client.get(f"/chat/conversations/{conv}").json()["unread_count"] == 0


def test_nested_receipts_and_repeated_echo_advance_status(gateway):
    g = gateway
    conv = create_conversation(g)
    g.client.post(
        f"/chat/conversations/{conv}/messages",
        json={"client_request_id": str(uuid.uuid4()), "text": "Mensagem"},
    )
    echo = incoming("sent-1")
    echo["key"]["fromMe"] = True
    echo["status"] = "DELIVERY_ACK"
    webhook(g, echo)
    echo["status"] = "READ"
    assert webhook(g, echo).json()["events"] == 0
    nested = {"key": echo["key"], "update": {"status": 3}}
    assert webhook(g, nested, "messages.update").status_code == 200
    message = g.client.get(f"/chat/conversations/{conv}/messages").json()["items"][0]
    assert message["status"] == "READ"
    assert message["read_at"] is not None
    assert message["author_name"] == "Chat"


def test_local_repair_is_idempotent_and_never_confirms_ambiguous_sends(gateway):
    g = gateway
    conv = create_conversation(g)
    saved = []
    for external_id in ("accepted", "uncertain", "no-provider-id"):
        g.send_id = external_id
        result = g.client.post(
            f"/chat/conversations/{conv}/messages",
            json={"client_request_id": str(uuid.uuid4()), "text": external_id},
        )
        message = g.db.get(ChatMessage, uuid.UUID(result.json()["id"]))
        message.status = "PENDING"
        if external_id == "uncertain":
            message.error_message = "Envio sem confirmação"
        if external_id == "no-provider-id":
            message.external_message_id = None
        saved.append(message)
        g.db.commit()
    g.calls.clear()
    conn = g.db.get(ChatConnection, uuid.UUID(g.connection_id))
    assert service.reconcile_local_metadata(g.db, conn)["accepted_messages"] == 1
    assert [message.status for message in saved] == ["SENT", "PENDING", "PENDING"]
    assert service.reconcile_local_metadata(g.db, conn)["accepted_messages"] == 0
    assert g.calls == []


def test_contact_updates_preserve_manual_name_and_refresh_is_scoped(gateway):
    g = gateway
    webhook(g, incoming())
    conv = g.client.get("/chat/conversations").json()["items"][0]
    name_event = {"remoteJid": "5571999999999@s.whatsapp.net", "pushName": "Nome atualizado"}
    assert webhook(g, name_event, "contacts.update").status_code == 200
    assert (
        g.client.get(f"/chat/conversations/{conv['id']}").json()["display_name"]
        == "Nome atualizado"
    )
    contact = g.db.get(Contact, uuid.UUID(conv["contact_id"]))
    contact.name = "Nome escolhido manualmente"
    g.db.commit()
    g.contact_name = "Nome da agenda"
    result = g.client.post(f"/chat/conversations/{conv['id']}/refresh-contact")
    assert result.status_code == 200, result.text
    assert result.json()["display_name"] == "Nome escolhido manualmente"
    g.user = SimpleNamespace(id=g.user.id, organization_id=g.other_org.id, role=g.user.role)
    assert g.client.post(f"/chat/conversations/{conv['id']}/refresh-contact").status_code == 404


def test_send_request_replay_does_not_send_twice(gateway):
    g = gateway
    conv = create_conversation(g)
    body = {"client_request_id": str(uuid.uuid4()), "text": "Olá cliente"}
    result = g.client.post(f"/chat/conversations/{conv}/messages", json=body)
    assert result.status_code == 200, result.text
    repeated = g.client.post(f"/chat/conversations/{conv}/messages", json=body)
    assert repeated.json()["id"] == result.json()["id"]
    assert [call for call in g.calls if "/message/sendText/" in call[0]] == [
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
    assert sum("/message/sendText/" in path for path, _ in g.calls) == 1


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
        == 200
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
    assert sum("/message/sendText/" in path for path, _ in g.calls) == 1
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


def test_replacement_same_phone_preserves_chats_team_and_checkpoint(gateway):
    g = gateway
    conv = create_conversation(g)
    assert webhook(g, incoming()).status_code == 200
    before = g.client.get(f"/chat/conversations/{conv}/messages").json()["items"]
    checkpoint = g.client.get(f"/chat/connections/{g.connection_id}").json()["sync_checkpoint_at"]
    g.provider_name = "comercial-nova-sessao"
    result = g.client.patch(
        f"/chat/connections/{g.connection_id}", json={"external_instance_id": g.provider_name}
    )
    assert result.status_code == 200, result.text
    assert result.json()["id"] == g.connection_id
    assert result.json()["team_id"] == str(g.team.id)
    assert result.json()["instance_phone"] == g.provider_phone
    assert result.json()["sync_checkpoint_at"] == checkpoint
    assert result.json()["recovery_pending"] is True
    assert result.json()["status"] == "CONNECTED"
    assert g.client.get(f"/chat/conversations/{conv}/messages").json()["items"] == before
    assert webhook(g, incoming("old-session")).status_code == 401
    token = g.calls[-1][1]["webhook"]["headers"]["X-ControlB-Webhook-Token"]
    received = g.client.post(
        f"/chat/webhooks/{g.connection_id}",
        headers={"X-ControlB-Webhook-Token": token},
        json={
            "event": "messages.upsert",
            "instance": g.provider_name,
            "data": incoming("new-session"),
        },
    )
    assert received.status_code == 200, received.text
    assert g.client.get("/chat/conversations").json()["total"] == 1
    assert g.client.get(f"/chat/conversations/{conv}/messages").json()["total"] == 2


@pytest.mark.parametrize(
    "phone,state", [("5571222222222", "open"), (None, "open"), ("5571000000000", "connecting")]
)
def test_invalid_replacement_rolls_back_configuration_and_history(gateway, phone, state):
    g = gateway
    conv = create_conversation(g)
    before = g.db.get(ChatConnection, uuid.UUID(g.connection_id)).credentials_ciphertext
    g.provider_name, g.provider_phone, g.instance_state = "nova-sessao", phone, state
    result = g.client.patch(
        f"/chat/connections/{g.connection_id}",
        json={"external_instance_id": g.provider_name, "api_key": "a-new-secret-key-for-session"},
    )
    assert result.status_code == 409, result.text
    stored = g.db.get(ChatConnection, uuid.UUID(g.connection_id))
    assert stored.external_instance_id == "comercial"
    assert stored.credentials_ciphertext == before
    assert stored.instance_phone == "5571000000000"
    assert g.client.get(f"/chat/conversations/{conv}").status_code == 200
    assert not any("/webhook/" in path for path, _ in g.calls)


def test_replacement_provider_failure_preserves_previous_configuration(gateway):
    g = gateway
    create_conversation(g)
    g.transport_status = 500
    result = g.client.patch(
        f"/chat/connections/{g.connection_id}", json={"external_instance_id": "unavailable"}
    )
    assert result.status_code == 502
    assert (
        g.client.get(f"/chat/connections/{g.connection_id}").json()["external_instance_id"]
        == "comercial"
    )


def test_replacement_cannot_transfer_history_to_another_team(gateway):
    g = gateway
    create_conversation(g)
    other = Team(organization_id=g.org.id, name="Outra equipe", members=[g.user])
    g.db.add(other)
    g.db.commit()
    result = g.client.patch(f"/chat/connections/{g.connection_id}", json={"team_id": str(other.id)})
    assert result.status_code == 422
    assert not g.calls


def test_same_phone_cannot_create_a_second_logical_connection(gateway):
    g = gateway
    result = g.client.post(
        "/chat/connections",
        json={
            "name": "Outra sessão",
            "member_ids": [str(g.user.id)],
            "base_url": "https://evolution.test",
            "external_instance_id": "outra",
            "api_key": "secret-for-other-session",
        },
    )
    assert result.status_code == 201, result.text
    g.provider_name = "outra"
    result = g.client.post(f"/chat/connections/{result.json()['id']}/check")
    assert result.status_code == 409, result.text


@pytest.mark.parametrize("administrator", [False, True])
def test_team_membership_revocation_blocks_list_detail_send_and_replacement(gateway, administrator):
    g = gateway
    conv = create_conversation(g)
    if administrator:
        g.user.role.name = "Administrador"
    g.team.members = []
    g.db.commit()
    assert g.client.get("/chat/channels").json() == []
    assert g.client.get("/chat/conversations").json()["total"] == 0
    assert g.client.get(f"/chat/conversations/{conv}/messages").status_code == 404
    assert (
        g.client.post(
            f"/chat/conversations/{conv}/messages",
            json={"client_request_id": str(uuid.uuid4()), "text": "Oi"},
        ).status_code
        == 404
    )
    assert (
        g.client.patch(
            f"/chat/connections/{g.connection_id}", json={"external_instance_id": "outra"}
        ).status_code
        == 404
    )
    assert not g.calls


def test_replacement_webhook_failure_rolls_back_after_identity_validation(gateway):
    g = gateway
    conv = create_conversation(g)
    before = g.db.get(ChatConnection, uuid.UUID(g.connection_id)).credentials_ciphertext
    g.provider_name, g.webhook_failure = "nova", True
    result = g.client.patch(
        f"/chat/connections/{g.connection_id}", json={"external_instance_id": "nova"}
    )
    assert result.status_code == 502, result.text
    stored = g.db.get(ChatConnection, uuid.UUID(g.connection_id))
    assert stored.external_instance_id == "comercial"
    assert stored.credentials_ciphertext == before
    assert g.client.get(f"/chat/conversations/{conv}").status_code == 200


@pytest.mark.parametrize("is_group", [False, True])
def test_same_contact_two_instance_numbers_have_separate_channels(gateway, is_group):
    g = gateway
    payload = group_message() if is_group else incoming()
    payload["message"] = {"audioMessage": {"mimetype": "audio/ogg"}}
    assert webhook(g, payload).status_code == 200
    first = g.client.get("/chat/conversations").json()["items"][0]
    result = g.client.post(
        "/chat/connections",
        json={
            "name": "Outro número",
            "member_ids": [str(g.user.id)],
            "base_url": "https://evolution.test",
            "external_instance_id": "outra",
            "api_key": "secret-for-other-session",
            "webhook_secret": "another-webhook-secret",
        },
    )
    assert result.status_code == 201, result.text
    connection_id = result.json()["id"]
    g.provider_name, g.provider_phone = "outra", "5571333333333"
    assert g.client.post(f"/chat/connections/{connection_id}/check").status_code == 200
    result = g.client.post(
        f"/chat/webhooks/{connection_id}",
        headers={"X-ControlB-Webhook-Token": "another-webhook-secret"},
        json={"event": "messages.upsert", "instance": "outra", "data": payload},
    )
    assert result.status_code == 200, result.text
    rows = g.client.get("/chat/conversations").json()
    assert rows["total"] == 2
    second = next(row for row in rows["items"] if row["connection_id"] == connection_id)
    assert first["contact_id"] == second["contact_id"]
    assert first["id"] != second["id"]
    assert first["instance_phone"] != second["instance_phone"]
    first_url = f"/chat/conversations/{first['id']}"
    assert g.client.post(first_url + "/read").status_code == 200
    assert (
        g.client.patch(first_url, json={"status": "CLOSED", "is_archived": True}).status_code == 200
    )
    untouched = g.client.get(f"/chat/conversations/{second['id']}").json()
    assert untouched["status"] == "OPEN"
    assert untouched["is_archived"] is False
    assert untouched["unread_count"] == 1
    for row in rows["items"]:
        messages = g.client.get(f"/chat/conversations/{row['id']}/messages").json()
        assert messages["total"] == 1
        assert messages["items"][0]["team_id"] == row["team_id"]
        assert messages["items"][0]["instance_phone"] == row["instance_phone"]
        message_id = messages["items"][0]["id"]
        assert g.client.get(f"/chat/messages/{message_id}/audio").status_code == 200
        expected_instance = "outra" if row["connection_id"] == connection_id else "comercial"
        assert g.calls[-1][0] == f"/chat/getBase64FromMediaMessage/{expected_instance}"


def receive_audio(g):
    payload = incoming("audio-1")
    payload["message"] = {"audioMessage": {"mimetype": "audio/ogg; codecs=opus", "ptt": True}}
    assert webhook(g, payload).status_code == 200
    conversation_id = g.client.get("/chat/conversations").json()["items"][0]["id"]
    return g.client.get(f"/chat/conversations/{conversation_id}/messages").json()["items"][0]


def test_audio_download_and_transcription_permissions(gateway):
    g = gateway
    message = receive_audio(g)
    url = f"/chat/messages/{message['id']}"
    response = g.client.get(url + "/audio")
    assert response.status_code == 200
    assert response.content == b"OggS-test-audio"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["content-type"] == "audio/ogg"
    assert g.calls[-1][0] == "/chat/getBase64FromMediaMessage/comercial"
    assert g.client.post(url + "/transcribe").status_code == 409
    assert g.client.get(url + "/transcription").json()["transcription_status"] == "NOT_REQUESTED"
    g.user.role = g.reader
    g.db.commit()
    assert g.client.get(url + "/audio").status_code == 200
    assert g.client.post(url + "/transcribe").status_code == 403
    g.team.members = []
    g.db.commit()
    calls = len(g.calls)
    assert g.client.get(url + "/audio").status_code == 404
    assert g.client.get(url + "/transcription").status_code == 404
    assert len(g.calls) == calls


def test_audio_provider_error_is_sanitized_and_text_is_not_downloaded(gateway):
    g = gateway
    assert webhook(g, incoming()).status_code == 200
    conversation_id = g.client.get("/chat/conversations").json()["items"][0]["id"]
    message = g.client.get(f"/chat/conversations/{conversation_id}/messages").json()["items"][0]
    assert g.client.get(f"/chat/messages/{message['id']}/audio").status_code == 422
    audio = receive_audio(g)
    # Mensagens com mesmo timestamp são ordenadas por UUID; selecione o áudio explicitamente.
    messages = g.client.get(f"/chat/conversations/{conversation_id}/messages").json()["items"]
    audio = next(item for item in messages if item["message_type"] == "AUDIO")
    g.transport_status = 500
    response = g.client.get(f"/chat/messages/{audio['id']}/audio")
    assert response.status_code == 502
    assert "secret-key" not in response.text


def test_audio_transcription_reports_missing_runtime(gateway, monkeypatch):
    from controlb.modules.chat import audio

    g = gateway
    monkeypatch.setattr(audio, "transcription_ready", lambda: False)
    assert (
        g.client.patch(
            f"/chat/connections/{g.connection_id}", json={"transcription_enabled": True}
        ).status_code
        == 200
    )
    message = receive_audio(g)
    assert message["transcription_status"] == "NOT_CONFIGURED"
    assert g.client.get("/chat/audio/runtime").json()["configured"] is False
    assert g.client.post(f"/chat/messages/{message['id']}/transcribe").status_code == 503


@pytest.mark.parametrize("failure", [False, True])
def test_audio_worker_processes_once_and_supports_explicit_retry(gateway, monkeypatch, failure):
    from controlb.modules.chat import audio
    from controlb.modules.chat.models import ChatMessage

    g = gateway
    monkeypatch.setattr(audio, "transcription_ready", lambda: True)
    monkeypatch.setattr(get_settings(), "chat_audio_worker_enabled", True)
    calls = []

    def transcribe(content):
        calls.append(content)
        if failure:
            raise ValueError("simulated invalid audio")
        return "Texto do áudio recebido"

    monkeypatch.setattr(audio, "transcribe", transcribe)
    assert (
        g.client.patch(
            f"/chat/connections/{g.connection_id}", json={"transcription_enabled": True}
        ).status_code
        == 200
    )
    message = receive_audio(g)
    assert message["transcription_status"] == "PENDING"
    message_id = uuid.UUID(message["id"])
    assert audio._try_lock(g.db, message_id)
    assert audio.process_one(message_id) is False
    g.db.rollback()
    assert audio.process_one(message_id) is True
    assert audio.process_one(message_id) is False
    g.db.expire_all()
    stored = g.db.get(ChatMessage, message_id)
    assert stored.transcription_status == ("FAILED" if failure else "DONE")
    assert stored.transcription == (None if failure else "Texto do áudio recebido")
    assert calls == [b"OggS-test-audio"]
    response = g.client.post(f"/chat/messages/{message_id}/transcribe")
    assert response.status_code == 202
    assert response.json()["transcription_status"] == ("PENDING" if failure else "DONE")
    monkeypatch.setattr(audio, "transcribe", lambda _: "Texto recuperado")
    assert audio.process_one(message_id) is failure
    g.db.expire_all()
    assert g.db.get(ChatMessage, message_id).transcription_status == "DONE"


def test_audio_worker_does_not_download_after_instance_is_disabled(gateway, monkeypatch):
    from controlb.modules.chat import audio
    from controlb.modules.chat.models import ChatMessage

    g = gateway
    monkeypatch.setattr(audio, "transcription_ready", lambda: True)
    monkeypatch.setattr(get_settings(), "chat_audio_worker_enabled", True)
    assert (
        g.client.patch(
            f"/chat/connections/{g.connection_id}", json={"transcription_enabled": True}
        ).status_code
        == 200
    )
    message = receive_audio(g)
    assert (
        g.client.patch(
            f"/chat/connections/{g.connection_id}", json={"transcription_enabled": False}
        ).status_code
        == 200
    )
    calls = len(g.calls)
    assert audio.process_one(uuid.UUID(message["id"]))
    g.db.expire_all()
    assert g.db.get(ChatMessage, uuid.UUID(message["id"])).transcription_status == "NOT_REQUESTED"
    assert len(g.calls) == calls


def test_incoming_contact_upsert_reuses_formatted_phone_and_preserves_manual_name(gateway):
    g = gateway
    contact = Contact(
        organization_id=g.org.id,
        person_type="PF",
        name="Nome do cadastro",
        phone="+55 (71) 99999-9999",
    )
    g.db.add(contact)
    g.db.commit()
    assert webhook(g, incoming()).status_code == 200
    conv = g.client.get("/chat/conversations").json()["items"][0]
    assert conv["contact_id"] == str(contact.id)
    assert conv["display_name"] == "Nome do cadastro"
    outgoing = incoming("outbound-name")
    outgoing["key"]["fromMe"] = True
    outgoing["pushName"] = "Nome do atendente"
    assert webhook(g, outgoing).status_code == 200
    g.db.refresh(contact)
    assert contact.name == "Nome do cadastro"
    assert contact.full_name == "Cliente"
    assert contact.normalized_phone == "5571999999999"
    assert contact.first_contact_at == contact.last_contact_at
    assert len(list(g.db.scalars(select(Contact).where(Contact.organization_id == g.org.id)))) == 1


def test_older_inbound_can_fill_missing_contact_name_without_using_outbound_name(gateway):
    g = gateway
    outgoing = incoming("outbound-first")
    outgoing["key"]["fromMe"] = True
    outgoing["pushName"] = "Nome do atendente"
    outgoing["messageTimestamp"] += 100
    assert webhook(g, outgoing).status_code == 200
    assert webhook(g, incoming()).status_code == 200
    conv = g.client.get("/chat/conversations").json()["items"][0]
    assert conv["display_name"] == "Cliente"
    assert conv["team_id"] == str(g.team.id)
    assert conv["instance_phone"] == g.provider_phone


def test_attendance_close_archive_and_reopen_are_independent_and_keep_history(gateway):
    g = gateway
    assert webhook(g, incoming()).status_code == 200
    conv = g.client.get("/chat/conversations").json()["items"][0]
    url = f"/chat/conversations/{conv['id']}"
    closed = g.client.patch(url, json={"status": "CLOSED", "assigned_user_id": str(g.user.id)})
    assert closed.status_code == 200, closed.text
    assert closed.json()["closed_by_id"] == str(g.user.id)
    assert closed.json()["closed_at"]
    assert (
        g.client.patch(url, json={"status": "CLOSED"}).json()["closed_at"]
        == closed.json()["closed_at"]
    )
    assert (
        g.client.post(
            url + "/messages", json={"client_request_id": str(uuid.uuid4()), "text": "Bloqueada"}
        ).status_code
        == 409
    )
    assert g.client.patch(url, json={"is_archived": True}).json()["status"] == "CLOSED"
    assert g.client.get("/chat/conversations").json()["total"] == 0
    assert g.client.get("/chat/conversations?archived=true").json()["total"] == 1
    assert g.client.get(url + "/messages").json()["total"] == 1
    reopened = g.client.patch(url, json={"status": "OPEN"}).json()
    assert reopened["is_archived"] is True
    assert reopened["closed_at"] is None and reopened["closed_by_id"] is None
    assert (
        g.client.post(
            url + "/messages", json={"client_request_id": str(uuid.uuid4()), "text": "Bloqueada"}
        ).status_code
        == 409
    )
    assert (
        g.client.patch(url, json={"is_archived": False, "assigned_user_id": None}).status_code
        == 200
    )
    assert g.client.get("/chat/conversations?status=OPEN").json()["total"] == 1
    assert (
        g.client.post(
            url + "/messages",
            json={"client_request_id": str(uuid.uuid4()), "text": "Sem documento obrigatório"},
        ).status_code
        == 200
    )


def test_contact_origin_inline_deduplicates_and_preserves_separate_business_entities(gateway):
    g = gateway
    assert webhook(g, incoming()).status_code == 200
    conv = g.client.get("/chat/conversations").json()["items"][0]
    url = f"/chat/conversations/{conv['id']}"
    assert g.client.get(url + "/contact").json()["origin_name"] is None
    result = g.client.patch(url + "/contact-origin", json={"name": " Indicação "})
    assert result.status_code == 200, result.text
    origin_id = result.json()["origin_id"]
    assert result.json()["origin_name"] == "Indicação"
    assert (
        g.client.patch(url + "/contact-origin", json={"name": "INDICAÇÃO"}).json()["origin_id"]
        == origin_id
    )
    origins = g.client.get("/identity/contact-origins").json()
    assert len(origins) >= 1
    assert any(o["id"] == origin_id and o["name"].lower() == "indicação" for o in origins)
    response = g.client.get(
        "/identity/contact-directory",
        params={"team_id": str(g.team.id), "connection_id": g.connection_id},
    )
    assert response.status_code == 200, response.text
    directory = response.json()
    assert directory["total"] == 1
    assert directory["items"][0]["contact_origin_id"] == origin_id
    assert directory["items"][0]["customers"] == []
    assert directory["items"][0]["suppliers"] == []
    assert (
        g.client.patch(url + "/contact-origin", json={"origin_id": None}).json()["origin_id"]
        is None
    )
    assert (
        g.client.patch(url + "/contact-origin", json={"origin_id": origin_id}).json()["origin_name"]
        == "Indicação"
    )


def test_contact_origin_and_attendance_permissions_cannot_be_bypassed(gateway):
    g = gateway
    assert webhook(g, incoming()).status_code == 200
    conv = g.client.get("/chat/conversations").json()["items"][0]
    url = f"/chat/conversations/{conv['id']}"
    foreign_origin = ContactOrigin(organization_id=g.other_org.id, name="privada")
    g.db.add(foreign_origin)
    g.db.commit()
    assert (
        g.client.patch(
            url + "/contact-origin", json={"origin_id": str(foreign_origin.id)}
        ).status_code
        == 422
    )
    assert g.client.patch(url + "/contact-origin", json={}).status_code == 422
    g.user = SimpleNamespace(id=g.user.id, organization_id=g.org.id, role=g.reader)
    assert g.client.patch(url, json={"status": "CLOSED"}).status_code == 403
    assert g.client.patch(url + "/contact-origin", json={"name": "teste"}).status_code == 403
    g.team.members = []
    g.db.commit()
    assert g.client.get(url + "/contact").status_code == 404


def test_supplier_link_is_optional_scoped_and_does_not_promote_contact_implicitly(gateway):
    g = gateway
    assert webhook(g, incoming()).status_code == 200
    contact_id = g.client.get("/chat/conversations").json()["items"][0]["contact_id"]
    supplier = Supplier(
        organization_id=g.org.id, name="Fornecedor separado", cnpj_cpf="12345678900"
    )
    foreign = Supplier(
        organization_id=g.other_org.id, name="Outra organização", cnpj_cpf="12345678900"
    )
    g.db.add_all([supplier, foreign])
    g.db.commit()
    assert supplier.contact_id is None
    url = f"/identity/contact-directory/{contact_id}/links"
    assert g.client.post(url, json={"supplier_id": str(supplier.id)}).status_code == 403
    g.user.role.name = "Administrador"
    g.db.commit()
    assert g.client.post(url, json={"supplier_id": str(foreign.id)}).status_code == 404
    assert g.client.post(url, json={"supplier_id": str(supplier.id)}).status_code == 200
    g.db.refresh(supplier)
    assert str(supplier.contact_id) == contact_id
    directory = g.client.get("/identity/contact-directory").json()
    assert directory["items"][0]["suppliers"] == [{"id": str(supplier.id), "name": supplier.name}]
    contact = g.db.get(Contact, uuid.UUID(contact_id))
    assert not contact.is_supplier


def test_inactive_contact_does_not_prevent_closing_attendance(gateway):
    g = gateway
    assert webhook(g, incoming()).status_code == 200
    conv = g.client.get("/chat/conversations").json()["items"][0]
    contact = g.db.get(Contact, uuid.UUID(conv["contact_id"]))
    contact.is_active = False
    g.db.commit()
    result = g.client.patch(
        f"/chat/conversations/{conv['id']}", json={"status": "CLOSED", "is_archived": True}
    )
    assert result.status_code == 200, result.text


def test_instance_members_are_independent_of_sales_team_and_can_change_with_history(gateway):
    g = gateway
    conv = create_conversation(g)
    teammate = User(
        organization_id=g.org.id,
        role_id=g.user.role_id,
        email=f"{uuid.uuid4()}@test.example",
        full_name="Participante",
        hashed_password="hash",
    )
    g.db.add(teammate)
    g.sales_team.members.append(teammate)
    g.db.commit()
    owner = g.user
    g.user = teammate
    assert g.client.get("/chat/channels").json() == []
    assert g.client.get(f"/chat/conversations/{conv}").status_code == 404
    g.user = owner
    result = g.client.patch(
        f"/chat/connections/{g.connection_id}",
        json={"member_ids": [str(owner.id), str(teammate.id)]},
    )
    assert result.status_code == 200, result.text
    assert result.json()["team_id"] == str(g.team.id)
    assert isinstance(g.team, ChatTeam)
    assert g.team.id != g.sales_team.id
    g.user = teammate
    assert g.client.get(f"/chat/conversations/{conv}").status_code == 200
    g.sales_team.members = []
    g.db.commit()
    assert g.client.get(f"/chat/conversations/{conv}").status_code == 200
    g.user = owner
    assert (
        g.client.patch(
            f"/chat/connections/{g.connection_id}", json={"member_ids": [str(owner.id)]}
        ).status_code
        == 200
    )
    g.user = teammate
    assert g.client.get(f"/chat/conversations/{conv}").status_code == 404
    assert g.client.get("/chat/conversations").json()["total"] == 0


def test_instance_participants_must_be_active_same_org_and_include_manager(gateway):
    g = gateway
    outsider = User(
        organization_id=g.other_org.id,
        email=f"{uuid.uuid4()}@test.example",
        full_name="Outra organização",
        hashed_password="hash",
    )
    inactive = User(
        organization_id=g.org.id,
        email=f"{uuid.uuid4()}@test.example",
        full_name="Inativo",
        hashed_password="hash",
        is_active=False,
    )
    g.db.add_all([outsider, inactive])
    g.db.commit()
    url = f"/chat/connections/{g.connection_id}"
    for ids in (
        [],
        [str(uuid.uuid4())],
        [str(g.user.id), str(outsider.id)],
        [str(g.user.id), str(inactive.id)],
    ):
        assert g.client.patch(url, json={"member_ids": ids}).status_code == 422
    available = g.client.get("/chat/eligible-users").json()
    assert {item["id"] for item in available} == {str(g.user.id)}
    assert "email" not in available[0]
    assert not g.calls


def test_start_from_identity_contact_without_document_and_send(gateway):
    g = gateway
    created = g.client.post(
        "/identity/contacts",
        json={"name": "Contato manual", "person_type": "PF", "phone": "+55 (71) 99999-9999"},
    )
    assert created.status_code == 201, created.text
    contact_id = created.json()["id"]
    # Atendimento não precisa de permissão para associar documentos.
    g.user.role.permissions = [
        permission for permission in g.user.role.permissions if permission.code != "chat:link"
    ]
    g.db.commit()
    payload = {"connection_id": g.connection_id, "contact_id": contact_id}
    started = g.client.post("/chat/conversations/start", json=payload)
    assert started.status_code == 201, started.text
    conv = started.json()
    assert conv["contact_id"] == contact_id
    assert conv["remote_phone"] == "5571999999999"
    assert conv["display_name"] == "Contato manual"
    assert conv["document_links"] == []
    assert g.client.post("/chat/conversations/start", json=payload).json()["id"] == conv["id"]
    assert not any("sendText" in path for path, _ in g.calls)
    response = g.client.post(
        f"/chat/conversations/{conv['id']}/messages",
        json={"client_request_id": str(uuid.uuid4()), "text": "Olá, primeiro atendimento"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "SENT"
    assert sum("sendText" in path for path, _ in g.calls) == 1
    assert webhook(g, incoming()).status_code == 200
    assert (
        g.client.get(f"/chat/conversations/{conv['id']}").json()["display_name"] == "Contato manual"
    )
    assert len(list(g.db.scalars(select(Contact).where(Contact.organization_id == g.org.id)))) == 1
    assert (
        g.client.patch(
            f"/chat/conversations/{conv['id']}", json={"status": "CLOSED", "is_archived": True}
        ).status_code
        == 200
    )
    reused = g.client.post("/chat/conversations/start", json=payload).json()
    assert reused["id"] == conv["id"] and reused["is_archived"] and reused["status"] == "CLOSED"


@pytest.mark.parametrize(
    "case,expected",
    [("foreign", 404), ("inactive", 404), ("no_phone", 422), ("outsider", 404), ("reader", 403)],
)
def test_start_conversation_validates_contact_and_instance_access(gateway, case, expected):
    g = gateway
    contact = Contact(
        organization_id=g.other_org.id if case == "foreign" else g.org.id,
        name="Contato",
        person_type="PF",
        is_active=case != "inactive",
        phone=None if case == "no_phone" else "5571999999999",
    )
    g.db.add(contact)
    g.db.commit()
    if case == "outsider":
        g.team.members = []
    if case == "reader":
        g.user.role = g.reader
    g.db.commit()
    response = g.client.post(
        "/chat/conversations/start",
        json={"connection_id": g.connection_id, "contact_id": str(contact.id)},
    )
    assert response.status_code == expected, response.text
    assert not g.calls


def test_new_contact_number_updates_from_instance_without_using_attendant_name(gateway):
    g = gateway
    g.contact_name = None
    unknown = incoming("unknown")
    unknown.pop("pushName")
    assert webhook(g, unknown).status_code == 200
    conv = g.client.get("/chat/conversations").json()["items"][0]
    assert conv["display_name"] == "5571999999999"
    g.contact_name = "Nome salvo na instância"
    outgoing = incoming("from-me")
    outgoing["key"]["fromMe"] = True
    outgoing["pushName"] = "Atendente (não usar)"
    assert webhook(g, outgoing).status_code == 200
    url = f"/chat/conversations/{conv['id']}"
    assert g.client.get(url).json()["display_name"] == "5571999999999"
    assert (
        webhook(
            g,
            {"remoteJid": outgoing["key"]["remoteJid"], "pushName": g.contact_name},
            event="contacts.update",
        ).status_code
        == 200
    )
    assert g.client.get(url).json()["display_name"] == g.contact_name
    g.contact_name = "Nome atualizado na agenda"
    assert g.client.post(url + "/refresh-contact").status_code == 200
    assert (
        g.client.post(
            url + "/messages", json={"client_request_id": str(uuid.uuid4()), "text": "Mensagem"}
        ).status_code
        == 200
    )
    assert g.client.get(url).json()["display_name"] == g.contact_name
    assert (
        g.client.put(
            f"/identity/contacts/{conv['contact_id']}", json={"name": "Nome manual"}
        ).status_code
        == 200
    )
    assert webhook(g, incoming("newer")).status_code == 200
    assert g.client.get(url).json()["display_name"] == "Nome manual"


def test_start_rejects_duplicate_phone_and_forged_contact_phone(gateway):
    g = gateway
    first = Contact(organization_id=g.org.id, name="Primeiro", phone="5571999999999")
    duplicate = Contact(organization_id=g.org.id, name="Outro", phone="+55 (71) 99999-9999")
    g.db.add_all([first, duplicate])
    g.db.commit()
    assert (
        g.client.post(
            "/chat/conversations/start",
            json={"connection_id": g.connection_id, "contact_id": str(first.id)},
        ).status_code
        == 409
    )
    assert (
        g.client.post(
            "/chat/conversations",
            json={
                "connection_id": g.connection_id,
                "contact_id": str(first.id),
                "remote_phone": "5571888888888",
            },
        ).status_code
        == 422
    )


def test_contact_directory_lists_identity_and_whatsapp_but_only_current_organization(gateway):
    g = gateway
    local = Contact(
        organization_id=g.org.id,
        name="Cadastro Identity",
        person_type="PF",
        origin_module="IDENTITY",
    )
    foreign = Contact(organization_id=g.other_org.id, name="Não mostrar", person_type="PF")
    g.db.add_all([local, foreign])
    g.db.commit()
    assert webhook(g, incoming()).status_code == 200
    result = g.client.get("/identity/contact-directory")
    assert result.status_code == 200, result.text
    assert result.json()["total"] == 2
    assert {row["origin_module"] for row in result.json()["items"]} == {"CHAT", "IDENTITY"}
    assert (
        g.client.get("/identity/contact-directory", params={"origin_module": "CHAT"}).json()[
            "total"
        ]
        == 1
    )
    assert (
        g.client.get("/identity/contact-directory", params={"contact_id": str(foreign.id)}).json()[
            "total"
        ]
        == 0
    )
    assert (
        g.client.get("/identity/contact-directory", params={"contact_id": str(local.id)}).json()[
            "items"
        ][0]["name"]
        == local.name
    )
    assert (
        g.client.get("/identity/contact-directory", params={"search": "Cadastro"}).json()["total"]
        == 1
    )
    g.team.members = []
    g.db.commit()
    rows = g.client.get("/identity/contact-directory").json()
    assert rows["total"] == 2
    assert all(not row["channels"] for row in rows["items"])
    assert (
        g.client.get(
            "/identity/contact-directory", params={"connection_id": g.connection_id}
        ).json()["total"]
        == 0
    )


def test_open_group_participant_does_not_save_until_inbound_direct(gateway):
    g = gateway
    assert webhook(g, group_message()).status_code == 200
    group = g.client.get("/chat/conversations").json()["items"][0]
    message = g.client.get(f"/chat/conversations/{group['id']}/messages").json()["items"][0]
    url = f"/chat/conversations/{group['id']}/participants/{message['id']}/direct"
    assert not list(g.db.scalars(select(Contact).where(Contact.organization_id == g.org.id)))
    opened = g.client.post(url)
    assert opened.status_code == 200, opened.text
    direct = opened.json()
    assert direct["contact_id"] is None and not direct["is_group"]
    assert g.client.post(url).json()["id"] == direct["id"]
    sent = g.client.post(f"/chat/conversations/{direct['id']}/messages",
                         json={"client_request_id": str(uuid.uuid4()), "text": "Olá do sistema"})
    assert sent.status_code == 200, sent.text
    assert not list(g.db.scalars(select(Contact).where(Contact.organization_id == g.org.id)))
    echo = incoming("outbound-before-inbound")
    echo["key"]["fromMe"] = True
    assert webhook(g, echo).status_code == 200
    assert not list(g.db.scalars(select(Contact).where(Contact.organization_id == g.org.id)))
    assert webhook(g, incoming("first-direct")).status_code == 200
    assert webhook(g, incoming("first-direct")).status_code == 200
    saved = g.client.get(f"/chat/conversations/{direct['id']}").json()
    assert saved["contact_id"]
    assert g.client.post(url).json()["id"] == direct["id"]
    assert len(list(g.db.scalars(select(Contact).where(Contact.organization_id == g.org.id)))) == 1
    g.user.role = g.reader
    g.db.commit()
    assert g.client.post(url).status_code == 403


def test_lid_only_participant_cannot_be_opened_as_a_phone(gateway):
    g = gateway
    assert webhook(g, group_message(participant="99887766@lid")).status_code == 200
    group = g.client.get("/chat/conversations").json()["items"][0]
    message = g.client.get(f"/chat/conversations/{group['id']}/messages").json()["items"][0]
    result = g.client.post(f"/chat/conversations/{group['id']}/participants/{message['id']}/direct")
    assert result.status_code == 422
    assert not list(g.db.scalars(select(Contact).where(Contact.organization_id == g.org.id)))
