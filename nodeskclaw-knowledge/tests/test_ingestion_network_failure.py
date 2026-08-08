"""Ingestion worker: network exhaustion must not mark version failed."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.integrations.ragflow.exceptions import RagflowError
from app.models.enums import IngestionJobStatus
from app.services.ingestion_service import process_leased_job


@pytest.mark.asyncio
async def test_process_leased_job_network_exhaustion_keeps_version_not_failed():
    job = SimpleNamespace(
        source_file_id="sf1",
        file_version_id="v1",
        attempt_count=4,
        max_attempts=5,
        status=IngestionJobStatus.parsing.value,
        progress=80,
        next_run_at=None,
        finished_at=None,
        error_code=None,
        error_message=None,
    )
    sf = SimpleNamespace(
        id="sf1",
        knowledge_base_id="kb1",
        active_version_id="v0",
        status="updating",
    )
    version = SimpleNamespace(
        id="v1",
        ragflow_document_id="doc1",
        parse_status="parsing",
        ragflow_status="RUNNING",
        ragflow_run="RUNNING",
        ragflow_progress=0.5,
        ragflow_progress_msg=None,
        chunk_count=None,
        token_count=None,
        process_duration=None,
    )
    kb = SimpleNamespace(id="kb1", ragflow_dataset_id="ds1")

    async def _get(model, oid):
        mapping = {"sf1": sf, "v1": version, "kb1": kb}
        return mapping.get(oid)

    db = MagicMock()
    db.get = AsyncMock(side_effect=_get)
    db.flush = AsyncMock()
    ragflow = AsyncMock()
    ragflow.list_documents = AsyncMock(side_effect=RagflowError("timeout", message_key="errors.knowledge.ragflow_error"))

    await process_leased_job(db, ragflow, job)

    assert job.status == IngestionJobStatus.failed.value
    assert job.error_message == "timeout"
    assert version.parse_status == "parsing"
