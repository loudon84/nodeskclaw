"""Static connector type registry."""

from __future__ import annotations

from collections.abc import Callable

from app.connectors.base import KnowledgeSourceConnector

ConnectorClass = type[KnowledgeSourceConnector]

CONNECTOR_REGISTRY: dict[str, ConnectorClass | None] = {
    "filesystem": None,
    "http_manifest": None,
    "s3_compatible": None,
}


def register(connector_type: str, cls: ConnectorClass | None = None) -> ConnectorClass | Callable[[ConnectorClass], ConnectorClass]:
    def _store(c: ConnectorClass) -> ConnectorClass:
        CONNECTOR_REGISTRY[connector_type] = c
        return c

    if cls is not None:
        return _store(cls)
    return _store


def get_connector_class(connector_type: str) -> ConnectorClass:
    _ensure_builtin_connectors_loaded()
    if connector_type not in CONNECTOR_REGISTRY:
        raise KeyError(f"unknown connector type: {connector_type}")
    cls = CONNECTOR_REGISTRY[connector_type]
    if cls is None:
        raise KeyError(f"connector type not implemented: {connector_type}")
    return cls


def list_types() -> list[str]:
    _ensure_builtin_connectors_loaded()
    return sorted(CONNECTOR_REGISTRY.keys())


def _ensure_builtin_connectors_loaded() -> None:
    if CONNECTOR_REGISTRY.get("filesystem") is None:
        from app.connectors.filesystem import connector as _fs  # noqa: F401
    if CONNECTOR_REGISTRY.get("http_manifest") is None:
        from app.connectors.http_manifest import connector as _http  # noqa: F401
