"""Download autorizado e fila durável de transcrição local, independente do provedor."""

import asyncio
import hashlib
import importlib.util
import logging
import threading
from functools import lru_cache
from io import BytesIO
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import select, text

from controlb.config import get_settings
from controlb.db import SessionLocal
from controlb.modules.chat import repository as repo
from controlb.modules.chat import service
from controlb.modules.chat.connectors.base import ConnectorError
from controlb.modules.chat.models import ChatConnection, ChatConversation, ChatMessage

logger = logging.getLogger(__name__)


def _model_files_available(path):
    # tokenizer.json ausente faria o motor tentar obter um tokenizer na rede.
    try:
        return bool(
            path
            and Path(path).is_absolute()
            and all(
                (Path(path) / name).is_file()
                for name in ("model.bin", "config.json", "tokenizer.json")
            )
        )
    except OSError:
        return False


def transcription_ready():
    return (
        _model_files_available(get_settings().chat_stt_model_path)
        and importlib.util.find_spec("faster_whisper") is not None
    )


def initial_status(enabled):
    if not enabled:
        return "NOT_REQUESTED"
    return (
        "PENDING"
        if transcription_ready() and get_settings().chat_audio_worker_enabled
        else "NOT_CONFIGURED"
    )


def authorized_message(db, user, message_id):
    service.require(user, "chat:view")
    message = db.scalar(
        select(ChatMessage).where(
            ChatMessage.id == message_id, ChatMessage.organization_id == user.organization_id
        )
    )
    if message is None or message.deleted_at:
        raise HTTPException(404, "Mensagem não encontrada.")
    conversation = service.conversation(db, user, message.conversation_id)
    connection = service.connection(db, user, conversation.connection_id, active=True)
    if message.message_type != "AUDIO" or not message.external_message_id:
        raise HTTPException(422, "Esta mensagem não possui áudio disponível.")
    return message, conversation, connection


async def download(db, user, message_id):
    message, conversation, connection = authorized_message(db, user, message_id)
    try:
        media = await _fetch(connection, conversation, message)
    except ConnectorError:
        raise HTTPException(
            502,
            "Áudio indisponível no provedor. Ele pode ter expirado; tente novamente mais tarde.",
        ) from None
    # A participação pode ter sido revogada durante a chamada externa.
    authorized_message(db, user, message_id)
    return media


async def _fetch(connection, conversation, message):
    adapter = service.connector_for(connection, network=True)
    try:
        return await adapter.fetch_audio(
            message.external_message_id,
            conversation.external_chat_id,
            from_me=message.direction == "OUTBOUND",
            **({"participant": message.sender_external_id} if conversation.is_group else {}),
        )
    finally:
        await adapter.aclose()


def _try_lock(db, message_id):
    key = int.from_bytes(hashlib.sha256(b"audio:" + message_id.bytes).digest()[:8], signed=True)
    return db.scalar(text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": key})


def queue_transcription(db, user, message_id):
    service.require(user, "chat:send")
    message, _, connection = authorized_message(db, user, message_id)
    if not connection.transcription_enabled:
        raise HTTPException(409, "Habilite a transcrição na configuração desta instância.")
    if not transcription_ready() or not get_settings().chat_audio_worker_enabled:
        raise HTTPException(
            503,
            "Transcrição local não configurada no servidor. Configure o motor e o modelo de áudio.",
        )
    if not _try_lock(db, message_id):
        return message
    db.refresh(message)
    if message.transcription_status != "DONE":
        message.transcription_status = "PENDING"
        db.flush()
    return message


@lru_cache(maxsize=1)
def _model(path):
    if not _model_files_available(path):
        raise ValueError("Complete local model required")
    from faster_whisper import WhisperModel

    return WhisperModel(
        path, device="cpu", compute_type="int8", local_files_only=True, cpu_threads=2
    )


def transcribe(content):
    """Decodifica no máximo dez minutos e não baixa modelos automaticamente."""
    import av
    import numpy as np

    pcm = bytearray()
    with av.open(BytesIO(content)) as container:
        resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
        for frame in container.decode(audio=0):
            for converted in resampler.resample(frame):
                pcm.extend(converted.to_ndarray().tobytes())
                if len(pcm) > 16000 * 2 * 600:
                    raise ValueError("Audio exceeds ten minutes")
        for converted in resampler.resample(None):
            pcm.extend(converted.to_ndarray().tobytes())
    if not pcm or len(pcm) > 16000 * 2 * 600:
        raise ValueError("Invalid audio duration")
    samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
    segments, _ = _model(get_settings().chat_stt_model_path).transcribe(samples, beam_size=1)
    return " ".join(segment.text.strip() for segment in segments).strip()[:100000]


def process_one(message_id):
    with SessionLocal() as db:
        if not _try_lock(db, message_id):
            return False
        message = db.get(ChatMessage, message_id)
        if (
            message is None
            or message.deleted_at is not None
            or message.transcription_status != "PENDING"
            or message.message_type != "AUDIO"
        ):
            return False
        conversation = db.get(ChatConversation, message.conversation_id)
        connection = db.get(ChatConnection, conversation.connection_id)
        if (
            not connection.is_active
            or not connection.transcription_enabled
            or message.organization_id != connection.organization_id
            or conversation.team_id != connection.team_id
            or message.team_id != connection.team_id
            or not repo.team_is_active(db, connection.organization_id, connection.team_id)
        ):
            message.transcription_status = "NOT_REQUESTED"
        elif not transcription_ready():
            message.transcription_status = "NOT_CONFIGURED"
        else:
            try:
                media = asyncio.run(_fetch(connection, conversation, message))
                result = transcribe(media.content)
                repo.lock_connection(db, connection.id)
                db.refresh(message)
                if message.deleted_at:
                    db.commit()
                    return True
                # Revalidar se a transcrição foi desabilitada enquanto o modelo processava.
                db.refresh(connection)
                if not connection.is_active or not connection.transcription_enabled:
                    message.transcription_status = "NOT_REQUESTED"
                else:
                    message.transcription = result
                    message.media_mime_type = media.mime_type
                    message.transcription_status = "DONE"
            except Exception:  # noqa: BLE001 - isola falhas dos decodificadores opcionais sem expor conteúdo
                # Nunca registrar o conteúdo do áudio, credenciais ou texto transcrito.
                message.transcription_status = "FAILED"
                logger.warning("Falha na transcrição da mensagem %s", message.id)
        db.commit()
        return True


def tick():
    with SessionLocal() as db:
        pending = list(
            db.scalars(
                select(ChatMessage.id)
                .where(
                    ChatMessage.transcription_status == "PENDING",
                    ChatMessage.message_type == "AUDIO",
                )
                .order_by(ChatMessage.created_at, ChatMessage.id)
                .limit(10)
            )
        )
    for message_id in pending:
        process_one(message_id)


def run_worker(stop: threading.Event):
    # Apenas áudio. Não executa recuperação/sincronização de histórico de mensagens.
    while not stop.wait(5):
        try:
            if transcription_ready():
                tick()
        except Exception:  # noqa: BLE001 - uma falha transitória não encerra o consumidor da fila
            logger.warning("Fila de transcrição temporariamente indisponível.")
