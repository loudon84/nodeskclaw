"""Build stage executors — per index_type materialization hooks."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.ragflow.client import RagflowClient
from app.integrations.ragflow.exceptions import RagflowError
from app.models.build_job import KnowledgeBuildJob
from app.models.enums import IndexType
from app.models.knowledge_base import KnowledgeBase
from app.services import runtime_binding_service

StageExecutor = Callable[
    [AsyncSession, KnowledgeBuildJob, KnowledgeBase],
    Awaitable["StageResult"],
]


@dataclass
class StageResult:
    status: str
    retryable: bool = False
    error_code: str | None = None
    error_message: str | None = None
    output: dict[str, Any] = field(default_factory=dict)


# @lat: [[knowledge-objects#Build Job]]
async def execute_chunk_stage(
    db: AsyncSession,
    job: KnowledgeBuildJob,
    kb: KnowledgeBase,
) -> StageResult:
    dataset_id = await runtime_binding_service.require_dataset_id(db, kb)
    ragflow = RagflowClient()
    page = 1
    page_size = 100
    documents_total = 0
    documents_ready = 0
    chunks_total = 0
    not_ready_ids: list[str] = []
    failed_ids: list[str] = []

    try:
        while True:
            docs = await ragflow.list_documents(dataset_id, page=page, page_size=page_size)
            if not docs:
                break
            for doc in docs:
                documents_total += 1
                run = (doc.run or "UNSTART").upper()
                if run == "DONE" and doc.chunk_count and doc.chunk_count > 0:
                    documents_ready += 1
                    chunks_total += int(doc.chunk_count or 0)
                elif run in {"FAIL", "CANCEL"}:
                    failed_ids.append(doc.id)
                else:
                    not_ready_ids.append(doc.id)
            if len(docs) < page_size:
                break
            page += 1
    except RagflowError:
        raise
    finally:
        await ragflow.aclose()

    output = {
        "documents_total": documents_total,
        "documents_ready": documents_ready,
        "chunks_total": chunks_total,
        "not_ready_document_ids": not_ready_ids[:20],
        "failed_document_ids": failed_ids[:20],
    }

    if failed_ids:
        return StageResult(
            status="failed",
            retryable=False,
            error_code="documents_parse_failed",
            error_message=f"{len(failed_ids)} document(s) failed parsing",
            output=output,
        )

    if not_ready_ids:
        return StageResult(
            status="failed",
            retryable=True,
            error_code="documents_not_ready",
            error_message=f"{len(not_ready_ids)} document(s) not ready",
            output=output,
        )

    return StageResult(status="succeeded", retryable=False, output=output)


EXECUTORS: dict[str, StageExecutor] = {
    IndexType.chunk.value: execute_chunk_stage,
}
