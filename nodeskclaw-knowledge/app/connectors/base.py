"""Connector protocol and capability declarations."""

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from app.connectors.models import DiscoveryPage, FetchedSource, SourceDescriptor


@dataclass(frozen=True)
class ConnectorCapabilities:
    incremental_cursor: bool = False
    stable_external_id: bool = True
    delete_events: bool = False
    folders: bool = False
    source_metadata: bool = True
    authentication: bool = False


@runtime_checkable
class KnowledgeSourceConnector(Protocol):
    capabilities: ConnectorCapabilities

    async def test_connection(self) -> dict[str, Any]:
        ...

    async def discover(self, *, cursor: dict[str, Any] | None = None) -> DiscoveryPage:
        ...

    async def fetch(self, descriptor: SourceDescriptor) -> FetchedSource:
        ...

    async def close(self) -> None:
        ...
