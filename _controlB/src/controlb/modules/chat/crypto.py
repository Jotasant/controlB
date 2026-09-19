"""Proteção reversível das credenciais usadas pelos conectores externos."""

from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from controlb.config import get_settings


class CredentialDecryptionError(ValueError):
    """Indica que uma credencial não pode ser aberta com a chave atual."""


def _fernet() -> Fernet:
    settings = get_settings()
    source_key = settings.chat_credentials_key or settings.secret_key
    derived_key = base64.urlsafe_b64encode(hashlib.sha256(source_key.encode("utf-8")).digest())
    return Fernet(derived_key)


def encrypt_secret(value: str) -> str:
    """Criptografa um segredo antes da persistência."""

    if not value:
        raise ValueError("O segredo não pode estar vazio.")
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret(value: str) -> str:
    """Descriptografa um segredo sem expor detalhes criptográficos ao domínio."""

    try:
        return _fernet().decrypt(value.encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeDecodeError, ValueError) as exc:
        raise CredentialDecryptionError(
            "Não foi possível descriptografar a credencial do conector."
        ) from exc


def encrypt_credentials(values: dict[str, Any]) -> str:
    """Serializa e protege o conjunto de credenciais específico do provedor."""

    if not values:
        raise ValueError("Informe ao menos uma credencial do conector.")
    return encrypt_secret(json.dumps(values, ensure_ascii=False, separators=(",", ":")))


def decrypt_credentials(value: str) -> dict[str, Any]:
    """Abre credenciais mantendo o formato extensível por provedor."""

    try:
        decoded = json.loads(decrypt_secret(value))
    except json.JSONDecodeError as exc:
        raise CredentialDecryptionError("As credenciais do conector são inválidas.") from exc
    if not isinstance(decoded, dict):
        raise CredentialDecryptionError("As credenciais do conector são inválidas.")
    return decoded
