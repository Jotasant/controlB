"""Registro dos adaptadores disponíveis sem condicionais no domínio do Chat."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from controlb.modules.chat.connectors.base import ChatConnector
from controlb.modules.chat.connectors.evolution import EvolutionConnector

ConnectorFactory = Callable[[dict[str, Any], dict[str, Any]], ChatConnector]


def _evolution_factory(configuration: dict[str, Any], credentials: dict[str, Any]) -> ChatConnector:
    return EvolutionConnector(
        base_url=str(configuration.get("base_url") or ""),
        instance_name=str(configuration.get("instance_name") or ""),
        api_key=str(credentials.get("api_key") or ""),
        timeout_seconds=float(configuration.get("timeout_seconds") or 20),
    )


_CONNECTOR_FACTORIES: dict[str, ConnectorFactory] = {"EVOLUTION": _evolution_factory}


def available_providers() -> list[str]:
    return sorted(_CONNECTOR_FACTORIES)


def create_connector(
    provider: str,
    *,
    configuration: dict[str, Any],
    credentials: dict[str, Any],
) -> ChatConnector:
    """Instancia o adaptador registrado para o provedor solicitado."""

    normalized_provider = provider.strip().upper()
    factory = _CONNECTOR_FACTORIES.get(normalized_provider)
    if factory is None:
        raise ValueError(f"Conector de Chat não suportado: {normalized_provider or provider}.")
    return factory(configuration, credentials)
