"""Adaptador do contrato de Chat para a Evolution API."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

import httpx

from controlb.modules.chat.connectors.base import (
    ChatConnector,
    ConnectorAudio,
    ConnectorConnectionState,
    ConnectorError,
    ConnectorHistoryPage,
    ConnectorInstanceDetails,
    ConnectorInstanceResult,
    ConnectorMedia,
    ConnectorMessageResult,
    ConnectorPairingSession,
    ConnectorWebhookEvent,
    InboundMessage,
)

EVOLUTION_WEBHOOK_EVENTS = (
    "MESSAGES_UPSERT",
    "MESSAGES_UPDATE",
    "MESSAGES_REACTION",
    "SEND_MESSAGE",
    "CONNECTION_UPDATE",
    "CONTACTS_UPDATE",
    "CONTACTS_UPSERT",
    "GROUPS_UPSERT",
    "GROUPS_UPDATE",
)
GROUP_JID = re.compile(r"[0-9]{5,25}(?:-[0-9]{1,20})?@g\.us")
PERSON_JID = re.compile(r"[1-9][0-9]{7,14}@s\.whatsapp\.net")
MAX_AUDIO_BYTES = 20 * 1024 * 1024
MAX_MEDIA_RESPONSE_BYTES = 28 * 1024 * 1024


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

    async def configure_groups(self, enabled: bool) -> None:
        current = await self._request("GET", f"/settings/find/{self._encoded_instance}")
        fields = {
            "rejectCall",
            "msgCall",
            "alwaysOnline",
            "readMessages",
            "readStatus",
            "syncFullHistory",
            "wavoipToken",
        }
        settings = {key: value for key, value in current.items() if key in fields}
        settings["groupsIgnore"] = not enabled
        await self._request("POST", f"/settings/set/{self._encoded_instance}", payload=settings)

    async def fetch_groups(self) -> list[dict[str, str]]:
        rows = await self._request(
            "GET",
            f"/group/fetchAllGroups/{self._encoded_instance}?getParticipants=false",
            allow_list=True,
        )
        if not isinstance(rows, list):
            raise ConnectorError("Resposta de grupos inválida.")
        return [
            {"id": row["id"], "name": str(row.get("subject") or f"Grupo {row['id']}")[:255]}
            for row in rows
            if isinstance(row, dict)
            and isinstance(row.get("id"), str)
            and GROUP_JID.fullmatch(row["id"])
        ]

    async def fetch_contact_name(self, phone: str) -> str | None:
        jid = self.chat_id_for_phone(phone)
        rows = await self._request(
            "POST",
            f"/chat/findContacts/{self._encoded_instance}",
            payload={"where": {"remoteJid": jid}, "offset": 5, "page": 1},
            allow_list=True,
        )
        if not isinstance(rows, list):
            raise ConnectorError("Resposta de contatos inválida.")
        for row in rows:
            if not isinstance(row, dict) or row.get("remoteJid") != jid:
                continue
            for field in ("name", "pushName", "profileName"):
                value = row.get(field)
                if isinstance(value, str) and value.strip():
                    return value.strip()[:255]
        return None

    async def fetch_group_name(self, group_id: str) -> str | None:
        if not GROUP_JID.fullmatch(group_id):
            raise ConnectorError("Grupo inválido.")
        row = await self._request(
            "GET",
            f"/group/findGroupInfos/{self._encoded_instance}?groupJid={quote(group_id, safe='')}",
        )
        if row.get("id") not in {None, group_id}:
            raise ConnectorError("Grupo retornado não corresponde ao solicitado.")
        name = row.get("subject") or row.get("name")
        return name.strip()[:255] if isinstance(name, str) and name.strip() else None

    async def fetch_media(
        self, external_message_id, external_chat_id, *, from_me, participant=None
    ) -> ConnectorMedia:
        try:
            async with self._client.stream(
                "POST",
                f"{self.base_url}/chat/getBase64FromMediaMessage/{self._encoded_instance}",
                headers=self._headers,
                follow_redirects=False,
                json={
                    "message": {
                        "key": {
                            "id": external_message_id,
                            "remoteJid": external_chat_id,
                            "fromMe": from_me,
                            **({"participant": participant} if participant else {}),
                        }
                    },
                    "convertToMp4": False,
                },
            ) as response:
                response.raise_for_status()
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > MAX_MEDIA_RESPONSE_BYTES:
                        raise ValueError("media too large")
            data = json.loads(body)
            encoded = data.get("base64")
            if (
                not isinstance(encoded, str)
                or not encoded
                or len(encoded) > ((MAX_AUDIO_BYTES + 2) // 3) * 4
            ):
                raise ValueError("invalid base64")
            content = base64.b64decode(encoded, validate=True)
            if not content or len(content) > MAX_AUDIO_BYTES:
                raise ValueError("invalid size")
            mime = (
                str(data.get("mimetype") or data.get("mimeType") or "application/octet-stream")
                .split(";", 1)[0]
                .strip()
                .lower()
            )
            return ConnectorMedia(content, mime, str(data.get("fileName") or "")[:500] or None)
        except (httpx.HTTPError, AttributeError, TypeError, ValueError, binascii.Error):
            raise ConnectorError(
                "Não foi possível obter a mídia da instância (limite de 20 MiB)."
            ) from None

    async def fetch_avatar(self, destination: str) -> ConnectorMedia | None:
        target = destination if GROUP_JID.fullmatch(destination) else _normalize_number(destination)
        try:
            result = await self._request(
                "POST",
                f"/chat/fetchProfilePictureUrl/{self._encoded_instance}",
                payload={"number": target},
            )
        except ConnectorError:
            return None
        url = (
            result.get("profilePictureUrl")
            or result.get("profilePicUrl")
            or result.get("url")
        )
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            return None
        try:
            resp = await self._client.get(url, follow_redirects=True, timeout=10.0)
            resp.raise_for_status()
            content = resp.content
            if not content or len(content) > 5 * 1024 * 1024:
                return None
            mime = (
                resp.headers.get("content-type", "image/jpeg")
                .split(";", 1)[0]
                .strip()
                .lower()
            )
            return ConnectorMedia(content, mime or "image/jpeg")
        except (httpx.HTTPError, ValueError):
            return None

    async def send_reaction(self, key: dict[str, Any], emoji: str) -> None:
        await self._request(
            "POST",
            f"/message/sendReaction/{self._encoded_instance}",
            payload={"key": key, "reaction": emoji},
        )

    async def send_media(
        self,
        destination: str,
        content: bytes,
        mime_type: str,
        filename: str,
        caption: str,
        message_type: str,
        *,
        quoted: dict[str, Any] | None = None,
    ) -> ConnectorMessageResult:
        number = destination if GROUP_JID.fullmatch(destination) else _normalize_number(destination)
        payload: dict[str, Any] = {
            "number": number,
            "mediatype": message_type.lower(),
            "mimetype": mime_type,
            "fileName": filename,
            "caption": caption,
            "media": base64.b64encode(content).decode("ascii"),
        }
        if quoted:
            payload["quoted"] = quoted
            payload["options"] = {"quoted": quoted}

        if message_type == "AUDIO":
            audio_payload: dict[str, Any] = {
                "number": number,
                "audio": base64.b64encode(content).decode("ascii"),
                "encoding": True,
            }
            if quoted:
                audio_payload["quoted"] = quoted
                audio_payload["options"] = {"quoted": quoted}
            try:
                result = await self._request(
                    "POST",
                    f"/message/sendWhatsAppAudio/{self._encoded_instance}",
                    payload=audio_payload,
                )
            except ConnectorError:
                result = await self._request(
                    "POST",
                    f"/message/sendMedia/{self._encoded_instance}",
                    payload=payload,
                )
        else:
            result = await self._request(
                "POST",
                f"/message/sendMedia/{self._encoded_instance}",
                payload=payload,
            )
        key = result.get("key") if isinstance(result.get("key"), dict) else {}
        if not key.get("id"):
            raise ConnectorError("O provedor não confirmou o identificador do anexo.")
        status = _delivery_status(result.get("status"))
        return ConnectorMessageResult(
            str(key["id"]),
            str(key.get("remoteJid") or destination),
            "SENT" if status in {None, "PENDING"} else status,
        )

    async def delete_for_everyone(self, external_message_id, external_chat_id, *, participant=None):
        await self._request(
            "DELETE",
            f"/chat/deleteMessageForEveryone/{self._encoded_instance}",
            payload={
                "id": external_message_id,
                "remoteJid": external_chat_id,
                "fromMe": True,
                **({"participant": participant} if participant else {}),
            },
        )

    async def fetch_audio(
        self,
        external_message_id: str,
        external_chat_id: str,
        *,
        from_me: bool,
        participant: str | None = None,
    ) -> ConnectorAudio:
        # O cliente não escolhe URLs de mídia; o provedor resolve a mensagem nesta instância.
        try:
            async with self._client.stream(
                "POST",
                f"{self.base_url}/chat/getBase64FromMediaMessage/{self._encoded_instance}",
                headers=self._headers,
                follow_redirects=False,
                json={
                    "message": {
                        "key": {
                            "id": external_message_id,
                            "remoteJid": external_chat_id,
                            "fromMe": from_me,
                            **({"participant": participant} if participant else {}),
                        }
                    },
                    "convertToMp4": False,
                },
            ) as response:
                response.raise_for_status()
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > MAX_MEDIA_RESPONSE_BYTES:
                        raise ConnectorError("Áudio excede o limite de download.")
            data = json.loads(body)
            if not isinstance(data, dict):
                raise TypeError("invalid media")
            encoded = data.get("base64")
            mime = (
                str(data.get("mimetype") or data.get("mimeType") or "")
                .split(";", 1)[0]
                .strip()
                .lower()
            )
            if mime not in {
                "audio/ogg",
                "audio/mpeg",
                "audio/mp4",
                "audio/wav",
                "audio/x-wav",
                "audio/webm",
                "audio/aac",
                "audio/opus",
            }:
                raise ValueError("invalid audio type")
            if (
                not isinstance(encoded, str)
                or not encoded
                or len(encoded) > ((MAX_AUDIO_BYTES + 2) // 3) * 4
            ):
                raise ValueError("invalid audio size")
            content = base64.b64decode(encoded, validate=True)
            if not content or len(content) > MAX_AUDIO_BYTES:
                raise ValueError("invalid audio size")
            return ConnectorAudio(content, mime)
        except (httpx.HTTPError, TypeError, ValueError, binascii.Error):
            raise ConnectorError("Não foi possível obter um áudio válido da instância.") from None

    async def _request(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        allow_list: bool = False,
    ) -> Any:
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
        if not isinstance(result, dict) and not (allow_list and isinstance(result, list)):
            raise ConnectorError("A Evolution API retornou uma resposta inválida.")
        return result

    async def get_instance_details(self) -> ConnectorInstanceDetails:
        result = await self._request(
            "GET",
            f"/instance/fetchInstances?instanceName={self._encoded_instance}",
            allow_list=True,
        )
        rows = result if isinstance(result, list) else [result]
        item = next(
            (
                row
                for row in rows
                if isinstance(row, dict) and row.get("name") == self.instance_name
            ),
            None,
        )
        if item is None:
            raise ConnectorError("Instância não encontrada no provedor.")
        owner = str(item.get("ownerJid") or "")
        phone = owner.split("@", 1)[0].split(":", 1)[0]
        if not re.fullmatch(r"[1-9][0-9]{7,14}", phone):
            phone = None
        counts = item.get("_count") if isinstance(item.get("_count"), dict) else {}
        return ConnectorInstanceDetails(
            instance_id=_optional_string(item.get("id")),
            instance_name=self.instance_name,
            phone=phone,
            profile_name=_optional_string(item.get("profileName")),
            integration=_optional_string(item.get("integration")),
            state={"open": "CONNECTED", "close": "DISCONNECTED", "connecting": "CONNECTING"}.get(
                item.get("connectionStatus"), "ERROR"
            ),
            message_count=counts.get("Message"),
            chat_count=counts.get("Chat"),
        )

    async def fetch_history(
        self, page: int, page_size: int, snapshot_at: datetime
    ) -> ConnectorHistoryPage:
        result = await self._request(
            "POST",
            f"/chat/findMessages/{self._encoded_instance}",
            payload={
                "where": {
                    "messageTimestamp": {
                        "gte": "1970-01-01T00:00:00Z",
                        "lte": snapshot_at.isoformat(),
                    }
                },
                "page": page,
                "offset": page_size,
            },
        )
        data = result.get("messages")
        if not isinstance(data, dict) or not isinstance(data.get("records"), list):
            raise ConnectorError("Histórico inválido retornado pelo provedor.")
        rows = data["records"]
        if len(rows) > page_size or not isinstance(data.get("total"), int) or data["total"] < 0:
            raise ConnectorError("Paginação inválida retornada pelo provedor.")
        events = []
        for row in rows:
            if not isinstance(row, dict):
                raise ConnectorError("Mensagem inválida no histórico.")
            try:
                event = self.parse_webhook(
                    {"event": "messages.upsert", "instance": self.instance_name, "data": row}
                )
            except (TypeError, ValueError, OverflowError):
                raise ConnectorError("Mensagem inválida no histórico.") from None
            # Namespace próprio: replay de histórico pode recuperar callbacks antes ignorados.
            updates = row.get("MessageUpdate")
            ranks = {"FAILED": -1, "PENDING": 0, "SENT": 1, "DELIVERED": 2, "READ": 3}
            statuses = [
                _delivery_status(update.get("status"))
                for update in (updates if isinstance(updates, list) else [])
                if isinstance(update, dict)
            ]
            statuses.append(event.delivery_status)
            delivery = max(
                (status for status in statuses if status in ranks), key=ranks.get, default=None
            )
            events.append(
                replace(
                    event,
                    event_type="HISTORY_MESSAGE",
                    event_key="history:" + event.event_key,
                    delivery_status=delivery,
                )
            )
        return ConnectorHistoryPage(
            events=events,
            total=data["total"],
            has_more=bool(rows) and page * page_size < data["total"],
        )

    async def send_text(self, number: str, text: str, *, quoted: dict[str, Any] | None = None) -> ConnectorMessageResult:
        normalized_number = _normalize_number(number)
        return await self._send_text(normalized_number, text, quoted=quoted)

    async def send_group_text(self, group_id: str, text: str, *, quoted: dict[str, Any] | None = None) -> ConnectorMessageResult:
        if not GROUP_JID.fullmatch(group_id):
            raise ValueError("Identificador de grupo inválido.")
        return await self._send_text(group_id, text, quoted=quoted)

    async def _send_text(self, normalized_number: str, text: str, *, quoted: dict[str, Any] | None = None) -> ConnectorMessageResult:
        normalized_text = text.strip()
        if not normalized_text:
            raise ValueError("A mensagem não pode estar vazia.")

        payload: dict[str, Any] = {"number": normalized_number, "text": normalized_text}
        if quoted:
            payload["quoted"] = quoted
            payload["options"] = {"quoted": quoted}

        result = await self._request(
            "POST",
            f"/message/sendText/{self._encoded_instance}",
            payload=payload,
        )
        key = result.get("key") if isinstance(result.get("key"), dict) else {}
        external_id = str(key.get("id") or "").strip()
        if not external_id:
            raise ConnectorError("A Evolution API não retornou o identificador da mensagem.")
        external_chat_id = str(key.get("remoteJid") or normalized_number)
        delivery = _delivery_status(result.get("status"))
        return ConnectorMessageResult(
            external_message_id=external_id,
            external_chat_id=external_chat_id,
            # HTTP bem-sucedido + ID confirma aceitação, não entrega/leitura.
            status="SENT" if delivery in {None, "PENDING"} else delivery,
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

    async def create_instance(self) -> ConnectorInstanceResult:
        try:
            result = await self._request(
                "POST",
                "/instance/create",
                payload={
                    "instanceName": self.instance_name,
                    "qrcode": True,
                    "integration": "WHATSAPP-BAILEYS",
                },
            )
        except ConnectorError as exc:
            if exc.status_code in {400, 403, 409}:
                state = await self.get_connection_state()
                return ConnectorInstanceResult(
                    created=False,
                    already_existed=True,
                    state=state.state,
                    raw_payload=state.raw_payload,
                )
            raise
        pairing = _pairing_from_payload(result)
        return ConnectorInstanceResult(
            created=True,
            already_existed=False,
            state=pairing.state or "CONNECTING",
            qr_code_base64=pairing.qr_code_base64,
            pairing_code=pairing.pairing_code,
            raw_payload=result,
        )

    async def get_pairing_session(self) -> ConnectorPairingSession:
        result = await self._request("GET", f"/instance/connect/{self._encoded_instance}")
        pairing = _pairing_from_payload(result)
        if pairing.state == "CONNECTED" or pairing.qr_code_base64 or pairing.pairing_code:
            return pairing
        state = await self.get_connection_state()
        return ConnectorPairingSession(
            state=state.state,
            qr_code_base64=pairing.qr_code_base64,
            pairing_code=pairing.pairing_code,
            raw_payload=result,
        )

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
        # LID é um identificador opaco, nunca um telefone. Usar apenas o alias
        # telefônico explícito fornecido pela Evolution, sem converter IDs de grupos.
        alternate = str(key.get("remoteJidAlt") or data.get("remoteJidAlt") or "")
        if remote_jid.endswith("@lid") and re.fullmatch(
            r"[1-9][0-9]{7,14}@s\.whatsapp\.net", alternate
        ):
            remote_jid = alternate
        if len(external_id) > 255 or len(remote_jid) > 255:
            raise ValueError("Identificador inválido.")

        message = None
        # Grupos são canais próprios. Seu JID e LIDs não são telefones de contatos.
        personal = bool(PERSON_JID.fullmatch(remote_jid))
        group = bool(GROUP_JID.fullmatch(remote_jid))
        participant = str(key.get("participant") or data.get("participant") or "")[:255]
        participant_alt = str(key.get("participantAlt") or data.get("participantAlt") or "")
        resolved_participant = participant
        if participant.endswith("@lid") and PERSON_JID.fullmatch(participant_alt):
            resolved_participant = participant_alt
        reaction = None
        body = _message_body(data) if isinstance(data, dict) else {}
        reaction_source = None
        if event_type in {"MESSAGES_REACTION", "MESSAGE_REACTION"}:
            reaction_source = data.get("reaction") or data.get("reactionMessage") or data
        elif "reactionMessage" in body and isinstance(body["reactionMessage"], dict):
            reaction_source = body["reactionMessage"]

        if reaction_source and isinstance(reaction_source, dict):
            r_key = reaction_source.get("key") if isinstance(reaction_source.get("key"), dict) else key
            target_id = str(r_key.get("id") or "").strip()
            target_chat = str(r_key.get("remoteJid") or remote_jid).strip()
            alternate_target = str(r_key.get("remoteJidAlt") or alternate)
            if target_chat.endswith("@lid") and re.fullmatch(r"[1-9][0-9]{7,14}@s\.whatsapp\.net", alternate_target):
                target_chat = alternate_target
            emoji = str(reaction_source.get("text") or reaction_source.get("reaction") or "").strip()
            from_me = bool(r_key.get("fromMe") if r_key.get("fromMe") is not None else key.get("fromMe"))
            sender_id = participant if group else (target_chat if not from_me else "me")
            reaction = {
                "target_message_id": target_id,
                "target_chat_id": target_chat,
                "emoji": emoji,
                "from_me": from_me,
                "sender_external_id": sender_id,
                "sender_phone": _phone_from_jid(resolved_participant)
                if group and PERSON_JID.fullmatch(resolved_participant)
                else (_phone_from_jid(target_chat) if personal else None),
            }

        if (
            not reaction
            and event_type in {"MESSAGES_UPSERT", "SEND_MESSAGE"}
            and external_id
            and (personal or group)
        ):
            direction = "OUTBOUND" if bool(key.get("fromMe")) else "INBOUND"
            media = next(
                (
                    value
                    for field, value in _message_body(data).items()
                    if field
                    in {
                        "imageMessage",
                        "videoMessage",
                        "documentMessage",
                        "audioMessage",
                        "stickerMessage",
                    }
                    and isinstance(value, dict)
                ),
                {},
            )
            message = InboundMessage(
                external_message_id=external_id,
                external_chat_id=remote_jid,
                remote_phone="" if group else _phone_from_jid(remote_jid),
                direction=direction,
                message_type=_message_type(data),
                content=_message_content(data),
                occurred_at=_message_datetime(data),
                sender_name=_sender_name(data) if direction == "INBOUND" else None,
                is_group=group,
                media_mime_type=str(media.get("mimetype") or "")[:150] or None,
                media_filename=str(media.get("fileName") or "")[:500] or None,
                group_name=_optional_string(data.get("groupName") or data.get("subject")),
                sender_external_id=participant if group else remote_jid,
                sender_phone=_phone_from_jid(resolved_participant)
                if group and PERSON_JID.fullmatch(resolved_participant)
                else (_phone_from_jid(remote_jid) if personal else None),
                reply=_reply_info(data),
            )

        # A criação da mensagem é idempotente pelo ID externo. Atualizações de
        # entrega/leitura usam o payload completo, pois o mesmo ID evolui por
        # vários estados legítimos (SENT -> DELIVERED -> READ).
        if reaction:
            event_key_source = (
                f"REACTION:{reaction['target_chat_id']}:{reaction['target_message_id']}:"
                f"{reaction['sender_external_id']}:{reaction['emoji']}"
            )
        elif event_type in {"MESSAGES_UPSERT", "SEND_MESSAGE"} and external_id:
            event_key_source = f"{event_type}:{remote_jid}:{external_id}"
        else:
            event_key_source = _canonical_json({"event": event_type, "data": data})

        event_key = hashlib.sha256(event_key_source.encode("utf-8")).hexdigest()
        update = data.get("update") if isinstance(data.get("update"), dict) else {}
        contact_jid = str(data.get("remoteJid") or data.get("id") or "")
        contact_name = next(
            (
                data.get(field).strip()[:255]
                for field in ("name", "pushName", "profileName")
                if isinstance(data.get(field), str) and data[field].strip()
            ),
            None,
        )
        return ConnectorWebhookEvent(
            group_id=str(data.get("id"))
            if event_type in {"GROUPS_UPSERT", "GROUPS_UPDATE"}
            and GROUP_JID.fullmatch(str(data.get("id") or ""))
            else None,
            group_name=_optional_string(data.get("subject"))
            if event_type in {"GROUPS_UPSERT", "GROUPS_UPDATE"}
            else None,
            event_key=event_key,
            event_type=event_type,
            external_instance_id=_optional_string(instance),
            message=message,
            external_message_id=external_id or None,
            external_chat_id=remote_jid or None,
            contact_phone=_phone_from_jid(contact_jid)
            if event_type in {"CONTACTS_UPDATE", "CONTACTS_UPSERT"}
            and re.fullmatch(r"[1-9][0-9]{7,14}@s\.whatsapp\.net", contact_jid)
            else None,
            contact_name=contact_name
            if event_type in {"CONTACTS_UPDATE", "CONTACTS_UPSERT"}
            else None,
            delivery_status=_delivery_status(data.get("status", update.get("status")))
            if event_type in {"MESSAGES_UPDATE", "MESSAGES_UPSERT", "SEND_MESSAGE"}
            else None,
            connection_state={
                "open": "CONNECTED",
                "connecting": "CONNECTING",
                "close": "DISCONNECTED",
            }.get(data.get("state"))
            if event_type == "CONNECTION_UPDATE"
            else None,
            reaction=reaction,
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()


def _pairing_from_payload(payload: dict[str, Any]) -> ConnectorPairingSession:
    qrcode = payload.get("qrcode") if isinstance(payload.get("qrcode"), dict) else payload
    raw_base64 = qrcode.get("base64") if isinstance(qrcode, dict) else None
    if not isinstance(raw_base64, str):
        raw_base64 = payload.get("base64") if isinstance(payload.get("base64"), str) else None
    qr_code = _normalize_qr_base64(raw_base64)
    pairing_code = None
    for source in (qrcode, payload):
        if isinstance(source, dict):
            value = source.get("pairingCode") or source.get("pairing_code")
            if isinstance(value, str) and value.strip():
                pairing_code = value.strip()[:64]
                break
    instance = payload.get("instance") if isinstance(payload.get("instance"), dict) else {}
    raw_state = str(
        instance.get("state")
        or instance.get("status")
        or payload.get("state")
        or ("connecting" if qr_code else "unknown")
    ).lower()
    state = {
        "open": "CONNECTED",
        "connected": "CONNECTED",
        "connecting": "CONNECTING",
        "close": "DISCONNECTED",
        "closed": "DISCONNECTED",
        "disconnected": "DISCONNECTED",
        "created": "CONNECTING" if qr_code or pairing_code else "DISCONNECTED",
    }.get(raw_state, "CONNECTING" if qr_code or pairing_code else "ERROR")
    return ConnectorPairingSession(
        state=state,
        qr_code_base64=qr_code,
        pairing_code=pairing_code,
        raw_payload=payload,
    )


def _normalize_qr_base64(value: str | None) -> str | None:
    if not value:
        return None
    stripped = value.strip()
    if not stripped or len(stripped) > 1_000_000:
        return None
    if stripped.startswith("data:"):
        if not re.fullmatch(r"data:image/(?:png|jpeg);base64,[A-Za-z0-9+/=]+", stripped):
            return None
        return stripped
    if not re.fullmatch(r"[A-Za-z0-9+/=]+", stripped):
        return None
    return f"data:image/png;base64,{stripped}"


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


def _sender_name(data):
    for key in ("pushName", "profileName"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:255]
    return None


def _message_body(data):
    message = data.get("message") if isinstance(data.get("message"), dict) else {}
    for _ in range(5):
        wrapper = next(
            (
                message[key]
                for key in (
                    "ephemeralMessage",
                    "viewOnceMessage",
                    "viewOnceMessageV2",
                    "viewOnceMessageV2Extension",
                    "documentWithCaptionMessage",
                )
                if isinstance(message.get(key), dict)
            ),
            None,
        )
        if wrapper is None or not isinstance(wrapper.get("message"), dict):
            break
        message = wrapper["message"]
    return message


def _reply_info(data: dict[str, Any]) -> dict[str, Any] | None:
    body = _message_body(data)
    context_info = None
    if isinstance(body, dict):
        for wrapper in body.values():
            if isinstance(wrapper, dict) and isinstance(wrapper.get("contextInfo"), dict):
                context_info = wrapper["contextInfo"]
                break
        if not context_info and isinstance(body.get("contextInfo"), dict):
            context_info = body["contextInfo"]
    if not isinstance(context_info, dict):
        return None
    stanza_id = context_info.get("stanzaId")
    if not stanza_id:
        return None
    quoted_msg = context_info.get("quotedMessage")
    text = None
    if isinstance(quoted_msg, dict):
        text = (
            quoted_msg.get("conversation")
            or (quoted_msg.get("extendedTextMessage") or {}).get("text")
            or (quoted_msg.get("imageMessage") or {}).get("caption")
            or (quoted_msg.get("videoMessage") or {}).get("caption")
            or (quoted_msg.get("documentMessage") or {}).get("caption")
            or (quoted_msg.get("documentMessage") or {}).get("fileName")
        )
    return {
        "external_message_id": str(stanza_id),
        "participant": str(context_info.get("participant") or ""),
        "text": str(text)[:500] if text else None,
    }


def _message_type(data: dict[str, Any]) -> str:
    message = _message_body(data)
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
    message = _message_body(data)
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
