"""Static connector type registry."""

from app.connectors.base import KnowledgeSourceConnector

ConnectorClass = type[KnowledgeSourceConnector]

# Placeholders reserved for reference connectors (implementations land in later tasks).
CONNECTOR_REGISTRY: dict[str, ConnectorClass | None] = {
    "filesystem": None,
    "http_manifest": None,
    "s3_compatible": None,
}


def register(connector_type: str, cls: ConnectorClass) -> ConnectorClass:
    CONNECTOR_REGISTRY[connector_type] = cls
    return cls


def get_connector_class(connector_type: str) -> ConnectorClass:
    if connector_type not in CONNECTOR_REGISTRY:
        raise KeyError(f"unknown connector type: {connector_type}")
    cls = CONNECTOR_REGISTRY[connector_type]
    if cls is None:
        raise KeyError(f"connector type not implemented: {connector_type}")
    return cls


def list_types() -> list[str]:
    return sorted(CONNECTOR_REGISTRY.keys())
