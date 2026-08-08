"""Citation resolve: historical metadata + current ACL/file status."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.chat_citation import ChatCitation
from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession
from app.models.enums import FilePermission
from app.models.source_file import SourceFile
from app.schemas.principal import KnowledgePrincipal
from app.services.permission_service import has_file_permission

# @lat: [[knowledge#Citation Resolve]]


def _citation_payload(citation: ChatCitation, *, accessible: bool, reason: str) -> dict:
    return {
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
    }


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

    if not is_owner:
        if source_file is None or source_file.deleted_at is not None:
            raise ForbiddenError()
        if not await has_file_permission(db, member, source_file, FilePermission.read.value):
            raise ForbiddenError()

    if source_file is None:
        return _citation_payload(citation, accessible=False, reason="not_found")
    if source_file.deleted_at is not None:
        return _citation_payload(citation, accessible=False, reason="deleted")
    if source_file.archived_at is not None:
        return _citation_payload(citation, accessible=False, reason="archived")
    if not await has_file_permission(db, member, source_file, FilePermission.read.value):
        return _citation_payload(citation, accessible=False, reason="permission_revoked")
    return _citation_payload(citation, accessible=True, reason="ok")
