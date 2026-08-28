"""Knowledge artifact SPI and outline provider tests."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.knowledge_artifacts.base import ArtifactBuildContext
from app.knowledge_artifacts.outline import OutlineArtifactProvider, _normalize_node
from app.knowledge_artifacts.registry import ensure_default_providers, get_provider, list_providers
from app.runtime.ragflow import RagflowRuntimeAdapter


def test_registry_registers_outline_graph_and_table_providers():
    ensure_default_providers()
    types = {provider.artifact_type for provider in list_providers()}
    assert "outline" in types
    assert "graph" in types
    assert "table" in types
    assert get_provider("outline") is not None
    assert get_provider("table") is not None


def test_outline_node_without_source_ref_not_citable():
    node = _normalize_node({"id": "n1", "title": "Chapter 1", "level": 1})
    assert node["citable"] is False
    assert node["source_refs"] == []


def test_outline_node_with_source_ref_is_citable():
    node = _normalize_node(
        {
            "id": "n1",
            "title": "Chapter 1",
            "source_refs": [
                {"source_file_id": "sf1", "file_version_id": "v1", "page_start": 1},
            ],
        }
    )
    assert node["citable"] is True
    assert len(node["source_refs"]) == 1


@pytest.mark.asyncio
async def test_outline_provider_retrieve_respects_citation(monkeypatch):
    provider = OutlineArtifactProvider()

    class FakeAdapter:
        async def get_artifact_structure(self, _dataset_id, **kwargs):
            return {
                "title": "Policy",
                "nodes": [
                    {
                        "id": "n1",
                        "title": "付款流程",
                        "source_refs": [
                            {"source_file_id": "sf1", "file_version_id": "v1"},
                        ],
                    },
                    {"id": "n2", "title": "附录", "source_refs": []},
                ],
            }

        async def get_artifact_topics(self, *_args, **_kwargs):
            return {}

        async def get_artifact_alteration(self, *_args, **_kwargs):
            return {}

    context = ArtifactBuildContext(
        org_id="o1",
        knowledge_base_id="kb1",
        dataset_id="ds1",
        adapter=FakeAdapter(),
        manifest_hash="abc",
        manifest_summary={"item_count": 1},
    )
    hits = await provider.retrieve("付款", context)
    assert len(hits) == 1
    assert hits[0].citable is True
    assert hits[0].source_refs[0].source_file_id == "sf1"


@pytest.mark.asyncio
async def test_ragflow_adapter_artifact_facade_delegates_to_client():
    client = SimpleNamespace(
        list_dataset_artifacts=AsyncMock(return_value=[{"type": "outline"}]),
        get_dataset_artifact_structure=AsyncMock(return_value={"nodes": []}),
        get_dataset_artifact_topics=AsyncMock(return_value={}),
        get_dataset_artifact_graph=AsyncMock(return_value={"entities": []}),
        get_dataset_artifact_alteration=AsyncMock(return_value={"changed": []}),
        aclose=AsyncMock(),
    )
    adapter = RagflowRuntimeAdapter(client=client)
    artifacts = await adapter.list_artifacts("ds1")
    assert artifacts[0]["type"] == "outline"
    await adapter.get_artifact_structure("ds1")
    await adapter.get_artifact_topics("ds1")
    await adapter.get_artifact_graph("ds1")
    await adapter.get_artifact_alteration("ds1")
    client.list_dataset_artifacts.assert_awaited_once()
    client.get_dataset_artifact_structure.assert_awaited_once()


@pytest.mark.asyncio
async def test_table_provider_retrieve_includes_row_lineage():
    from app.knowledge_artifacts.table import TableArtifactProvider

    provider = TableArtifactProvider()

    class FakeAdapter:
        async def get_artifact_alteration(self, _dataset_id, **kwargs):
            return {
                "rows": [
                    {
                        "id": "r1",
                        "header": "付款金额",
                        "cells": {"amount": "1000"},
                        "source_file_id": "sf1",
                        "file_version_id": "v1",
                        "page": 2,
                    }
                ]
            }

    context = ArtifactBuildContext(
        org_id="o1",
        knowledge_base_id="kb1",
        dataset_id="ds1",
        adapter=FakeAdapter(),
        manifest_hash="abc",
        manifest_summary={"item_count": 1},
    )
    hits = await provider.retrieve("付款", context)
    assert len(hits) == 1
    assert hits[0].citable is True
    assert hits[0].provider_payload["row_id"] == "r1"
    assert hits[0].source_refs[0].source_file_id == "sf1"
    assert hits[0].source_refs[0].file_version_id == "v1"


def test_table_acl_filter_drops_unauthorized_rows():
    from app.knowledge_artifacts.base import ArtifactEvidenceCandidate, SourceRef
    from app.knowledge_artifacts.table import filter_table_candidates_by_acl

    candidates = [
        ArtifactEvidenceCandidate(
            artifact_type="table",
            title="row1",
            content="{}",
            source_refs=[SourceRef(source_file_id="sf1", file_version_id="v1")],
            citable=True,
            provider_payload={"row_id": "r1"},
        ),
        ArtifactEvidenceCandidate(
            artifact_type="table",
            title="row2",
            content="{}",
            source_refs=[SourceRef(source_file_id="sf2", file_version_id="v1")],
            citable=True,
            provider_payload={"row_id": "r2"},
        ),
    ]
    filtered = filter_table_candidates_by_acl(candidates, {"sf1"})
    assert len(filtered) == 1
    assert filtered[0].provider_payload["row_id"] == "r1"
