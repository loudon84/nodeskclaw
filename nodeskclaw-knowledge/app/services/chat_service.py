"""Secure chat sessions and streaming responses."""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.runtime.ragflow import RagflowRuntimeAdapter
from app.core.exceptions import AppException, BadRequestError, ForbiddenError, NotFoundError
from app.integrations.llm_proxy.client import LlmProxyClient
from app.integrations.llm_proxy.exceptions import LlmProxyError
from app.integrations.llm_proxy.models import ChatCompletionRequest, ChatMessage as LlmChatMessage
from app.models.base import not_deleted
from app.models.chat_citation import ChatCitation
from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession
from app.models.enums import (
    ChatMessageRole,
    ChatMessageStatus,
    ChatSessionStatus,
    KnowledgeSetStatus,
    RetrievalOrigin,
    SetPermission,
)
from app.models.knowledge_set import KnowledgeSet
from app.schemas.principal import KnowledgePrincipal
from app.services import context_builder, knowledge_set_service, retrieval_service
from app.services.permission_service import has_set_permission


async def _ensure_set_usable(db: AsyncSession, member: KnowledgePrincipal, knowledge_set_id: str) -> KnowledgeSet:
    ks = await knowledge_set_service.get_knowledge_set(db, member, knowledge_set_id)
    if ks.status == KnowledgeSetStatus.disabled.value:
        raise ForbiddenError(message="知识集合已禁用", message_key="errors.knowledge.set_disabled")
    return ks


_SOURCE_REF_RE = re.compile(r"\[Source\s+(\d+)\]")

# @lat: [[knowledge#Secure Chat]]
CHAT_PIPELINE_VERSION = "v1.2"


async def list_sessions(
    db: AsyncSession,
    member: KnowledgePrincipal,
    *,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[ChatSession], int]:
    filters = [
        ChatSession.org_id == member.org_id,
        ChatSession.member_id == member.member_id,
        not_deleted(ChatSession),
    ]
    total = await db.scalar(select(func.count()).select_from(ChatSession).where(*filters)) or 0
    result = await db.execute(
        select(ChatSession)
        .where(*filters)
        .order_by(ChatSession.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(result.scalars().all()), int(total)


async def create_session(
    db: AsyncSession,
    member: KnowledgePrincipal,
    *,
    knowledge_set_id: str | None = None,
    application_id: str | None = None,
    title: str | None = None,
    answer_mode: str = "detailed",
    show_citations: bool = True,
    answer_model: str | None = None,
    channel: str = "stable",
) -> ChatSession:
    resolved_set_id = knowledge_set_id
    resolved_answer_model = answer_model
    if application_id:
        from app.models.enums import ApplicationPermission, ApplicationStatus
        from app.services import knowledge_application_service
        from app.services.permission_service import has_application_permission

        app = await knowledge_application_service.get_application(db, member, application_id)
        if app.status == ApplicationStatus.disabled.value:
            raise ForbiddenError(
                message="应用已禁用",
                message_key="errors.knowledge.application_disabled",
            )
        if not await has_application_permission(
            db, member, app, ApplicationPermission.use.value
        ):
            raise ForbiddenError(
                message="无权使用该知识应用",
                message_key="errors.knowledge.retrieval_denied",
            )

        if settings.KNOWLEDGE_V24_RELEASE_ENABLED:
            from app.services.release_runtime_service import resolve_application_release

            ctx = await resolve_application_release(
                db,
                member,
                application_id=application_id,
                channel=channel,
            )
            if not ctx.knowledge_set_ids:
                raise BadRequestError(
                    message="Release Manifest 缺少知识集合",
                    message_key="errors.knowledge.application_empty",
                )
            resolved_set_id = ctx.knowledge_set_ids[0]
            if resolved_answer_model is None:
                resolved_answer_model = ctx.answer_model
        else:
            if app.status != ApplicationStatus.active.value:
                raise ForbiddenError(
                    message="应用未发布",
                    message_key="errors.knowledge.application_not_active",
                )
            set_ids = await knowledge_application_service.list_bound_set_ids(db, application_id)
            if not set_ids:
                raise BadRequestError(
                    message="应用未绑定知识集合",
                    message_key="errors.knowledge.application_empty",
                )
            resolved_set_id = set_ids[0]
        if resolved_answer_model is None and not settings.KNOWLEDGE_V24_RELEASE_ENABLED:
            resolved_answer_model = app.answer_model
    if not resolved_set_id:
        raise BadRequestError(
            message="需要 knowledge_set_id 或 application_id",
            message_key="errors.knowledge.chat_target_required",
        )
    await _ensure_set_usable(db, member, resolved_set_id)
    if not await has_set_permission(db, member, resolved_set_id, SetPermission.use.value):
        raise ForbiddenError(message="无权使用该知识集合", message_key="errors.knowledge.set_use_denied")
    row = ChatSession(
        org_id=member.org_id,
        member_id=member.member_id,
        knowledge_set_id=resolved_set_id,
        application_id=application_id,
        title=title,
        answer_mode=answer_mode,
        show_citations=show_citations,
        answer_model=resolved_answer_model,
        status=ChatSessionStatus.active.value,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def get_session(db: AsyncSession, member: KnowledgePrincipal, session_id: str) -> ChatSession:
    row = await db.get(ChatSession, session_id)
    if row is None or row.deleted_at is not None:
        raise NotFoundError(message="会话不存在", message_key="errors.knowledge.chat_session_not_found")
    if row.org_id != member.org_id or row.member_id != member.member_id:
        raise ForbiddenError()
    return row


async def delete_session(db: AsyncSession, member: KnowledgePrincipal, session_id: str) -> None:
    row = await get_session(db, member, session_id)
    row.soft_delete()
    await db.commit()


async def list_messages(
    db: AsyncSession,
    member: KnowledgePrincipal,
    session_id: str,
    *,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[ChatMessage], int]:
    await get_session(db, member, session_id)
    filters = [ChatMessage.session_id == session_id, not_deleted(ChatMessage)]
    total = await db.scalar(select(func.count()).select_from(ChatMessage).where(*filters)) or 0
    result = await db.execute(
        select(ChatMessage)
        .where(*filters)
        .order_by(ChatMessage.created_at.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(result.scalars().all()), int(total)


async def send_message_stream(
    db: AsyncSession,
    member: KnowledgePrincipal,
    ragflow: RagflowRuntimeAdapter,
    llm_proxy: LlmProxyClient,
    *,
    session_id: str,
    content: str,
) -> AsyncIterator[dict]:
    session = await get_session(db, member, session_id)
    await _ensure_set_usable(db, member, session.knowledge_set_id)
    if not await has_set_permission(db, member, session.knowledge_set_id, SetPermission.use.value):
        raise ForbiddenError(message="无权使用该知识集合", message_key="errors.knowledge.set_use_denied")

    user_message = ChatMessage(
        session_id=session.id,
        role=ChatMessageRole.user.value,
        content=content,
        status=ChatMessageStatus.completed.value,
    )
    db.add(user_message)
    await db.flush()

    assistant = ChatMessage(
        session_id=session.id,
        role=ChatMessageRole.assistant.value,
        content="",
        status=ChatMessageStatus.streaming.value,
        model=session.answer_model or settings.LLM_PROXY_PROVIDER,
    )
    db.add(assistant)
    await db.flush()

    yield {"event": "retrieval_started", "data": {"session_id": session.id, "message_id": assistant.id}}

    try:
        retrieval = await retrieval_service.retrieve(
            db,
            member,
            ragflow,
            knowledge_set_id=session.knowledge_set_id,
            application_id=getattr(session, "application_id", None),
            query=content,
            origin=RetrievalOrigin.chat.value,
        )
        raw_chunks = retrieval.get("chunks") or []
        from app.integrations.ragflow.models import RagflowChunk

        ragflow_chunks = [
            RagflowChunk(
                id=str(c.get("chunk_id", "")),
                content=str(c.get("content", "")),
                document_id=str(c.get("document_id") or ""),
                similarity=float(c.get("similarity") or 0),
                document_keyword=c.get("file_name"),
                document_metadata={
                    "nk_source_file_id": c.get("source_file_id"),
                    "nk_file_version_id": c.get("file_version_id"),
                    "nk_knowledge_base_id": c.get("knowledge_base_id"),
                },
                positions=c.get("positions"),
            )
            for c in raw_chunks
        ]
        safe_chunks = context_builder.build_safe_chunks(ragflow_chunks)

        if retrieval.get("status") == "degraded":
            yield {
                "event": "retrieval_degraded",
                "data": {
                    "message": "部分知识源当前不可用，本回答基于可用知识生成。",
                    "message_key": "errors.knowledge.retrieval_partial_failure",
                    "diagnostics": retrieval.get("diagnostics") or {},
                },
            }

        yield {
            "event": "retrieval_completed",
            "data": {"chunk_count": len(safe_chunks), "query_id": retrieval.get("query_id")},
        }

        history_rows = await db.execute(
            select(ChatMessage)
            .where(
                ChatMessage.session_id == session.id,
                ChatMessage.id != assistant.id,
                ChatMessage.id != user_message.id,
                not_deleted(ChatMessage),
            )
            .order_by(ChatMessage.created_at.desc())
            .limit(settings.CHAT_HISTORY_MAX_MESSAGES)
        )
        recent_history = list(history_rows.scalars().all())
        recent_history.reverse()
        history = [
            LlmChatMessage(role=row.role, content=row.content)
            for row in recent_history
            if row.role in {ChatMessageRole.user.value, ChatMessageRole.assistant.value}
        ]

        messages = context_builder.build_context_messages(
            safe_chunks,
            answer_mode=session.answer_mode,
            history=history,
            user_message=content,
        )
        model = session.answer_model or settings.LLM_PROXY_PROVIDER
        request = ChatCompletionRequest(model=model, messages=messages, stream=True)

        yield {"event": "generation_started", "data": {"model": model}}

        accumulated = ""
        prompt_tokens = 0
        completion_tokens = 0

        async for chunk_data in llm_proxy.chat_completions_stream(
            request,
            org_id=member.org_id,
            member_id=member.member_id,
            session_id=session.id,
        ):
            for choice in chunk_data.get("choices") or []:
                delta = choice.get("delta") or {}
                text = delta.get("content") or ""
                if text:
                    accumulated += text
                    yield {"event": "delta", "data": {"content": text}}
            usage = chunk_data.get("usage")
            if usage:
                prompt_tokens = int(usage.get("prompt_tokens") or prompt_tokens)
                completion_tokens = int(usage.get("completion_tokens") or completion_tokens)

        cited_indices = _extract_source_indices(accumulated)
        citations: list[dict] = []
        for idx in cited_indices:
            if not context_builder.context_contains_chunk_index(safe_chunks, idx):
                continue
            safe = next(item for item in safe_chunks if item.index == idx)
            meta = safe.chunk.document_metadata or {}
            page = retrieval_service._extract_page(safe.chunk.positions)
            citation_payload = {
                "index": idx,
                "source_file_id": meta.get("nk_source_file_id"),
                "file_version_id": meta.get("nk_file_version_id"),
                "knowledge_base_id": meta.get("nk_knowledge_base_id"),
                "document_id": safe.chunk.document_id,
                "chunk_id": safe.chunk.id,
                "quote": (safe.chunk.content or "")[:500],
                "score": safe.chunk.similarity,
                "page": page,
                "positions": safe.chunk.positions,
            }
            citations.append(citation_payload)
            if session.show_citations:
                yield {"event": "citation", "data": citation_payload}

        assistant.content = accumulated
        assistant.status = ChatMessageStatus.completed.value
        assistant.prompt_tokens = prompt_tokens
        assistant.completion_tokens = completion_tokens
        assistant.model = model

        for cit in citations:
            source_refs = [
                {
                    "source_file_id": cit.get("source_file_id"),
                    "file_version_id": cit.get("file_version_id"),
                    "knowledge_base_id": cit.get("knowledge_base_id"),
                }
            ]
            runtime_payload = {
                "document_id": cit.get("document_id"),
                "chunk_id": cit.get("chunk_id"),
                "page": cit.get("page"),
                "positions": cit.get("positions"),
            }
            db.add(
                ChatCitation(
                    org_id=member.org_id,
                    issued_member_id=member.member_id,
                    message_id=assistant.id,
                    knowledge_base_id=str(cit.get("knowledge_base_id") or ""),
                    source_file_id=str(cit.get("source_file_id") or ""),
                    file_version_id=str(cit.get("file_version_id") or ""),
                    ragflow_document_id=cit.get("document_id"),
                    ragflow_chunk_id=cit.get("chunk_id"),
                    score=float(cit.get("score") or 0),
                    quote=cit.get("quote"),
                    page=cit.get("page"),
                    positions=cit.get("positions"),
                    evidence_type="chunk",
                    content=cit.get("quote"),
                    source_refs=source_refs,
                    runtime_payload=runtime_payload,
                    origin=RetrievalOrigin.chat.value,
                )
            )

        await db.commit()

        yield {
            "event": "message_completed",
            "data": {
                "message_id": assistant.id,
                "content": accumulated,
                "citations": citations,
            },
        }
    except LlmProxyError as exc:
        assistant.status = ChatMessageStatus.failed.value
        assistant.error_message = str(exc)
        await db.commit()
        yield {"event": "error", "data": {"message": str(exc), "message_key": "errors.knowledge.llm_proxy_failed"}}
    except AppException as exc:
        assistant.status = ChatMessageStatus.failed.value
        assistant.error_message = exc.message
        await db.commit()
        yield {
            "event": "error",
            "data": {
                "message": exc.message,
                "message_key": exc.message_key or "errors.system.internal_error",
            },
        }
    except Exception as exc:
        assistant.status = ChatMessageStatus.failed.value
        assistant.error_message = str(exc)
        await db.commit()
        yield {"event": "error", "data": {"message": str(exc), "message_key": "errors.system.internal_error"}}


def _extract_source_indices(text: str) -> list[int]:
    seen: set[int] = set()
    ordered: list[int] = []
    for match in _SOURCE_REF_RE.finditer(text):
        idx = int(match.group(1))
        if idx not in seen:
            seen.add(idx)
            ordered.append(idx)
    return ordered


def format_sse_event(payload: dict) -> str:
    event = payload.get("event", "message")
    data = payload.get("data", {})
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
