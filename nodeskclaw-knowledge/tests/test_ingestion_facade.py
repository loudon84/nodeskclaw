"""Ingestion facade unit tests (mocked DB / RAGFlow)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import ConflictError, ForbiddenError
from app.models.enums import KnowledgeActorType, SourceKind, SourceSyncState
from app.schemas.principal import KnowledgePrincipal
from app.services.ingestion_facade import (
    KnowledgeActor,
    actor_from_connector,
    actor_from_member,
    authorize_user_upload,
)
from app.services.metadata_service import build_meta_fields


def _member() -> KnowledgePrincipal:
    return KnowledgePrincipal(
        user_id="u1",
        member_id="m1",
        org_id="o1",
        member_role="operator",
    )


def test_actor_from_member_and_connector():
    member = _member()
    ma = actor_from_member(member)
    assert ma.actor_type == KnowledgeActorType.member.value
    assert ma.actor_id == "m1"
    assert ma.member_id == "m1"

    ca = actor_from_connector(connector_id="c1", org_id="o1")
    assert ca.actor_type == KnowledgeActorType.connector.value
    assert ca.actor_id == "c1"
    assert ca.member_id is None


def test_build_meta_fields_includes_provenance():
    fields = build_meta_fields(
        source_file_id="sf1",
        file_version_id="v1",
        knowledge_base_id="kb1",
        org_id="o1",
        metadata={"dept": "finance"},
        metadata_revision=2,
        source_kind=SourceKind.connector.value,
        connector_id="c1",
        external_object_id="ext-1",
        source_revision="r9",
    )
    assert fields["nk_source_kind"] == "connector"
    assert fields["nk_connector_id"] == "c1"
    assert fields["nk_external_object_id"] == "ext-1"
    assert fields["nk_source_revision"] == "r9"
    assert fields["biz_dept"] == "finance"
    assert fields["nk_metadata_revision"] == "2"


@pytest.mark.asyncio
async def test_authorize_user_upload_requires_permission():
    db = AsyncMock()
    member = _member()
    kb = MagicMock()
    kb.id = "kb1"
    kb.ragflow_dataset_id = "ds1"
    kb.status = "active"

    with (
        patch("app.services.ingestion_facade.knowledge_base_service.get_knowledge_base", AsyncMock(return_value=kb)),
        patch(
            "app.services.ingestion_facade.runtime_binding_service.get_dataset_id",
            AsyncMock(return_value="ds1"),
        ),
        patch("app.services.ingestion_facade.has_kb_permission", AsyncMock(return_value=False)),
    ):
        with pytest.raises(ForbiddenError):
            await authorize_user_upload(db, member, "kb1")


@pytest.mark.asyncio
async def test_ingest_from_member_rejects_connector_managed_version():
    from app.services.ingestion_facade import ingest_from_member

    db = AsyncMock()
    member = _member()
    ragflow = AsyncMock()
    kb = MagicMock()
    kb.id = "kb1"
    kb.org_id = "o1"
    kb.ragflow_dataset_id = "ds1"
    kb.status = "active"
    kb.metadata_schema = None

    sf = MagicMock()
    sf.knowledge_base_id = "kb1"
    sf.source_kind = SourceKind.connector.value
    sf.connector_id = "c1"

    with (
        patch("app.services.ingestion_facade.authorize_user_upload", AsyncMock(return_value=kb)),
        patch("app.services.ingestion_facade.source_file_service.get_source_file", AsyncMock(return_value=sf)),
    ):
        with pytest.raises(ConflictError) as exc:
            await ingest_from_member(
                db,
                member,
                ragflow,
                knowledge_base_id="kb1",
                file_name="a.pdf",
                mime_type="application/pdf",
                content=b"abc",
                source_file_id="sf1",
            )
        assert exc.value.message_key == "errors.knowledge.source_managed_by_connector"


@pytest.mark.asyncio
async def test_ingest_from_connector_sets_actor_and_provenance():
    from app.services.ingestion_facade import ingest_from_connector

    db = AsyncMock()
    db.get = AsyncMock(return_value=None)
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.execute = AsyncMock()

    empty_result = MagicMock()
    empty_result.scalar_one_or_none.return_value = None
    db.execute.return_value = empty_result

    ragflow = AsyncMock()
    ragflow.upload_document = AsyncMock(return_value="doc-1")
    ragflow.update_document_metadata = AsyncMock()
    ragflow.parse_documents = AsyncMock()

    kb = MagicMock()
    kb.id = "kb1"
    kb.org_id = "o1"
    kb.ragflow_dataset_id = "ds1"
    kb.status = "active"
    kb.metadata_schema = None

    actor = KnowledgeActor(
        actor_type=KnowledgeActorType.connector.value,
        actor_id="c1",
        org_id="o1",
    )

    created = {}

    def capture_add(obj):
        created.setdefault(type(obj).__name__, []).append(obj)

    db.add.side_effect = capture_add

    with patch("app.services.ingestion_facade.next_version_no", AsyncMock(return_value=1)), patch(
        "app.services.ingestion_facade.runtime_binding_service.require_dataset_id",
        AsyncMock(return_value="ds1"),
    ), patch(
        "app.services.ingestion_facade.runtime_binding_service.get_dataset_id",
        AsyncMock(return_value="ds1"),
    ):
        sf, version, job = await ingest_from_connector(
            db,
            ragflow,
            actor=actor,
            kb=kb,
            file_name="erp.pdf",
            mime_type="application/pdf",
            content=b"hello",
            connector_id="c1",
            external_object_id="ERP-1",
            source_uri="https://example.com/erp-1",
            source_path="/erp/erp-1.pdf",
            source_revision="rev-1",
            source_etag="etag-1",
            source_metadata={"department": "sales"},
            owner_member_id="owner1",
        )

    assert sf.source_kind == SourceKind.connector.value
    assert sf.connector_id == "c1"
    assert sf.external_object_id == "ERP-1"
    assert sf.sync_state == SourceSyncState.in_sync.value
    assert version.created_by_actor_type == KnowledgeActorType.connector.value
    assert version.created_by_actor_id == "c1"
    assert version.uploaded_by_member_id is None
    assert version.origin_connector_id == "c1"
    assert job.created_by_member_id == "owner1"
    ragflow.upload_document.assert_awaited()
    meta_call = ragflow.update_document_metadata.await_args
    meta = meta_call.args[2]
    assert meta["nk_source_kind"] == "connector"
    assert meta["nk_connector_id"] == "c1"
    assert meta["nk_external_object_id"] == "ERP-1"


@pytest.mark.asyncio
async def test_detach_source_file():
    from app.services.ingestion_facade import detach_source_file

    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    sf = MagicMock()
    sf.id = "sf1"
    sf.source_kind = SourceKind.connector.value
    sf.connector_id = "c1"
    sf.external_object_id = "ext-1"
    sf.knowledge_base_id = "kb1"

    obj = MagicMock()
    obj.source_file_id = "sf1"
    obj.state = "active"

    result = MagicMock()
    result.scalars.return_value.all.return_value = [obj]
    db.execute = AsyncMock(return_value=result)

    with (
        patch("app.services.ingestion_facade.source_file_service.get_source_file", AsyncMock(return_value=sf)),
        patch("app.services.ingestion_facade.has_kb_permission", AsyncMock(return_value=True)),
    ):
        out = await detach_source_file(db, _member(), "sf1")

    assert out.source_kind == SourceKind.manual.value
    assert out.connector_id is None
    assert out.external_object_id is None
    assert out.sync_state == SourceSyncState.detached.value
    assert obj.source_file_id is None
    assert obj.state == "detached"
