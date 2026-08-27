"""Citation Resolve API: metadata + current ACL/file status."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import ForbiddenError, NotFoundError
from app.schemas.principal import KnowledgePrincipal
from app.services import citation_service


def _member(**kwargs) -> KnowledgePrincipal:
    base = dict(
        user_id="u1",
        member_id="m1",
        org_id="o1",
        name="Zhang",
        department="sales",
        member_role="member",
        is_active=True,
        is_super_admin=False,
    )
    base.update(kwargs)
    return KnowledgePrincipal(**base)


def _citation(**kwargs):
    data = dict(
        id="cit1",
        org_id="o1",
        issued_member_id="m1",
        message_id="msg1",
        knowledge_base_id="kb1",
        source_file_id="sf1",
        file_version_id="v1",
        ragflow_document_id="doc1",
        ragflow_chunk_id="chunk1",
        page=3,
        positions=[[1, 2, 3, 4]],
        score=0.91,
        quote="hello",
        evidence_type="chunk",
        content="hello",
        source_refs=[
            {
                "source_file_id": "sf1",
                "file_version_id": "v1",
                "knowledge_base_id": "kb1",
            }
        ],
        origin="chat",
        deleted_at=None,
    )
    data.update(kwargs)
    return SimpleNamespace(**data)


def _message(**kwargs):
    data = dict(id="msg1", session_id="sess1", deleted_at=None)
    data.update(kwargs)
    return SimpleNamespace(**data)


def _session(**kwargs):
    data = dict(
        id="sess1",
        org_id="o1",
        member_id="m1",
        knowledge_set_id="set1",
        deleted_at=None,
    )
    data.update(kwargs)
    return SimpleNamespace(**data)


def _sf(**kwargs):
    data = dict(
        id="sf1",
        org_id="o1",
        knowledge_base_id="kb1",
        owner_member_id="m1",
        status="active",
        archived_at=None,
        deleted_at=None,
        source_kind="connector",
        connector_id="conn1",
        source_path="/data/a.pdf",
        source_revision="rev-9",
        source_modified_at=datetime(2026, 8, 1, tzinfo=UTC),
        last_synced_at=datetime(2026, 8, 8, tzinfo=UTC),
        sync_state="in_sync",
    )
    data.update(kwargs)
    return SimpleNamespace(**data)


async def _db_get_side_effect(citation, message, session, source_file, connector=None):
    mapping = {
        ("ChatCitation", citation.id if citation else None): citation,
        ("ChatMessage", message.id if message else None): message,
        ("ChatSession", session.id if session else None): session,
        ("SourceFile", source_file.id if source_file else "sf1"): source_file,
    }
    if connector is not None:
        mapping[("KnowledgeSourceConnector", connector.id)] = connector

    async def _get(model, pk):
        return mapping.get((model.__name__, pk))

    return _get


@pytest.mark.asyncio
async def test_resolve_ok_for_session_owner():
    db = MagicMock()
    cit = _citation()
    msg = _message()
    sess = _session()
    sf = _sf()
    connector = SimpleNamespace(id="conn1", connector_type="filesystem", name="Docs FS")
    db.get = AsyncMock(side_effect=await _db_get_side_effect(cit, msg, sess, sf, connector))
    member = _member()

    with patch(
        "app.services.citation_service.has_file_permission",
        new=AsyncMock(return_value=True),
    ):
        result = await citation_service.resolve_citation(db, member, "cit1")

    assert result["citation_id"] == "cit1"
    assert result["evidence_id"] == "cit1"
    assert result["evidence_type"] == "chunk"
    assert result["origin"] == "chat"
    assert result["accessible"] is True
    assert result["reason"] == "ok"
    assert result["page"] == 3
    assert result["positions"] == [[1, 2, 3, 4]]
    assert result["source_file_id"] == "sf1"
    assert result["source_kind"] == "connector"
    assert result["connector_type"] == "filesystem"
    assert result["connector_name"] == "Docs FS"
    assert result["source_path"] == "/data/a.pdf"
    assert result["source_revision"] == "rev-9"
    assert result["sync_state"] == "in_sync"
    assert result["source_freshness"] in {"fresh", "stale"}
    assert "credential" not in result
    assert "url" not in str(result).lower() or "source_path" in result


@pytest.mark.asyncio
async def test_stale_source_still_accessible():
    db = MagicMock()
    cit = _citation()
    msg = _message()
    sess = _session()
    sf = _sf(sync_state="stale", last_synced_at=datetime(2020, 1, 1, tzinfo=UTC))
    db.get = AsyncMock(side_effect=await _db_get_side_effect(cit, msg, sess, sf))
    member = _member()

    with patch(
        "app.services.citation_service.has_file_permission",
        new=AsyncMock(return_value=True),
    ):
        result = await citation_service.resolve_citation(db, member, "cit1")

    assert result["accessible"] is True
    assert result["source_freshness"] == "stale"
    assert result["reason"] == "ok"


@pytest.mark.asyncio
async def test_resolve_permission_revoked():
    db = MagicMock()
    cit = _citation()
    msg = _message()
    sess = _session()
    sf = _sf(owner_member_id="other")
    db.get = AsyncMock(side_effect=await _db_get_side_effect(cit, msg, sess, sf))
    member = _member()

    with patch(
        "app.services.citation_service.has_file_permission",
        new=AsyncMock(return_value=False),
    ):
        result = await citation_service.resolve_citation(db, member, "cit1")

    assert result["accessible"] is False
    assert result["reason"] == "permission_revoked"


@pytest.mark.asyncio
async def test_resolve_archived():
    db = MagicMock()
    cit = _citation()
    msg = _message()
    sess = _session()
    sf = _sf(archived_at=datetime.now(UTC))
    db.get = AsyncMock(side_effect=await _db_get_side_effect(cit, msg, sess, sf))
    member = _member()

    with patch(
        "app.services.citation_service.has_file_permission",
        new=AsyncMock(return_value=True),
    ):
        result = await citation_service.resolve_citation(db, member, "cit1")

    assert result["accessible"] is False
    assert result["reason"] == "archived"


@pytest.mark.asyncio
async def test_resolve_deleted_source_file():
    db = MagicMock()
    cit = _citation()
    msg = _message()
    sess = _session()
    sf = _sf(deleted_at=datetime.now(UTC))
    db.get = AsyncMock(side_effect=await _db_get_side_effect(cit, msg, sess, sf))
    member = _member()

    result = await citation_service.resolve_citation(db, member, "cit1")

    assert result["accessible"] is False
    assert result["reason"] == "deleted"


@pytest.mark.asyncio
async def test_resolve_source_file_missing():
    db = MagicMock()
    cit = _citation()
    msg = _message()
    sess = _session()
    db.get = AsyncMock(side_effect=await _db_get_side_effect(cit, msg, sess, None))
    member = _member()

    result = await citation_service.resolve_citation(db, member, "cit1")

    assert result["accessible"] is False
    assert result["reason"] == "not_found"


@pytest.mark.asyncio
async def test_resolve_citation_not_found():
    db = MagicMock()
    db.get = AsyncMock(return_value=None)
    member = _member()

    with pytest.raises(NotFoundError):
        await citation_service.resolve_citation(db, member, "missing")


@pytest.mark.asyncio
async def test_resolve_wrong_org_is_not_found():
    db = MagicMock()
    cit = _citation()
    msg = _message()
    sess = _session(org_id="other-org")
    sf = _sf()
    db.get = AsyncMock(side_effect=await _db_get_side_effect(cit, msg, sess, sf))
    member = _member()

    with pytest.raises(NotFoundError):
        await citation_service.resolve_citation(db, member, "cit1")


@pytest.mark.asyncio
async def test_resolve_same_org_non_owner_without_permission_forbidden():
    db = MagicMock()
    cit = _citation()
    msg = _message()
    sess = _session(member_id="owner-m")
    sf = _sf(owner_member_id="owner-m")
    db.get = AsyncMock(side_effect=await _db_get_side_effect(cit, msg, sess, sf))
    member = _member(member_id="m2")

    with patch(
        "app.services.citation_service.has_file_permission",
        new=AsyncMock(return_value=False),
    ):
        with pytest.raises(ForbiddenError):
            await citation_service.resolve_citation(db, member, "cit1")


@pytest.mark.asyncio
async def test_resolve_same_org_non_owner_with_file_read_allowed():
    db = MagicMock()
    cit = _citation()
    msg = _message()
    sess = _session(member_id="owner-m")
    sf = _sf(owner_member_id="owner-m")
    db.get = AsyncMock(side_effect=await _db_get_side_effect(cit, msg, sess, sf))
    member = _member(member_id="m2")

    with patch(
        "app.services.citation_service.has_file_permission",
        new=AsyncMock(return_value=True),
    ):
        result = await citation_service.resolve_citation(db, member, "cit1")

    assert result["accessible"] is True
    assert result["reason"] == "ok"


@pytest.mark.asyncio
async def test_resolve_retrieval_evidence_ok():
    db = MagicMock()
    cit = _citation(message_id=None, origin="direct_retrieval", issued_member_id="m1")
    sf = _sf()
    db.get = AsyncMock(side_effect=await _db_get_side_effect(cit, None, None, sf))
    member = _member()

    with patch(
        "app.services.citation_service.has_file_permission",
        new=AsyncMock(return_value=True),
    ):
        result = await citation_service.resolve_citation(db, member, "cit1")

    assert result["evidence_id"] == "cit1"
    assert result["message_id"] is None
    assert result["origin"] == "direct_retrieval"
    assert result["accessible"] is True


@pytest.mark.asyncio
async def test_resolve_retrieval_wrong_org_not_found():
    db = MagicMock()
    cit = _citation(message_id=None, org_id="other-org", origin="direct_retrieval")
    db.get = AsyncMock(return_value=cit)
    member = _member()

    with pytest.raises(NotFoundError):
        await citation_service.resolve_citation(db, member, "cit1")


@pytest.mark.asyncio
async def test_resolve_retrieval_no_permission_forbidden():
    db = MagicMock()
    cit = _citation(message_id=None, origin="direct_retrieval")
    sf = _sf()
    db.get = AsyncMock(side_effect=await _db_get_side_effect(cit, None, None, sf))
    member = _member()

    with patch(
        "app.services.citation_service.has_file_permission",
        new=AsyncMock(return_value=False),
    ):
        with pytest.raises(ForbiddenError):
            await citation_service.resolve_citation(db, member, "cit1")


def test_evidence_normalizer_classify_summary():
    from app.integrations.ragflow.models import RagflowChunk
    from app.services.evidence_normalizer import classify

    chunk = RagflowChunk(
        id="c1",
        content="compiled summary",
        document_id="d1",
        document_metadata={"raptor": True},
    )
    assert classify(chunk, "compiled_assisted") == "summary"


def test_evidence_normalizer_ignores_nk_evidence_type():
    from app.integrations.ragflow.models import RagflowChunk
    from app.services.evidence_normalizer import classify

    chunk = RagflowChunk(
        id="c1",
        content="plain",
        document_id="d1",
        document_metadata={"nk_evidence_type": "graph_path"},
    )
    assert classify(chunk, "semantic") == "chunk"
