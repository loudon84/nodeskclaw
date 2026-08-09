"""Citation resolve: historical metadata + current ACL/file status + source provenance."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.chat_citation import ChatCitation
from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession
from app.models.connector import KnowledgeSourceConnector
from app.models.enums import FilePermission, SourceSyncState
from app.models.source_file import SourceFile
from app.schemas.principal import KnowledgePrincipal
from app.services.permission_service import has_file_permission

# @lat: [[knowledge#Citation Resolve]]


def _source_freshness(source_file: SourceFile | None) -> str:
    if source_file is None:
        return "unknown"
    if source_file.sync_state in {SourceSyncState.stale.value, SourceSyncState.error.value}:
        return "stale"
    if source_file.last_synced_at is None:
        return "unknown" if source_file.source_kind == "connector" else "fresh"
    last = source_file.last_synced_at
    if last.tzinfo is None:
        last = last.replace(tzinfo=UTC)
    age = (datetime.now(UTC) - last).total_seconds()
    if age > int(settings.SOURCE_FRESHNESS_MAX_AGE_SECONDS):
        return "stale"
    return "fresh"


def _citation_payload(
    citation: ChatCitation,
    *,
    accessible: bool,
    reason: str,
    source_file: SourceFile | None = None,
    connector: KnowledgeSourceConnector | None = None,
) -> dict:
    payload = {
        "citation_id": citation.id,
        "message_id": citation.message_id,
        "knowledge_base_id": citation.knowledge_base_id,
        "source_file_id": citation.source_file_id,
        "file_version_id": citation.file_version_id,
        "document_id": citation.ragflow_document_id,
        "chunk_id": citation.ragflow_chunk_id,
        "page": citation.page,
        "positions": citation.positions,
        "score": citation.score,
        "quote": citation.quote,
        "accessible": accessible,
        "reason": reason,
        "source_kind": getattr(source_file, "source_kind", None),
        "connector_type": getattr(connector, "connector_type", None),
        "connector_name": getattr(connector, "name", None),
        "source_path": getattr(source_file, "source_path", None),
        "source_revision": getattr(source_file, "source_revision", None),
        "source_modified_at": (
            source_file.source_modified_at.isoformat()
            if source_file and source_file.source_modified_at
            else None
        ),
        "last_synced_at": (
            source_file.last_synced_at.isoformat() if source_file and source_file.last_synced_at else None
        ),
        "sync_state": getattr(source_file, "sync_state", None),
        "source_freshness": _source_freshness(source_file),
    }
    return payload


async def resolve_citation(
    db: AsyncSession,
    member: KnowledgePrincipal,
    citation_id: str,
) -> dict:
    citation = await db.get(ChatCitation, citation_id)
    if citation is None or citation.deleted_at is not None:
        raise NotFoundError(message="引用不存在", message_key="errors.knowledge.citation_not_found")

    message = await db.get(ChatMessage, citation.message_id)
    if message is None or message.deleted_at is not None:
        raise NotFoundError(message="引用不存在", message_key="errors.knowledge.citation_not_found")

    session = await db.get(ChatSession, message.session_id)
    if session is None or session.deleted_at is not None:
        raise NotFoundError(message="引用不存在", message_key="errors.knowledge.citation_not_found")

    if session.org_id != member.org_id:
        raise NotFoundError(message="引用不存在", message_key="errors.knowledge.citation_not_found")

    is_owner = session.member_id == member.member_id
    source_file = await db.get(SourceFile, citation.source_file_id)
    connector = None
    if source_file and source_file.connector_id:
        connector = await db.get(KnowledgeSourceConnector, source_file.connector_id)

    if not is_owner:
        if source_file is None or source_file.deleted_at is not None:
            raise ForbiddenError()
        if not await has_file_permission(db, member, source_file, FilePermission.read.value):
            raise ForbiddenError()

    if source_file is None:
        return _citation_payload(citation, accessible=False, reason="not_found")
    if source_file.deleted_at is not None:
        return _citation_payload(
            citation, accessible=False, reason="deleted", source_file=source_file, connector=connector
        )
    if source_file.archived_at is not None:
        return _citation_payload(
            citation, accessible=False, reason="archived", source_file=source_file, connector=connector
        )
    if not await has_file_permission(db, member, source_file, FilePermission.read.value):
        return _citation_payload(
            citation,
            accessible=False,
            reason="permission_revoked",
            source_file=source_file,
            connector=connector,
        )
    return _citation_payload(
        citation, accessible=True, reason="ok", source_file=source_file, connector=connector
    )
