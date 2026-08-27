"""Runtime capability probe tests."""

from unittest.mock import AsyncMock

import pytest

from app.runtime.capabilities import probe_index_capabilities, probe_runtime


@pytest.mark.asyncio
async def test_probe_index_capabilities_unreachable():
    caps = await probe_index_capabilities(
        AsyncMock(),
        reachable=False,
        runtime_version=None,
    )
    assert caps["supports_chunk"]["build_supported"] is False
    assert caps["supports_chunk"]["reason"] == "ragflow_unreachable"


@pytest.mark.asyncio
async def test_probe_index_capabilities_reachable_validated():
    caps = await probe_index_capabilities(
        AsyncMock(),
        reachable=True,
        runtime_version="0.17.0",
    )
    assert caps["supports_chunk"]["build_supported"] is True
    assert caps["supports_chunk"]["retrieval_supported"] is True
    assert caps["supports_graph"]["build_supported"] is True
    assert caps["supports_graph"]["retrieval_supported"] is False


@pytest.mark.asyncio
async def test_probe_runtime_orchestrates_client():
    client = AsyncMock()
    client.system_health = AsyncMock(return_value=True)
    client.get_system_version = AsyncMock(return_value="0.24.0")
    reachable, version, caps = await probe_runtime(client)
    assert reachable is True
    assert version == "0.24.0"
    assert caps["supports_chunk"]["validated"] is True
