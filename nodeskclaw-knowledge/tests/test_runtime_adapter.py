"""Runtime Adapter health and provision tests."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import settings
from app.runtime.ragflow import RagflowRuntimeAdapter


@pytest.mark.asyncio
async def test_check_health_chunk_ok_when_reachable():
    client = AsyncMock()
    client.system_health = AsyncMock(return_value=True)
    adapter = RagflowRuntimeAdapter(client=client)
    health = await adapter.check_health()
    assert health.reachable is True
    assert health.chunk_retrieval_ok is True
    assert health.capabilities["supports_chunk"] is True


@pytest.mark.asyncio
async def test_check_health_not_ready_when_unreachable():
    client = AsyncMock()
    client.system_health = AsyncMock(side_effect=RuntimeError("down"))
    adapter = RagflowRuntimeAdapter(client=client)
    health = await adapter.check_health()
    assert health.reachable is False
    assert health.chunk_retrieval_ok is False
    assert "ragflow_unreachable" in health.degraded_reasons


@pytest.mark.asyncio
async def test_provision_binding_dual_writes(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_V2_RUNTIME_BINDING_ENABLED", True)
    client = AsyncMock()
    client.create_dataset = AsyncMock(return_value="ds-new")
    client.system_health = AsyncMock(return_value=True)
    db = AsyncMock()
    kb = SimpleNamespace(id="kb1", ragflow_dataset_id=None)
    upsert = AsyncMock(
        return_value=SimpleNamespace(
            resource_id="ds-new",
            status="ready",
            capabilities={"supports_chunk": True},
            runtime_version=None,
        )
    )
    mirror = AsyncMock()
    monkeypatch.setattr("app.services.runtime_binding_service.upsert_ragflow_dataset_binding", upsert)
    monkeypatch.setattr("app.services.runtime_binding_service.mirror_dataset_id_to_kb", mirror)
    adapter = RagflowRuntimeAdapter(client=client)
    result = await adapter.provision_binding(
        db,
        kb=kb,
        embedding_model="bge-m3",
        chunk_method="naive",
        parser_config=None,
        description=None,
        name="o1:kb",
        org_id="o1",
    )
    assert result.resource_id == "ds-new"
    upsert.assert_awaited_once()
    mirror.assert_awaited_once()
