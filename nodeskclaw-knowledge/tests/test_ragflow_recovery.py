"""RAGFlow upload unknown outcome and recovery tests."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.integrations.ragflow.client import RagflowClient
from app.integrations.ragflow.exceptions import RagflowUploadUnknownError
from app.integrations.ragflow.models import RagflowDocument
from app.integrations.ragflow.upload_token import build_upload_token, deterministic_upload_filename
from app.services.retrieval_merge_service import _retrieve_slice
from app.services.retrieval_planner import RetrievalSlice, build_metadata_condition, build_retrieval_plan
from app.models.enums import AccessPlanKind, RetrievalSliceKind
from app.services.permission_service import AccessPlan


def test_deterministic_upload_token_and_filename():
    token = build_upload_token(source_file_id="sf1", file_version_id="v1")
    assert token == "nk_sf1_v1"
    name = deterministic_upload_filename(
        source_file_id="sf1",
        file_version_id="v1",
        original_name="报告.pdf",
    )
    assert name.startswith("nk_sf1_v1")
    assert name.endswith(".pdf")


@pytest.mark.asyncio
async def test_upload_timeout_raises_upload_unknown():
    client = RagflowClient(base_url="http://ragflow.example.com", api_key="k", upload_timeout=0.01)
    mock_http = AsyncMock()
    mock_http.base_url = "http://ragflow.example.com"
    mock_http.request = AsyncMock(side_effect=httpx.ReadTimeout("timed out"))
    client._http_client = mock_http
    client._owns_client = False

    with pytest.raises(RagflowUploadUnknownError) as exc:
        await client.upload_document("ds1", b"hello", "nk_sf1_v1.txt", upload_token="nk_sf1_v1")
    assert exc.value.upload_token == "nk_sf1_v1"
    assert mock_http.request.await_count == 1


@pytest.mark.asyncio
async def test_recover_uploaded_document_by_token():
    client = RagflowClient(base_url="http://ragflow.example.com", api_key="k")
    token = "nk_sf1_v1"
    docs = [
        RagflowDocument(id="d1", name=f"{token}.txt"),
        RagflowDocument(id="d2", name="other.txt"),
    ]
    client.list_documents = AsyncMock(return_value=docs)
    recovered = await client.recover_uploaded_document("ds1", token)
    assert recovered == "d1"


@pytest.mark.asyncio
async def test_recover_returns_none_when_missing():
    client = RagflowClient(base_url="http://ragflow.example.com", api_key="k")
    client.list_documents = AsyncMock(return_value=[RagflowDocument(id="d2", name="other.txt")])
    assert await client.recover_uploaded_document("ds1", "nk_missing") is None


@pytest.mark.asyncio
async def test_ingest_facade_recovers_without_reupload():
    from app.services import ingestion_facade
    from app.models.enums import IngestionJobStatus

    db = AsyncMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

    kb = MagicMock(id="kb1", org_id="o1", ragflow_dataset_id="ds1", status="active", metadata_schema={}, deleted_at=None)
    actor = ingestion_facade.KnowledgeActor(actor_type="member", actor_id="m1", org_id="o1", member_id="m1")

    ragflow = AsyncMock()
    ragflow.upload_document = AsyncMock(
        side_effect=RagflowUploadUnknownError("timeout", upload_token="token")
    )
    ragflow.recover_uploaded_document = AsyncMock(return_value="doc-recovered")
    ragflow.update_document_metadata = AsyncMock()
    ragflow.parse_documents = AsyncMock()

    created = []

    def _add(obj):
        created.append(obj)
        if getattr(obj, "id", None) is None:
            obj.id = f"id-{len(created)}"

    db.add.side_effect = _add

    with patch("app.services.ingestion_facade.validate_metadata_values", return_value={}), patch(
        "app.services.ingestion_facade.next_version_no", new=AsyncMock(return_value=1)
    ), patch("app.services.ingestion_facade.build_meta_fields", return_value={"nk_source_file_id": "sf"}), patch(
        "app.services.ingestion_facade.runtime_binding_service.require_dataset_id",
        new=AsyncMock(return_value="ds1"),
    ):
        sf, version, job = await ingestion_facade.ingest_core(
            db,
            ragflow,
            actor=actor,
            kb=kb,
            file_name="a.txt",
            mime_type="text/plain",
            content=b"hello",
            owner_member_id="m1",
        )

    ragflow.upload_document.assert_awaited_once()
    ragflow.recover_uploaded_document.assert_awaited_once()
    assert version.ragflow_document_id == "doc-recovered"
    assert job.status == IngestionJobStatus.parse_dispatched.value
    # Must not blind re-POST
    assert ragflow.upload_document.await_count == 1


def test_metadata_condition_builder():
    cond = build_metadata_condition({"dept": ["ops"], "biz_env": ["prod"]})
    assert cond["logic"] == "and"
    assert len(cond["conditions"]) == 2


def test_pushdown_disabled_omits_condition(monkeypatch):
    monkeypatch.setattr("app.services.retrieval_planner.settings.RAGFLOW_METADATA_PUSHDOWN_ENABLED", False)
    plan_access = AccessPlan(
        kind=AccessPlanKind.full_access,
        dataset_ids=["ds1"],
        document_ids=[],
        source_file_ids=["sf1"],
        knowledge_base_ids=["kb1"],
        full_dataset_ids=["ds1"],
        partial_slices=[],
    )
    kb = MagicMock(id="kb1", ragflow_dataset_id="ds1")
    item = MagicMock(knowledge_base_id="kb1", weight=1.0)
    plan = build_retrieval_plan(
        plan_access,
        [kb],
        [item],
        metadata_condition={"logic": "and", "conditions": []},
        dataset_id_by_kb_id={"kb1": "ds1"},
    )
    assert plan.metadata_pushdown is False
    assert plan.slices[0].metadata_condition is None


@pytest.mark.asyncio
async def test_pushdown_fallback_retries_without_condition():
    slice_ = RetrievalSlice(
        kind=RetrievalSliceKind.filtered_documents,
        dataset_id="ds1",
        document_ids=["d1"],
        metadata_condition={"logic": "and", "conditions": [{"name": "biz_x", "comparison_operator": "is", "value": "1"}]},
    )
    ragflow = AsyncMock()
    from app.integrations.ragflow.models import RagflowChunk, RagflowRetrievalResult

    ragflow.retrieve = AsyncMock(
        side_effect=[
            RuntimeError("metadata_condition unsupported"),
            RagflowRetrievalResult(chunks=[RagflowChunk(id="c1", content="ok", document_id="d1")], total=1),
        ]
    )
    result, chunks = await _retrieve_slice(
        ragflow,
        slice_,
        query="q",
        top_k=10,
        similarity_threshold=0.2,
        vector_similarity_weight=0.7,
        keyword=False,
        highlight=False,
        rerank_id=None,
        cross_languages=None,
        semaphore=__import__("asyncio").Semaphore(1),
    )
    assert result.status == "success"
    assert len(chunks) == 1
    assert ragflow.retrieve.await_count == 2
    assert ragflow.retrieve.await_args_list[1].kwargs.get("metadata_condition") is None
