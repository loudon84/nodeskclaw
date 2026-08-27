"""Runtime capability probe tests."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.integrations.ragflow.client import RagflowClient
from app.integrations.ragflow.exceptions import RagflowError
from app.runtime.capabilities import probe_index_capabilities, probe_runtime
from app.runtime.ragflow_contract import probe_compatibility_profile


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


@pytest.mark.asyncio
async def test_probe_retrieval_features_non_unsupported_error_not_supported():
    client = RagflowClient()
    client.retrieve = AsyncMock(side_effect=RagflowError("model_not_configured"))
    result = await client.probe_retrieval_features("ds-1")
    assert result["kg_retrieval"]["supported"] is False
    assert result["kg_retrieval"]["operational"] is False


@pytest.mark.asyncio
async def test_probe_retrieval_features_unsupported_param():
    client = RagflowClient()
    client.retrieve = AsyncMock(side_effect=RagflowError("unsupported parameter use_kg"))
    result = await client.probe_retrieval_features("ds-1")
    assert result["kg_retrieval"]["supported"] is False


@pytest.mark.asyncio
async def test_compatibility_profile_metadata_filter_from_probe_not_hardcoded():
    client = AsyncMock()
    client.system_health = AsyncMock(return_value=True)
    client.get_system_version = AsyncMock(return_value="0.24.0")
    client.list_datasets = AsyncMock(return_value=[MagicMock(id="ds-1")])
    client.probe_retrieval_endpoint = AsyncMock(return_value=True)
    client.probe_dataset_search = AsyncMock(return_value=True)
    client.probe_dataset_graph = AsyncMock(return_value=False)
    client.probe_document_chunks = AsyncMock(return_value={"chunk_retrieval": True})
    client.probe_retrieval_features = AsyncMock(
        return_value={
            "kg_retrieval": {"transport": True, "supported": False, "operational": False, "artifact_present": False},
            "toc_enhance": {"transport": True, "supported": False, "operational": False, "artifact_present": False},
            "metadata_filter": {"transport": True, "supported": False, "operational": False, "artifact_present": False},
            "knn_top_k": {"transport": True, "supported": True, "operational": True, "artifact_present": False},
            "knn_num_candidates": {"transport": True, "supported": False, "operational": False, "artifact_present": False},
            "rerank_candidates_count": {"transport": True, "supported": False, "operational": False, "artifact_present": False},
            "knowledge_compilation": {"transport": True, "supported": False, "operational": False, "artifact_present": False},
        }
    )
    profile = await probe_compatibility_profile(client, dataset_id="ds-1")
    assert profile.metadata_filter is False
