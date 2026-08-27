"""Reconciliation metadata LOCAL_WINS repair tests."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from datetime import UTC, datetime

from app.integrations.ragflow.models import RagflowDocument
from app.services import reconciliation_service


@pytest.mark.asyncio
async def test_metadata_drift_local_wins_repair():
    db = MagicMock()
    ragflow = AsyncMock()
    version = SimpleNamespace(
        id="v1",
        ragflow_document_id="d1",
        parse_status="active",
        deleted_at=None,
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    sf = SimpleNamespace(
        id="sf1",
        org_id="o1",
        knowledge_base_id="kb1",
        metadata_={"document_type": "contract"},
        metadata_revision=2,
    )
    kb = SimpleNamespace(id="kb1", ragflow_dataset_id="ds1")

    execute_result = MagicMock()
    execute_result.all.return_value = [(version, sf, kb)]
    empty_result = MagicMock()
    empty_result.all.return_value = []
    db.execute = AsyncMock(side_effect=[execute_result, empty_result])

    drifted = RagflowDocument(
        id="d1",
        name="a.pdf",
        meta_fields={
            "nk_source_file_id": "sf1",
            "nk_file_version_id": "v1",
            "nk_knowledge_base_id": "kb1",
            "nk_org_id": "o1",
            "nk_metadata_revision": "1",
            "biz_document_type": "manual",
        },
    )
    repaired = RagflowDocument(
        id="d1",
        name="a.pdf",
        meta_fields={
            "nk_source_file_id": "sf1",
            "nk_file_version_id": "v1",
            "nk_knowledge_base_id": "kb1",
            "nk_org_id": "o1",
            "nk_metadata_revision": "2",
            "biz_document_type": "contract",
        },
    )
    ragflow.list_documents = AsyncMock(side_effect=[[drifted], [repaired]])
    ragflow.update_document_metadata = AsyncMock()

    with patch("app.services.reconciliation_service.write_audit", new=AsyncMock()) as write_audit:
        checked, drift, repaired_count, failed = await reconciliation_service._repair_metadata_drift(db, ragflow)

    assert checked == 1
    assert drift == 1
    assert repaired_count == 1
    assert failed == 0
    ragflow.update_document_metadata.assert_awaited_once()
    assert write_audit.await_args.kwargs["action"] == "METADATA_REPAIRED"
    assert write_audit.await_args.kwargs["details"]["status"] == "REPAIRED"
