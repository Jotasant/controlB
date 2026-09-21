"""Regressões HTTP de mídias, nomes protegidos e exclusões sem reenviar."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
import test_chat_api as shared_chat
from test_chat_api import (
    create_conversation,
    group_message,
    incoming,
    webhook,
)

from controlb.modules.chat.models import ChatMessage
from controlb.modules.identity import service as identity_service
from controlb.modules.identity.models import Contact
from controlb.modules.identity.schemas import ContactUpdate


@pytest.fixture
def gateway(monkeypatch):
    yield from shared_chat.gateway.__wrapped__(monkeypatch)


def receive_media(g, kind="image", group=False, identifier="media-1"):
    data = group_message(identifier) if group else incoming(identifier)
    data["message"] = {
        f"{kind}Message": {
            "mimetype": f"{kind}/mp4" if kind == "video" else "image/png",
            "fileName": "foto.png",
            "caption": "Legenda para pesquisa",
        }
    }
    assert webhook(g, data).status_code == 200
    conv = g.client.get("/chat/conversations").json()["items"][0]
    message = next(
        m
        for m in g.client.get(f"/chat/conversations/{conv['id']}/messages").json()["items"]
        if m["external_message_id"] == identifier
    )
    return conv, message, data


def test_manual_name_survives_messages_contacts_and_history_even_when_same_as_profile(gateway):
    g = gateway
    webhook(g, incoming())
    conv = g.client.get("/chat/conversations").json()["items"][0]
    contact_id = uuid.UUID(conv["contact_id"])
    identity_service.update_contact(g.db, contact_id, g.org.id, ContactUpdate(name="Cliente"))
    g.db.commit()
    assert g.db.get(Contact, contact_id).name_manually_set
    data = incoming("changed")
    data["pushName"] = "Outro nome"
    webhook(g, data)
    webhook(
        g,
        {"remoteJid": "5571999999999@s.whatsapp.net", "name": "Nome na agenda"},
        "contacts.update",
    )
    g.contact_name = "Nome externo"
    g.client.post(f"/chat/connections/{g.connection_id}/sync", json={})
    assert g.client.get(f"/chat/conversations/{conv['id']}").json()["display_name"] == "Cliente"
    identity_service.update_contact(g.db, contact_id, g.org.id, ContactUpdate(name="Minha escolha"))
    g.db.commit()
    assert (
        g.client.get(f"/chat/conversations/{conv['id']}").json()["display_name"] == "Minha escolha"
    )
    result = g.client.post(
        f"/chat/conversations/{conv['id']}/refresh-contact", params={"replace_manual": True}
    )
    assert result.json()["display_name"] == "Nome externo"
    webhook(
        g,
        {"remoteJid": "5571999999999@s.whatsapp.net", "name": "Mudou novamente"},
        "contacts.update",
    )
    assert (
        g.client.get(f"/chat/conversations/{conv['id']}").json()["display_name"] == "Nome externo"
    )


def test_group_name_resolved_without_changing_sender_or_sending_message(gateway):
    g = gateway
    webhook(g, group_message())
    conv = g.client.get("/chat/conversations").json()["items"][0]
    result = g.client.post(f"/chat/conversations/{conv['id']}/refresh-contact")
    assert result.status_code == 200, result.text
    assert result.json()["display_name"] == "Nome correto do grupo"
    assert all("sendText" not in path for path, _ in g.calls)


@pytest.mark.parametrize("group", [False, True])
@pytest.mark.parametrize("kind", ["image", "video", "document"])
def test_media_download_cache_gallery_and_permissions(gateway, group, kind):
    g = gateway
    if kind == "video":
        g.media_bytes, g.media_mime = b"\x00\x00\x00\x18ftypisom-video", "video/mp4"
    if kind == "document":
        g.media_bytes, g.media_mime = b"%PDF-test", "application/pdf"
    conv, message, _ = receive_media(g, kind, group)
    url = f"/chat/messages/{message['id']}/media"
    first = g.client.get(url)
    assert first.status_code == 200, first.text
    assert first.content == g.media_bytes
    assert first.headers["cache-control"] == "no-store"
    assert first.headers["x-content-type-options"] == "nosniff"
    assert ("attachment" in first.headers["content-disposition"]) == (kind == "document")
    assert g.calls[-1][1]["message"]["key"]["remoteJid"] == conv["external_chat_id"]
    if group:
        assert g.calls[-1][1]["message"]["key"]["participant"] == "5571999999999@s.whatsapp.net"
    calls = len(g.calls)
    assert g.client.get(url).content == first.content and len(g.calls) == calls
    gallery = g.client.get(
        f"/chat/conversations/{conv['id']}/media",
        params={"search": "pesquisa", "kind": kind.upper()},
    ).json()
    assert gallery["total"] == 1 and gallery["items"][0]["id"] == message["id"]
    assert "media_blob" not in gallery["items"][0]
    g.team.members = []
    g.db.commit()
    assert g.client.get(url).status_code == 404
    assert g.client.get(f"/chat/conversations/{conv['id']}/media").status_code == 404


def test_active_content_mislabeled_as_image_is_download_only(gateway):
    g = gateway
    g.media_bytes, g.media_mime = b'<svg onload="alert(1)">', "image/png"
    _, message, _ = receive_media(g)
    result = g.client.get(f"/chat/messages/{message['id']}/media")
    assert result.headers["content-type"] == "application/octet-stream"
    assert result.headers["content-disposition"].startswith("attachment")


@pytest.mark.parametrize("group", [False, True])
def test_attachment_send_is_durable_idempotent_and_not_inflated_by_echo(gateway, group):
    g = gateway
    if group:
        webhook(g, group_message())
        conv = g.client.get("/chat/conversations").json()["items"][0]["id"]
    else:
        conv = create_conversation(g)
    url = f"/chat/conversations/{conv}/media"
    params = {"client_request_id": str(uuid.uuid4()), "filename": "foto.png", "caption": "Anexo"}
    headers = {"Content-Type": "image/png"}
    result = g.client.post(url, params=params, content=g.media_bytes, headers=headers)
    assert result.status_code == 200, result.text
    message = result.json()
    assert message["status"] == "SENT" and message["author_name"] == "Chat"
    assert message["message_type"] == "IMAGE"
    assert (
        g.client.post(url, params=params, content=g.media_bytes, headers=headers).json()["id"]
        == message["id"]
    )
    assert sum("sendMedia" in path for path, _ in g.calls) == 1
    assert (
        g.client.post(
            url, params=params, content=g.media_bytes + b"different", headers=headers
        ).status_code
        == 409
    )
    g.calls.clear()
    assert g.client.get(f"/chat/messages/{message['id']}/media").content == g.media_bytes
    assert not g.calls
    echo = group_message(g.send_id) if group else incoming(g.send_id)
    echo["key"]["fromMe"] = True
    echo["message"] = {"imageMessage": {"mimetype": "image/png"}}
    webhook(g, echo)
    assert g.client.get(f"/chat/conversations/{conv}/media").json()["total"] == 1


def test_upload_size_limits_and_uncertain_send_not_retried(gateway, monkeypatch):
    from controlb.modules.chat import media

    g = gateway
    conv = create_conversation(g)
    url = f"/chat/conversations/{conv}/media"
    params = {"client_request_id": str(uuid.uuid4()), "filename": "file.bin"}
    monkeypatch.setattr(media, "MAX_BYTES", 20)
    assert g.client.post(url, params=params, content=b"x" * 21).status_code == 413
    assert g.client.post(url, params=params, content=b"").status_code == 413
    assert not g.calls
    g.timeout = True
    result = g.client.post(url, params=params, content=b"x")
    assert result.json()["status"] == "PENDING"
    g.client.post(url, params=params, content=b"x")
    assert sum("sendMedia" in path for path, _ in g.calls) == 1


def test_local_message_delete_purges_content_and_prevents_history_resurrection(gateway):
    g = gateway
    conv, message, payload = receive_media(g)
    g.client.get(f"/chat/messages/{message['id']}/media")
    g.calls.clear()
    assert g.client.delete(f"/chat/messages/{message['id']}").json()["scope"] == "LOCAL"
    assert not g.calls
    assert g.client.get(f"/chat/messages/{message['id']}/media").status_code == 404
    assert g.client.get(f"/chat/conversations/{conv['id']}/media").json()["total"] == 0
    webhook(g, payload)
    g.history_rows = [payload]
    g.client.post(f"/chat/connections/{g.connection_id}/sync", json={})
    messages = g.client.get(f"/chat/conversations/{conv['id']}/messages").json()["items"]
    assert len(messages) == 1 and messages[0]["deleted_at"] and messages[0]["content"] is None
    stored = g.db.get(ChatMessage, uuid.UUID(message["id"]))
    g.db.refresh(stored)
    assert stored.media_blob is None
    assert g.client.get(f"/chat/conversations/{conv['id']}").json()["last_message_preview"] is None
    assert all("deleteMessage" not in path for path, _ in g.calls)


def test_channel_delete_is_local_and_new_live_message_can_reopen_without_old_history(gateway):
    g = gateway
    conv, message, payload = receive_media(g)
    assert g.client.delete(f"/chat/conversations/{conv['id']}").json()["scope"] == "LOCAL"
    assert g.client.get("/chat/conversations").json()["total"] == 0
    assert g.client.get(f"/chat/messages/{message['id']}/media").status_code == 404
    g.history_rows = [payload]
    g.client.post(f"/chat/connections/{g.connection_id}/sync", json={})
    assert g.client.get("/chat/conversations").json()["total"] == 0
    fresh = incoming("after-deletion")
    fresh["messageTimestamp"] = (datetime.now(UTC) + timedelta(seconds=1)).timestamp()
    webhook(g, fresh)
    assert g.client.get("/chat/conversations").json()["total"] == 1
    rows = g.client.get(f"/chat/conversations/{conv['id']}/messages").json()["items"]
    assert len([m for m in rows if not m["deleted_at"]]) == 1


@pytest.mark.parametrize("failure", [None, 401, 500])
def test_delete_for_everyone_is_explicit_and_uncertain_result_not_repeated(gateway, failure):
    g = gateway
    conv = create_conversation(g)
    sent = g.client.post(
        f"/chat/conversations/{conv}/messages",
        json={"client_request_id": str(uuid.uuid4()), "text": "Mensagem"},
    ).json()
    g.calls.clear()
    if failure:
        g.transport_status = failure
    url = f"/chat/messages/{sent['id']}/delete-for-everyone"
    result = g.client.post(url)
    assert result.status_code == 200, result.text
    assert result.json()["deleted"] == (failure is None)
    assert g.calls[0] == (
        "/chat/deleteMessageForEveryone/comercial",
        {"id": "sent-1", "remoteJid": "5571999999999@s.whatsapp.net", "fromMe": True},
    )
    if failure != 401:
        repeated = g.client.post(url)
        assert repeated.status_code == (409 if failure == 500 else 200)
        assert len(g.calls) == 1


def test_delete_permissions_and_inbound_revoke_rejected(gateway):
    g = gateway
    conv, message, _ = receive_media(g)
    assert g.client.post(f"/chat/messages/{message['id']}/delete-for-everyone").status_code == 409
    g.user.role = g.reader
    g.db.commit()
    assert g.client.delete(f"/chat/messages/{message['id']}").status_code == 403
    assert g.client.delete(f"/chat/conversations/{conv['id']}").status_code == 403
    assert not g.calls
