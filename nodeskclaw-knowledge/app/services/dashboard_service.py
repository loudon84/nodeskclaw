"""Dashboard aggregation scoped to member permissions."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import not_deleted
from app.models.chat_message import ChatMessage
from app.models.enums import FilePermission, KbPermission, SetPermission
from app.models.knowledge_base import KnowledgeBase
from app.models.knowledge_set import KnowledgeSet
from app.models.retrieval_audit import RetrievalAudit
from app.models.source_file import SourceFile
from app.models.source_file_version import SourceFileVersion
from app.schemas.principal import KnowledgePrincipal
from app.services.permission_service import has_file_permission, has_kb_permission, has_set_permission


def _parse_status_bucket(parse_status: str | None) -> str:
    if parse_status in {"pending"}:
        return "pending"
    if parse_status in {"parsing"}:
        return "parsing"
    if parse_status in {"active", "superseded"}:
        return "completed"
    if parse_status in {"failed"}:
        return "failed"
    return "pending"


async def get_dashboard(db: AsyncSession, member: KnowledgePrincipal) -> dict:
    kb_rows = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.org_id == member.org_id,
            not_deleted(KnowledgeBase),
        )
    )
    readable_kbs = [
        kb for kb in kb_rows.scalars().all()
        if await has_kb_permission(db, member, kb.id, KbPermission.read.value)
    ]
    kb_ids = {kb.id for kb in readable_kbs}

    set_rows = await db.execute(
        select(KnowledgeSet).where(
            KnowledgeSet.org_id == member.org_id,
            not_deleted(KnowledgeSet),
        ).order_by(KnowledgeSet.updated_at.desc())
    )
    readable_sets = [
        ks for ks in set_rows.scalars().all()
        if await has_set_permission(db, member, ks, SetPermission.read.value)
        or await has_set_permission(db, member, ks, SetPermission.use.value)
    ]

    file_filters = [
        SourceFile.org_id == member.org_id,
        not_deleted(SourceFile),
    ]
    if kb_ids:
        file_filters.append(SourceFile.knowledge_base_id.in_(kb_ids))
    else:
        file_filters.append(SourceFile.knowledge_base_id.in_([]))

    file_rows = await db.execute(
        select(SourceFile).where(*file_filters).order_by(SourceFile.updated_at.desc())
    )
    readable_files: list[SourceFile] = []
    parse_status_summary = {"pending": 0, "parsing": 0, "completed": 0, "failed": 0}
    total_chunks = 0

    for sf in file_rows.scalars().all():
        if not await has_file_permission(db, member, sf, FilePermission.read.value):
            continue
        readable_files.append(sf)
        if sf.active_version_id:
            version = await db.get(SourceFileVersion, sf.active_version_id)
            if version and version.deleted_at is None:
                bucket = _parse_status_bucket(version.parse_status)
                parse_status_summary[bucket] += 1
                total_chunks += int(version.chunk_count or 0)

    week_start = datetime.now(UTC) - timedelta(days=7)
    retrieval_count = await db.scalar(
        select(func.count()).select_from(RetrievalAudit).where(
            RetrievalAudit.org_id == member.org_id,
            RetrievalAudit.member_id == member.member_id,
            RetrievalAudit.created_at >= week_start,
            not_deleted(RetrievalAudit),
        )
    ) or 0
    chat_count = await db.scalar(
        select(func.count()).select_from(ChatMessage).where(
            ChatMessage.role == "user",
            ChatMessage.created_at >= week_start,
            not_deleted(ChatMessage),
        )
    ) or 0

    return {
        "stats": {
            "knowledge_base_count": len(readable_kbs),
            "knowledge_set_count": len(readable_sets),
            "document_count": len(readable_files),
            "chunk_count": total_chunks,
            "weekly_query_count": int(retrieval_count) + int(chat_count),
        },
        "parse_status_summary": parse_status_summary,
        "recent_knowledge_sets": readable_sets[:5],
        "recent_documents": readable_files[:5],
    }
