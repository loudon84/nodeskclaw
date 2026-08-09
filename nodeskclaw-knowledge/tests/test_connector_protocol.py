"""Connector protocol contract tests."""

from typing import Any

import pytest

from app.connectors.base import ConnectorCapabilities, KnowledgeSourceConnector
from app.connectors.models import DiscoveryPage, FetchedSource, SourceDescriptor
from app.connectors.registry import (
    CONNECTOR_REGISTRY,
    get_connector_class,
    list_types,
    register,
)


class FakeConnector:
    capabilities = ConnectorCapabilities(
        incremental_cursor=True,
        stable_external_id=True,
        delete_events=True,
        folders=False,
        source_metadata=True,
        authentication=False,
    )

    def __init__(self) -> None:
        self.closed = False

    async def test_connection(self) -> dict[str, Any]:
        return {"ok": True}

    async def discover(self, *, cursor: dict[str, Any] | None = None) -> DiscoveryPage:
        return DiscoveryPage(
            objects=[
                SourceDescriptor(
                    external_object_id="obj-1",
                    name="readme.md",
                    path="/readme.md",
                    canonical_uri="file:///readme.md",
                )
            ],
            next_cursor=None,
            has_more=False,
        )

    async def fetch(self, descriptor: SourceDescriptor) -> FetchedSource:
        return FetchedSource(
            file_name=descriptor.name,
            mime_type="text/markdown",
            stream=b"hello",
            size=5,
            sha256="abc",
        )

    async def close(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_fake_connector_satisfies_protocol():
    connector = FakeConnector()
    assert isinstance(connector, KnowledgeSourceConnector)

    assert await connector.test_connection() == {"ok": True}
    page = await connector.discover()
    assert len(page.objects) == 1
    assert page.objects[0].external_object_id == "obj-1"

    fetched = await connector.fetch(page.objects[0])
    assert fetched.file_name == "readme.md"
    assert fetched.size == 5

    await connector.close()
    assert connector.closed is True


def test_registry_register_and_list():
    previous = CONNECTOR_REGISTRY.get("fake_test")
    try:
        register("fake_test", FakeConnector)
        assert "fake_test" in list_types()
        assert get_connector_class("fake_test") is FakeConnector
    finally:
        if previous is None:
            CONNECTOR_REGISTRY.pop("fake_test", None)
        else:
            CONNECTOR_REGISTRY["fake_test"] = previous


def test_registry_has_placeholder_types():
    types = list_types()
    assert "filesystem" in types
    assert "http_manifest" in types
    assert "s3_compatible" in types
