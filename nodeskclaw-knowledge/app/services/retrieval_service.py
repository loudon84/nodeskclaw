"""Secure retrieval pipeline."""

from __future__ import annotations

import hashlib
import time
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, ForbiddenError
from app.integrations.ragflow.client import RagflowClient
from app.models.enums import AccessPlanKind
from app.models.retrieval_audit import RetrievalAudit
from app.schemas.principal import KnowledgePrincipal
from app.services import chunk_security_service, knowledge_set_service
from app.services.permission_service import build_access_plan


async def retrieve(
    db: AsyncSession,
    member: KnowledgePrincipal,
    ragflow: RagflowClient,
    *,
    knowledge_set_id: str,
    query: str,
    top_k: int = 20,
    similarity_threshold: float | None = 0.2,
) -> dict:
    started = time.perf_counter()
    kbs = await knowledge_set_service.list_bound_knowledge_bases(db, member, knowledge_set_id)
    if not kbs:
        raise BadRequestError(message="知识集合未绑定知识库", message_key="errors.knowledge.set_empty")

    plan = await build_access_plan(db, member, kbs)
    if plan.kind == AccessPlanKind.no_access or not plan.dataset_ids:
        raise ForbiddenError(message="无权检索该知识集合", message_key="errors.knowledge.retrieval_denied")

    document_ids = plan.document_ids if plan.kind == AccessPlanKind.filtered_access else None
    if plan.kind == AccessPlanKind.filtered_access and not document_ids:
        return {
            "query_id": str(uuid.uuid4()),
            "chunks": [],
        }

    result = await ragflow.retrieve(
        question=query,
        dataset_ids=plan.dataset_ids,
        document_ids=document_ids,
        top_k=top_k,
        similarity_threshold=similarity_threshold,
    )

    allowed = set(plan.source_file_ids)
    if plan.kind == AccessPlanKind.full_access and not allowed:
        from sqlalchemy import select

        from app.models.base import not_deleted
        from app.models.source_file import SourceFile

        for kb in kbs:
            rows = await db.execute(
                select(SourceFile.id).where(
                    SourceFile.knowledge_base_id == kb.id,
                    not_deleted(SourceFile),
                )
            )
            allowed.update(rows.scalars().all())

    safe_chunks, filtered_count = await chunk_security_service.clean_chunks(
        db,
        ragflow,
        result.chunks,
        allowed_source_file_ids=allowed,
    )

    query_id = str(uuid.uuid4())
    latency_ms = int((time.perf_counter() - started) * 1000)
    audit = RetrievalAudit(
        member_id=member.member_id,
        org_id=member.org_id,
        knowledge_set_id=knowledge_set_id,
        query_hash=hashlib.sha256(query.encode("utf-8")).hexdigest(),
        candidate_chunk_count=len(result.chunks),
        filtered_chunk_count=filtered_count,
        returned_chunk_count=len(safe_chunks),
        source_file_ids=sorted({c.document_metadata.get("nk_source_file_id") for c in safe_chunks if c.document_metadata.get("nk_source_file_id")}),
        latency_ms=latency_ms,
    )
    db.add(audit)
    await db.commit()

    chunks_out = []
    for chunk in safe_chunks:
        meta = chunk.document_metadata or {}
        chunks_out.append(
            {
                "chunk_id": chunk.id,
                "knowledge_base_id": meta.get("nk_knowledge_base_id"),
                "source_file_id": meta.get("nk_source_file_id"),
                "file_version_id": meta.get("nk_file_version_id"),
                "document_id": chunk.document_id,
                "file_name": chunk.document_keyword,
                "content": chunk.content,
                "similarity": chunk.similarity,
            }
        )

    return {"query_id": query_id, "chunks": chunks_out}
