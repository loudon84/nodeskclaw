"""Runtime Adapter health and provision tests."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import settings
from app.runtime.ragflow import RagflowRuntimeAdapter


def _mock_probe_client(
    *,
    reachable: bool = True,
    version: str = "0.17.0",
    dataset_api: bool = True,
    chunk_retrieval: bool = True,
) -> AsyncMock:
    client = AsyncMock()
    client.system_health = AsyncMock(return_value=reachable)
    client.get_system_version = AsyncMock(return_value=version)
    client.list_datasets = AsyncMock(return_value=[SimpleNamespace(id="ds-probe")] if dataset_api else [])
    client.probe_retrieval_endpoint = AsyncMock(return_value=chunk_retrieval)
    client.probe_dataset_search = AsyncMock(return_value=dataset_api)
    client.probe_dataset_graph = AsyncMock(return_value=False)
    client.probe_document_chunks = AsyncMock(return_value={"chunk_retrieval": chunk_retrieval, "question_fields_visible": True})
    client.probe_retrieval_features = AsyncMock(
        return_value={
            "kg_retrieval": {"transport": True, "supported": False, "operational": False, "artifact_present": False},
            "knowledge_compilation": {"transport": True, "supported": False, "operational": False, "artifact_present": False},
            "toc_enhance": {"transport": True, "supported": False, "operational": False, "artifact_present": False},
            "metadata_filter": {"transport": True, "supported": True, "operational": True, "artifact_present": False},
            "knn_top_k": {"transport": True, "supported": True, "operational": True, "artifact_present": False},
            "knn_num_candidates": {"transport": True, "supported": False, "operational": False, "artifact_present": False},
            "rerank_candidates_count": {"transport": True, "supported": False, "operational": False, "artifact_present": False},
        }
    )
    return client


@pytest.mark.asyncio
async def test_check_health_chunk_ok_when_reachable():
    client = _mock_probe_client()
    adapter = RagflowRuntimeAdapter(client=client)
    health = await adapter.check_health()
    assert health.reachable is True
    assert health.chunk_retrieval_ok is True
    assert health.capabilities["supports_chunk"]["build_supported"] is True


@pytest.mark.asyncio
async def test_probe_capabilities_persists_snapshot_on_adapter():
    client = _mock_probe_client()
    adapter = RagflowRuntimeAdapter(client=client)
    caps = await adapter.probe_capabilities()
    snapshot, version = adapter.get_probe_snapshot()
    assert snapshot == caps
    assert version == "0.17.0"
    assert caps["supports_chunk"]["build_supported"] is True


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
    client = _mock_probe_client()
    client.create_dataset = AsyncMock(return_value="ds-new")
    db = AsyncMock()
    kb = SimpleNamespace(id="kb1", ragflow_dataset_id=None, name="kb")
    create_idempotent = AsyncMock(return_value="ds-new")
    compile_desired = AsyncMock(return_value={"embedding_model": "bge-m3", "chunk_method": "naive", "parser_config": None})
    monkeypatch.setattr("app.services.runtime_binding_service.create_dataset_idempotent", create_idempotent)
    monkeypatch.setattr("app.services.runtime_binding_service.compile_and_persist_desired_config", compile_desired)
    probe = AsyncMock(
        return_value=SimpleNamespace(
            capabilities={"supports_chunk": {"build_supported": True, "retrieval_supported": True}},
            runtime_version="0.17.0",
            probe_error=None,
        )
    )
    upsert = AsyncMock(
        return_value=SimpleNamespace(
            resource_id="ds-new",
            status="ready",
            capabilities={"supports_chunk": {"build_supported": True, "retrieval_supported": True}},
            runtime_version="0.17.0",
        )
    )
    mirror = AsyncMock()
    monkeypatch.setattr("app.services.runtime_binding_service.probe_and_persist_binding_capabilities", probe)
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
    create_idempotent.assert_awaited_once()
    probe.assert_awaited_once()
    upsert.assert_awaited_once()
    assert upsert.await_args.kwargs.get("from_probe") is True
    mirror.assert_awaited_once()
