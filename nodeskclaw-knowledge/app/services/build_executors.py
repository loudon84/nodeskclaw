"""Build stage executors — per index_type materialization hooks."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.ragflow.client import RagflowClient
from app.integrations.ragflow.exceptions import RagflowError
from app.models.base import not_deleted
from app.models.build_job import KnowledgeBuildJob
from app.models.enums import IndexType, SourceFileStatus
from app.models.knowledge_base import KnowledgeBase
from app.models.source_file import SourceFile
from app.runtime.ragflow import RagflowRuntimeAdapter
from app.services import index_state_service, runtime_binding_service
from app.services.index_registry import is_index_retrieval_ready, is_runtime_supported

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


async def _current_active_watermark(db: AsyncSession, kb: KnowledgeBase) -> str | None:
    result = await db.execute(
        select(SourceFile.active_version_id)
        .where(
            SourceFile.knowledge_base_id == kb.id,
            SourceFile.status == SourceFileStatus.active.value,
            SourceFile.active_version_id.is_not(None),
            not_deleted(SourceFile),
        )
        .order_by(SourceFile.updated_at.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    return str(row) if row else None


async def _validate_source_watermark(
    db: AsyncSession,
    kb: KnowledgeBase,
    index_type: str,
) -> StageResult | None:
    state = await index_state_service.get_or_create_state(
        db,
        org_id=kb.org_id,
        knowledge_base_id=kb.id,
        index_type=index_type,
    )
    expected = state.source_watermark
    if not expected:
        return None
    current = await _current_active_watermark(db, kb)
    if current and current != expected:
        return StageResult(
            status="failed",
            retryable=True,
            error_code="source_watermark_mismatch",
            error_message="active version changed during build",
            output={"expected_watermark": expected, "current_watermark": current},
        )
    return None


async def _poll_documents_ready(
    dataset_id: str,
    *,
    max_wait_seconds: int = 30,
) -> tuple[bool, dict[str, Any]]:
    ragflow = RagflowClient()
    try:
        deadline = time.monotonic() + max_wait_seconds
        while time.monotonic() < deadline:
            docs = await ragflow.list_documents(dataset_id, page=1, page_size=200)
            total = len(docs)
            ready = sum(
                1
                for doc in docs
                if (doc.run or "UNSTART").upper() == "DONE" and (doc.chunk_count or 0) > 0
            )
            pending = total - ready
            if total > 0 and pending == 0:
                return True, {"documents_total": total, "documents_ready": ready}
            await asyncio.sleep(2)
        docs = await ragflow.list_documents(dataset_id, page=1, page_size=200)
        ready = sum(
            1
            for doc in docs
            if (doc.run or "UNSTART").upper() == "DONE" and (doc.chunk_count or 0) > 0
        )
        return False, {
            "documents_total": len(docs),
            "documents_ready": ready,
            "pending_documents": len(docs) - ready,
        }
    finally:
        await ragflow.aclose()


# @lat: [[knowledge-objects#Build Job]]
async def execute_chunk_stage(
    db: AsyncSession,
    job: KnowledgeBuildJob,
    kb: KnowledgeBase,
) -> StageResult:
    mismatch = await _validate_source_watermark(db, kb, IndexType.chunk.value)
    if mismatch is not None:
        return mismatch

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
        "pending_documents": len(not_ready_ids),
        "failed_documents": len(failed_ids),
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


async def _execute_secondary_stage(
    db: AsyncSession,
    job: KnowledgeBuildJob,
    kb: KnowledgeBase,
    *,
    index_type: str,
    capability_key: str,
    parser_patch: dict[str, Any],
) -> StageResult:
    mismatch = await _validate_source_watermark(db, kb, index_type)
    if mismatch is not None:
        return mismatch

    binding = await runtime_binding_service.get_binding(db, kb.id)
    capabilities = (binding.capabilities if binding else None) or {}
    if not is_runtime_supported(index_type, capabilities):
        return StageResult(
            status="failed",
            retryable=False,
            error_code="runtime_public_api_unavailable",
            error_message=f"{index_type} build unsupported by runtime",
        )

    dataset_id = await runtime_binding_service.require_dataset_id(db, kb)
    adapter = RagflowRuntimeAdapter()
    try:
        current = await adapter.get_dataset_runtime_config(dataset_id) or {}
        parser_config = dict(current.get("parser_config") or {})
        parser_config.update(parser_patch)
        await adapter.configure_index(dataset_id, parser_config=parser_config)
        docs = await adapter.client.list_documents(dataset_id, page=1, page_size=200)
        doc_ids = [doc.id for doc in docs if doc.id]
        if doc_ids:
            await adapter.trigger_index_build(dataset_id, document_ids=doc_ids[:50])
        ready, poll_output = await _poll_documents_ready(dataset_id, max_wait_seconds=20)
        output = {
            **poll_output,
            "capability_key": capability_key,
            "retrieval_ready": is_index_retrieval_ready(index_type, capabilities),
        }
        if ready:
            return StageResult(status="succeeded", retryable=False, output=output)
        return StageResult(
            status="failed",
            retryable=True,
            error_code="build_not_ready",
            error_message=f"{index_type} build still in progress",
            output=output,
        )
    except RagflowError as exc:
        return StageResult(
            status="failed",
            retryable=True,
            error_code="runtime_error",
            error_message=str(exc),
        )
    finally:
        await adapter.aclose()


async def execute_question_stage(
    db: AsyncSession,
    job: KnowledgeBuildJob,
    kb: KnowledgeBase,
) -> StageResult:
    return await _execute_secondary_stage(
        db,
        job,
        kb,
        index_type=IndexType.question.value,
        capability_key="supports_auto_questions",
        parser_patch={"auto_questions": 5},
    )


async def execute_summary_stage(
    db: AsyncSession,
    job: KnowledgeBuildJob,
    kb: KnowledgeBase,
) -> StageResult:
    return await _execute_secondary_stage(
        db,
        job,
        kb,
        index_type=IndexType.hierarchical_summary.value,
        capability_key="supports_raptor",
        parser_patch={"raptor": {"use_raptor": True}},
    )


async def execute_graph_stage(
    db: AsyncSession,
    job: KnowledgeBuildJob,
    kb: KnowledgeBase,
) -> StageResult:
    return await _execute_secondary_stage(
        db,
        job,
        kb,
        index_type=IndexType.graph.value,
        capability_key="supports_graph",
        parser_patch={"graphrag": {"use_graphrag": True}},
    )


EXECUTORS: dict[str, StageExecutor] = {
    IndexType.chunk.value: execute_chunk_stage,
    IndexType.question.value: execute_question_stage,
    IndexType.hierarchical_summary.value: execute_summary_stage,
    IndexType.graph.value: execute_graph_stage,
}
