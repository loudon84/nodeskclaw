"""Runtime capability probe tests."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.integrations.ragflow.client import RagflowClient
from app.integrations.ragflow.exceptions import RagflowError
from app.runtime.capabilities import capabilities_from_profile, probe_index_capabilities, probe_runtime
from app.runtime.ragflow_contract import (
    CAPABILITY_UNAVAILABLE,
    CAPABILITY_UNKNOWN,
    CAPABILITY_UNSUPPORTED,
    RagflowCompatibilityProfile,
    probe_compatibility_profile,
)


def test_unreachable_capability_is_unavailable_not_false_bool():
    caps = capabilities_from_profile(RagflowCompatibilityProfile(reachable=False, runtime_version=None))
    chunk = caps["supports_chunk"]
    assert chunk["status"] == CAPABILITY_UNAVAILABLE
    assert chunk["build_supported"] is True
    assert chunk["retrieval_supported"] is True
    assert isinstance(chunk["build_supported"], bool)
    assert chunk["build_supported"] is not False


def test_no_fixture_capability_is_unknown_and_bool_not_false():
    profile = RagflowCompatibilityProfile(reachable=True, runtime_version="v0.27.0")
    caps = capabilities_from_profile(profile)
    chunk = caps["supports_chunk"]
    graph = caps["supports_graph"]
    assert chunk["status"] == CAPABILITY_UNKNOWN
    assert graph["status"] == CAPABILITY_UNKNOWN
    assert chunk["build_supported"] is True
    assert graph["retrieval_supported"] is True
    assert chunk["build_supported"] is not False
    assert isinstance(chunk["build_supported"], bool)
    assert chunk["status"] != chunk["build_supported"]


def test_contract_reject_projects_false_and_keeps_bool():
    caps = capabilities_from_profile(RagflowCompatibilityProfile(reachable=True, runtime_version="v0.27.0"))
    table = caps["supports_table"]
    assert table["status"] == CAPABILITY_UNSUPPORTED
    assert table["build_supported"] is False
    assert isinstance(table["build_supported"], bool)


def test_version_string_does_not_rewrite_capability():
    old = capabilities_from_profile(RagflowCompatibilityProfile(reachable=True, runtime_version="0.17.0"))
    new = capabilities_from_profile(RagflowCompatibilityProfile(reachable=True, runtime_version="v0.27.0"))
    assert old["supports_chunk"]["status"] == new["supports_chunk"]["status"] == CAPABILITY_UNKNOWN
    assert old["supports_graph"]["status"] == new["supports_graph"]["status"]


@pytest.mark.asyncio
async def test_probe_index_capabilities_unreachable():
    caps = await probe_index_capabilities(
        AsyncMock(),
        reachable=False,
        runtime_version=None,
    )
    assert caps["supports_chunk"]["status"] == CAPABILITY_UNAVAILABLE
    assert caps["supports_chunk"]["build_supported"] is True
    assert caps["supports_chunk"]["reason"] == "ragflow_unreachable"


@pytest.mark.asyncio
async def test_probe_index_capabilities_reachable_validated():
    profile = RagflowCompatibilityProfile(
        reachable=True,
        runtime_version="0.17.0",
        dataset_api=True,
        document_api=True,
        chunk_retrieval=True,
        dataset_graph=True,
        feature_status={
            "dataset_api": "supported",
            "document_api": "supported",
            "chunk_retrieval": "supported",
            "dataset_graph": "supported",
            "kg_retrieval": "unsupported",
        },
    )
    caps = await probe_index_capabilities(
        AsyncMock(),
        reachable=True,
        runtime_version="0.17.0",
        profile=profile,
    )
    assert caps["supports_chunk"]["build_supported"] is True
    assert caps["supports_chunk"]["retrieval_supported"] is True
    assert caps["supports_chunk"]["status"] == "supported"
    assert caps["supports_graph"]["build_supported"] is False
    assert caps["supports_graph"]["retrieval_supported"] is False
    assert caps["supports_graph"]["status"] == CAPABILITY_UNSUPPORTED


@pytest.mark.asyncio
async def test_probe_runtime_orchestrates_client():
    client = AsyncMock()
    client.system_health = AsyncMock(return_value=True)
    client.get_system_version = AsyncMock(return_value="0.24.0")
    reachable, version, caps = await probe_runtime(client)
    assert reachable is True
    assert version == "0.24.0"
    assert caps["supports_chunk"]["status"] in {CAPABILITY_UNKNOWN, "supported"}
    assert isinstance(caps["supports_chunk"]["build_supported"], bool)


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
    assert profile.fact("metadata_filter") == CAPABILITY_UNSUPPORTED
    assert profile.fact("kg_retrieval") == CAPABILITY_UNSUPPORTED
    assert profile.fact("knn_top_k") == "supported"
