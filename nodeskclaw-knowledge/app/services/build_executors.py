"""Build stage executors — per index_type materialization hooks."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.integrations.ragflow.client import RagflowClient
from app.integrations.ragflow.exceptions import RagflowError
from app.models.base import not_deleted
from app.models.build_job import KnowledgeBuildJob
from app.models.enums import IndexType, SourceFileStatus
from app.models.knowledge_base import KnowledgeBase
from app.models.source_file import SourceFile
from app.runtime.ragflow import RagflowRuntimeAdapter
from app.services import active_runtime_documents, index_state_service, runtime_binding_service
from app.services.active_runtime_documents import ActiveRuntimeDocument, iter_document_batches
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
    validation_payload: dict[str, Any] | None = None
    coverage_payload: dict[str, Any] | None = None


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
    adapter: RagflowRuntimeAdapter,
    dataset_id: str,
    document_ids: list[str],
    *,
    max_wait_seconds: int = 30,
) -> tuple[bool, dict[str, Any]]:
    if not document_ids:
        return False, {"documents_total": 0, "documents_ready": 0, "pending_documents": 0}
    deadline = time.monotonic() + max_wait_seconds
    ready = pending = failed = 0
    while time.monotonic() < deadline:
        ready = 0
        pending = 0
        failed = 0
        for doc_id in document_ids:
            status = await adapter.get_index_build_status(dataset_id, doc_id)
            if status is None:
                pending += 1
                continue
            run = (status.get("run") or "UNSTART").upper()
            chunk_count = int(status.get("chunk_count") or 0)
            if run == "DONE" and chunk_count > 0:
                ready += 1
            elif run in {"FAIL", "CANCEL"}:
                failed += 1
            else:
                pending += 1
        if pending == 0 and failed == 0 and ready == len(document_ids):
            return True, {
                "documents_total": len(document_ids),
                "documents_ready": ready,
                "pending_documents": 0,
                "failed_documents": failed,
            }
        await asyncio.sleep(2)
    return False, {
        "documents_total": len(document_ids),
        "documents_ready": ready,
        "pending_documents": pending,
        "failed_documents": failed,
    }


def _chunk_question_count(chunk: dict[str, Any]) -> int:
    questions = chunk.get("questions") or chunk.get("question_kwd")
    if questions is None:
        return 0
    if isinstance(questions, str):
        return 1 if questions.strip() else 0
    if isinstance(questions, list):
        return len([item for item in questions if item])
    return 0


def _chunk_has_summary_marker(chunk: dict[str, Any]) -> bool:
    for key in ("compiled", "raptor", "summary", "is_summary"):
        value = chunk.get(key)
        if value:
            return True
    content = str(chunk.get("content") or "")
    return "raptor" in content.lower() or "compiled" in content.lower()


async def _validate_question_artifacts(
    adapter: RagflowRuntimeAdapter,
    dataset_id: str,
    documents: list[ActiveRuntimeDocument],
) -> tuple[dict[str, Any], dict[str, Any], bool]:
    eligible = len(documents)
    enriched_chunks = 0
    per_document: list[dict[str, Any]] = []
    for doc in documents:
        chunks = await adapter.read_document_chunks(dataset_id, doc.ragflow_document_id, page=1, page_size=100)
        doc_enriched = sum(_chunk_question_count(chunk) for chunk in chunks)
        enriched_chunks += doc_enriched
        per_document.append(
            {
                "ragflow_document_id": doc.ragflow_document_id,
                "file_version_id": doc.file_version_id,
                "question_enriched_chunks": doc_enriched,
            }
        )
    coverage_ratio = (enriched_chunks / eligible) if eligible else 0.0
    validation = {
        "artifact_type": "question_enrichment",
        "eligible_documents": eligible,
        "question_enriched_chunks": enriched_chunks,
        "per_document": per_document,
        "ready": enriched_chunks > 0,
    }
    coverage = {
        "eligible_documents": eligible,
        "question_enriched_chunks": enriched_chunks,
        "coverage_ratio": coverage_ratio,
    }
    return validation, coverage, enriched_chunks > 0


async def _validate_summary_artifacts(
    adapter: RagflowRuntimeAdapter,
    dataset_id: str,
    documents: list[ActiveRuntimeDocument],
) -> tuple[dict[str, Any], dict[str, Any], bool]:
    summary_chunks = 0
    per_document: list[dict[str, Any]] = []
    for doc in documents:
        chunks = await adapter.read_document_chunks(dataset_id, doc.ragflow_document_id, page=1, page_size=100)
        doc_summary = sum(1 for chunk in chunks if _chunk_has_summary_marker(chunk))
        summary_chunks += doc_summary
        per_document.append(
            {
                "ragflow_document_id": doc.ragflow_document_id,
                "file_version_id": doc.file_version_id,
                "summary_chunks": doc_summary,
            }
        )
    validation = {
        "artifact_type": "raptor_summary",
        "eligible_documents": len(documents),
        "summary_chunks": summary_chunks,
        "per_document": per_document,
        "ready": summary_chunks > 0,
    }
    coverage = {
        "eligible_documents": len(documents),
        "summary_chunks": summary_chunks,
        "coverage_ratio": (summary_chunks / len(documents)) if documents else 0.0,
    }
    return validation, coverage, summary_chunks > 0


async def _validate_graph_artifacts(
    adapter: RagflowRuntimeAdapter,
    dataset_id: str,
) -> tuple[dict[str, Any], dict[str, Any], bool]:
    graph = await adapter.get_dataset_graph(dataset_id)
    entities = graph.get("entities") or (graph.get("data") or {}).get("entities") or []
    relations = graph.get("relations") or (graph.get("data") or {}).get("relations") or []
    entity_count = len(entities) if isinstance(entities, list) else 0
    relation_count = len(relations) if isinstance(relations, list) else 0
    ready = entity_count > 0 or relation_count > 0
    validation = {
        "artifact_type": "graph",
        "entity_count": entity_count,
        "relation_count": relation_count,
        "ready": ready,
    }
    coverage = {
        "entity_count": entity_count,
        "relation_count": relation_count,
        "coverage_ratio": 1.0 if ready else 0.0,
    }
    return validation, coverage, ready


async def _trigger_parse_batches(
    adapter: RagflowRuntimeAdapter,
    dataset_id: str,
    document_ids: list[str],
) -> None:
    batch_size = settings.RAGFLOW_BUILD_BATCH_SIZE
    semaphore = asyncio.Semaphore(batch_size)

    async def _parse_batch(batch: list[str]) -> None:
        async with semaphore:
            await adapter.trigger_index_build(dataset_id, document_ids=batch)

    batches = iter_document_batches(document_ids, batch_size)
    await asyncio.gather(*[_parse_batch(batch) for batch in batches if batch])


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
    page_size = settings.RAGFLOW_BUILD_BATCH_SIZE
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
        "runtime_operation": "chunk_inventory",
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
    runtime_operation: str,
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
        resolution = await active_runtime_documents.resolve_and_validate_active_documents(
            db,
            adapter,
            knowledge_base_id=kb.id,
            dataset_id=dataset_id,
        )
        if resolution.blocked:
            return StageResult(
                status="failed",
                retryable=True,
                error_code="active_documents_blocked",
                error_message="active runtime documents require reconciliation",
                output={
                    "runtime_operation": runtime_operation,
                    "active_document_count": len(resolution.documents),
                    "blocked_documents": resolution.blocked,
                },
            )
        doc_ids = [doc.ragflow_document_id for doc in resolution.documents]
        if doc_ids:
            await _trigger_parse_batches(adapter, dataset_id, doc_ids)
        ready, poll_output = await _poll_documents_ready(adapter, dataset_id, doc_ids, max_wait_seconds=20)
        output = {
            **poll_output,
            "runtime_operation": runtime_operation,
            "runtime_config_revision": getattr(binding, "config_revision", None),
            "active_document_count": len(resolution.documents),
            "processed_document_count": poll_output.get("documents_ready", 0),
            "capability_key": capability_key,
            "retrieval_ready": is_index_retrieval_ready(index_type, capabilities),
        }
        if not ready:
            return StageResult(
                status="failed",
                retryable=True,
                error_code="build_not_ready",
                error_message=f"{index_type} build still in progress",
                output=output,
            )

        validation_payload: dict[str, Any]
        coverage_payload: dict[str, Any]
        artifact_ready: bool
        if index_type == IndexType.question.value:
            validation_payload, coverage_payload, artifact_ready = await _validate_question_artifacts(
                adapter, dataset_id, resolution.documents
            )
        elif index_type == IndexType.hierarchical_summary.value:
            validation_payload, coverage_payload, artifact_ready = await _validate_summary_artifacts(
                adapter, dataset_id, resolution.documents
            )
        elif index_type == IndexType.graph.value:
            validation_payload, coverage_payload, artifact_ready = await _validate_graph_artifacts(
                adapter, dataset_id
            )
        else:
            validation_payload = {"ready": True}
            coverage_payload = {}
            artifact_ready = True

        output["artifact_validation"] = validation_payload
        output["retrieval_validation"] = {"ready": artifact_ready}
        if not artifact_ready:
            return StageResult(
                status="failed",
                retryable=True,
                error_code="artifact_validation_failed",
                error_message=f"{index_type} artifact validation failed",
                output=output,
                validation_payload=validation_payload,
                coverage_payload=coverage_payload,
            )
        return StageResult(
            status="succeeded",
            retryable=False,
            output=output,
            validation_payload=validation_payload,
            coverage_payload=coverage_payload,
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
        runtime_operation="question_enrichment",
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
        runtime_operation="raptor_summary",
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
        runtime_operation="graph_build",
    )


EXECUTORS: dict[str, StageExecutor] = {
    IndexType.chunk.value: execute_chunk_stage,
    IndexType.question.value: execute_question_stage,
    IndexType.hierarchical_summary.value: execute_summary_stage,
    IndexType.graph.value: execute_graph_stage,
}
