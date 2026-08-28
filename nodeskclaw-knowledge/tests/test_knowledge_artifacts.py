"""Knowledge artifact SPI and outline provider tests."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.knowledge_artifacts.base import ArtifactBuildContext, ArtifactBuildResult
from app.knowledge_artifacts.outline import OutlineArtifactProvider, _normalize_node
from app.knowledge_artifacts.registry import ensure_default_providers, get_provider, list_providers
from app.runtime.ragflow import RagflowRuntimeAdapter
from app.services import artifact_revision_service, build_executors, build_orchestrator


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
async def test_table_provider_retrieve_uses_document_chunks():
    from app.knowledge_artifacts.table import TableArtifactProvider

    provider = TableArtifactProvider()

    class FakeAdapter:
        async def iter_document_chunks(self, _dataset_id, _document_id, **kwargs):
            yield {
                "id": "chunk-table-1",
                "type": "html-table",
                "metadata": {
                    "type": "html-table",
                    "nk_source_file_id": "sf1",
                    "nk_file_version_id": "v1",
                    "table": {
                        "table_id": "t1",
                        "columns": [{"name": "amount", "type": "number"}],
                        "rows": [
                            {
                                "row_id": "r1",
                                "values": {"amount": "1000"},
                            }
                        ],
                    },
                },
            }

        async def get_artifact_alteration(self, *_args, **_kwargs):
            raise AssertionError("retrieve must not read alteration rows")

    context = ArtifactBuildContext(
        org_id="o1",
        knowledge_base_id="kb1",
        dataset_id="ds1",
        adapter=FakeAdapter(),
        manifest_hash="abc",
        manifest_summary={"item_count": 1},
        ragflow_document_id="doc1",
    )
    hits = await provider.retrieve("1000", context)
    assert len(hits) == 1
    assert hits[0].citable is True
    assert hits[0].provider_payload["row_id"] == "r1"
    assert hits[0].source_refs[0].source_file_id == "sf1"
    assert hits[0].source_refs[0].file_version_id == "v1"


@pytest.mark.asyncio
async def test_table_provider_build_reads_chunks_not_alteration():
    from app.knowledge_artifacts.table import TableArtifactProvider

    provider = TableArtifactProvider()
    alteration_called = {"value": False}

    class FakeAdapter:
        async def iter_document_chunks(self, _dataset_id, _document_id, **kwargs):
            yield {
                "id": "chunk-table-1",
                "metadata": {
                    "type": "table",
                    "nk_source_file_id": "sf1",
                    "nk_file_version_id": "v1",
                    "table": {
                        "columns": [{"name": "amount", "type": "number"}],
                        "rows": [{"row_id": "r1", "values": {"amount": "500"}}],
                    },
                },
            }

        async def get_artifact_alteration(self, *_args, **_kwargs):
            alteration_called["value"] = True
            return {"rows": [{"id": "legacy", "cells": {"amount": "999"}}]}

    context = ArtifactBuildContext(
        org_id="o1",
        knowledge_base_id="kb1",
        dataset_id="ds1",
        adapter=FakeAdapter(),
        manifest_hash="abc",
        manifest_summary={"item_count": 1},
        ragflow_document_id="doc1",
        source_file_id="sf1",
    )
    result = await provider.build(context)
    assert result.status == "succeeded"
    assert alteration_called["value"] is False


@pytest.mark.asyncio
async def test_table_provider_retrieve_with_chunks_when_alteration_empty():
    from app.knowledge_artifacts.table import TableArtifactProvider

    provider = TableArtifactProvider()

    class FakeAdapter:
        async def iter_document_chunks(self, _dataset_id, _document_id, **kwargs):
            yield {
                "id": "chunk-table-1",
                "metadata": {
                    "type": "table",
                    "nk_source_file_id": "sf1",
                    "nk_file_version_id": "v1",
                    "table": {
                        "columns": [{"name": "customer", "type": "string"}],
                        "rows": [{"row_id": "r1", "values": {"customer": "付款流程"}}],
                    },
                },
            }

        async def get_artifact_alteration(self, *_args, **_kwargs):
            return {"rows": []}

    context = ArtifactBuildContext(
        org_id="o1",
        knowledge_base_id="kb1",
        dataset_id="ds1",
        adapter=FakeAdapter(),
        manifest_hash="abc",
        manifest_summary={"item_count": 1},
        ragflow_document_id="doc1",
    )
    hits = await provider.retrieve("付款", context)
    assert len(hits) == 1


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


def test_artifact_security_filter_source_refs_filtered_access():
    from app.models.enums import AccessPlanKind
    from app.services.artifact_security_service import filter_source_refs
    from app.services.permission_service import AccessPlan

    plan = AccessPlan(
        kind=AccessPlanKind.filtered_access,
        source_file_ids=["sf1"],
    )
    refs = [
        {"source_file_id": "sf1", "file_version_id": "v1"},
        {"source_file_id": "sf2", "file_version_id": "v1"},
    ]
    filtered = filter_source_refs(plan, refs)
    assert len(filtered) == 1
    assert filtered[0]["source_file_id"] == "sf1"


def test_artifact_security_filter_table_content_drops_unauthorized_rows():
    from app.models.enums import AccessPlanKind
    from app.services.artifact_security_service import filter_artifact_content
    from app.services.permission_service import AccessPlan

    plan = AccessPlan(kind=AccessPlanKind.filtered_access, source_file_ids=["sf1"])
    content = {
        "table_id": "t1",
        "columns": [{"name": "amount", "type": "number"}],
        "rows": [
            {"row_id": "r1", "values": {"amount": "1"}, "source_refs": [{"source_file_id": "sf1", "file_version_id": "v1"}]},
            {"row_id": "r2", "values": {"amount": "2"}, "source_refs": [{"source_file_id": "sf2", "file_version_id": "v1"}]},
        ],
    }
    filtered = filter_artifact_content(content, plan, artifact_type="table")
    assert len(filtered["rows"]) == 1
    assert filtered["rows"][0]["row_id"] == "r1"


@pytest.mark.asyncio
async def test_authorize_artifact_read_denies_without_kb_access(monkeypatch):
    from app.core.config import settings
    from app.core.exceptions import NotFoundError
    from app.models.enums import AccessPlanKind
    from app.services import artifact_security_service
    from app.services.permission_service import AccessPlan

    monkeypatch.setattr(settings, "KNOWLEDGE_V24_ARTIFACT_ACL_ENABLED", True)

    class FakeDB:
        async def get(self, _model, _id):
            return None

    artifact = SimpleNamespace(
        org_id="o1",
        scope="knowledge_base",
        source_file_id=None,
        file_version_id=None,
    )
    kb = SimpleNamespace(id="kb1", org_id="o1", deleted_at=None, status="active")

    async def _no_access(*_args, **_kwargs):
        return AccessPlan(kind=AccessPlanKind.no_access)

    monkeypatch.setattr(
        "app.services.artifact_security_service.build_access_plan",
        _no_access,
    )
    with pytest.raises(NotFoundError):
        await artifact_security_service.authorize_artifact_read(
            FakeDB(),
            SimpleNamespace(org_id="o1", is_super_admin=False, member_id="m1"),
            artifact,
            kb,
        )


@pytest.mark.asyncio
async def test_file_scoped_outline_identities_coexist():
    db = MagicMock()
    db.scalar = AsyncMock(return_value=None)
    db.add = MagicMock()
    db.flush = AsyncMock()

    first = await artifact_revision_service.get_or_create_identity(
        db,
        org_id="o1",
        knowledge_base_id="kb1",
        artifact_type="outline",
        provider="ragflow_native",
        scope="file",
        source_file_id="sf1",
        file_version_id="v1",
    )
    db.scalar = AsyncMock(return_value=None)
    second = await artifact_revision_service.get_or_create_identity(
        db,
        org_id="o1",
        knowledge_base_id="kb1",
        artifact_type="outline",
        provider="ragflow_native",
        scope="file",
        source_file_id="sf2",
        file_version_id="v2",
    )
    assert first.source_file_id == "sf1"
    assert second.source_file_id == "sf2"
    assert first is not second
    assert db.add.call_count == 2


@pytest.mark.asyncio
async def test_publish_revision_keeps_previous_revision_row():
    artifact = SimpleNamespace(
        id="art-1",
        org_id="o1",
        knowledge_base_id="kb1",
        artifact_type="outline",
        provider="ragflow_native",
        scope="file",
        source_file_id="sf1",
        file_version_id="v1",
        status="building",
        version=0,
        active_revision_id=None,
        artifact_uri=None,
        input_manifest_hash=None,
        validation_payload=None,
        coverage_payload=None,
        provider_payload=None,
        lineage_payload=None,
        last_built_at=None,
        last_validated_at=None,
        last_error=None,
    )
    old_revision = SimpleNamespace(id="rev-1", status="ready")
    db = MagicMock()
    db.scalar = AsyncMock(side_effect=[1, None])
    db.scalars = AsyncMock(return_value=MagicMock(all=MagicMock(return_value=[old_revision])))
    db.add = MagicMock()
    db.flush = AsyncMock()

    build_result = ArtifactBuildResult(
        status="succeeded",
        artifact_uri="artifacts/o1/kb1/outline/sf1/hash2.json",
        validation_payload={"ready": True},
        coverage_payload={"node_count": 2},
    )
    revision = await artifact_revision_service.publish_revision(
        db,
        artifact=artifact,
        build_result=build_result,
        input_manifest_hash="hash2",
        file_version_id="v2",
    )

    assert old_revision.status == "stale"
    assert revision.revision_number == 2
    assert revision.status == "ready"
    assert artifact.active_revision_id == revision.id
    assert artifact.version == 2
    assert db.add.call_count == 1


@pytest.mark.asyncio
async def test_enqueue_artifact_build_does_not_call_provider_build(monkeypatch):
    from app.api.v2 import artifacts as artifacts_api
    from app.core.config import settings

    monkeypatch.setattr(settings, "KNOWLEDGE_API_V2_ENABLED", True)
    monkeypatch.setattr(settings, "KNOWLEDGE_V23_ARTIFACTS_ENABLED", True)
    monkeypatch.setattr(settings, "KNOWLEDGE_V23_OUTLINE_ENABLED", True)

    kb = SimpleNamespace(id="kb1", org_id="o1", deleted_at=None)
    member = SimpleNamespace(org_id="o1", member_id="m1")
    artifact_row = SimpleNamespace(
        id="art-1",
        status="building",
        source_file_id="sf1",
        file_version_id="v1",
    )
    job = SimpleNamespace(id="job-1", stage_results=None)

    db = AsyncMock()
    db.get = AsyncMock(return_value=kb)
    db.flush = AsyncMock()

    provider = SimpleNamespace(
        capabilities=MagicMock(
            return_value=SimpleNamespace(provider="ragflow_native", scope="file")
        ),
        build=AsyncMock(),
    )
    monkeypatch.setattr(artifacts_api, "ensure_default_providers", lambda: None)
    monkeypatch.setattr(artifacts_api, "get_provider", lambda _type: provider)
    monkeypatch.setattr(
        artifacts_api.build_input_manifest_service,
        "compute_manifest",
        AsyncMock(return_value=("hash1", [], {"item_count": 0})),
    )
    monkeypatch.setattr(
        artifacts_api.artifact_revision_service,
        "get_or_create_identity",
        AsyncMock(return_value=artifact_row),
    )
    enqueue = AsyncMock(return_value=job)
    monkeypatch.setattr(artifacts_api.build_orchestrator, "enqueue_build", enqueue)

    response = await artifacts_api.enqueue_artifact_build(
        "kb1",
        {"artifact_type": "outline", "source_file_id": "sf1", "file_version_id": "v1"},
        member=member,
        db=db,
    )

    provider.build.assert_not_called()
    enqueue.assert_awaited_once()
    kwargs = enqueue.await_args.kwargs
    assert kwargs["target_kind"] == "artifact"
    assert kwargs["target_key"] == "outline"
    assert response.data["build_job_id"] == "job-1"
    assert response.data["status"] == "building"
    assert job.stage_results["input"]["artifact_id"] == "art-1"


@pytest.mark.asyncio
async def test_process_build_job_runs_artifact_executor(monkeypatch):
    from app.models.enums import BuildJobStatus

    db = AsyncMock()
    kb = SimpleNamespace(id="kb1", org_id="o1", deleted_at=None)
    db.get = AsyncMock(return_value=kb)
    job = SimpleNamespace(
        id="job-1",
        org_id="o1",
        knowledge_base_id="kb1",
        index_type="outline:file:sf1",
        target_kind="artifact",
        target_key="outline",
        knowledge_model_revision_id=None,
        attempt_count=1,
        max_attempts=5,
        stage_results={"input": {"artifact_id": "art-1", "source_file_id": "sf1"}},
        input_manifest_hash="hash1",
        status=BuildJobStatus.running.value,
        progress=0,
        error_code=None,
        error_message=None,
        finished_at=None,
        next_run_at=None,
    )
    monkeypatch.setattr(
        build_orchestrator,
        "_resolve_active_model_revision_id",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        build_executors,
        "execute_artifact_stage",
        AsyncMock(
            return_value=build_executors.StageResult(
                status="succeeded",
                output={"artifact_id": "art-1", "revision_number": 1},
            )
        ),
    )

    await build_orchestrator.process_build_job(db, job)
    assert job.status == BuildJobStatus.completed.value
    assert job.stage_results["status"] == "succeeded"
    build_executors.execute_artifact_stage.assert_awaited_once()
