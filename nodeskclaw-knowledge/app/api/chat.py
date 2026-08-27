"""Chat session and streaming message API."""

from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_llm_proxy_client, get_member_context, get_runtime_adapter
from app.integrations.llm_proxy.client import LlmProxyClient
from app.runtime.ragflow import RagflowRuntimeAdapter
from app.schemas.common import ApiResponse, PageData
from app.schemas.knowledge import ChatMessageCreate, ChatMessageOut, ChatSessionCreate, ChatSessionOut
from app.schemas.principal import KnowledgePrincipal
from app.services import chat_service

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/sessions", response_model=ApiResponse[PageData[ChatSessionOut]])
async def list_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    items, total = await chat_service.list_sessions(db, member, page=page, page_size=page_size)
    return ApiResponse(
        data=PageData(
            items=[ChatSessionOut.model_validate(i) for i in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.post("/sessions", response_model=ApiResponse[ChatSessionOut])
async def create_session(
    body: ChatSessionCreate,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    row = await chat_service.create_session(
        db,
        member,
        knowledge_set_id=body.knowledge_set_id,
        application_id=body.application_id,
        title=body.title,
        answer_mode=body.answer_mode.value,
        show_citations=body.show_citations,
        answer_model=body.answer_model,
    )
    return ApiResponse(data=ChatSessionOut.model_validate(row))


@router.get("/sessions/{session_id}", response_model=ApiResponse[ChatSessionOut])
async def get_session(
    session_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    row = await chat_service.get_session(db, member, session_id)
    return ApiResponse(data=ChatSessionOut.model_validate(row))


@router.delete("/sessions/{session_id}", response_model=ApiResponse)
async def delete_session(
    session_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    await chat_service.delete_session(db, member, session_id)
    return ApiResponse(message="deleted")


@router.get("/sessions/{session_id}/messages", response_model=ApiResponse[PageData[ChatMessageOut]])
async def list_messages(
    session_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    items, total = await chat_service.list_messages(
        db, member, session_id, page=page, page_size=page_size
    )
    return ApiResponse(
        data=PageData(
            items=[ChatMessageOut.model_validate(i) for i in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: str,
    body: ChatMessageCreate,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
    ragflow: RagflowRuntimeAdapter = Depends(get_runtime_adapter),
    llm_proxy: LlmProxyClient = Depends(get_llm_proxy_client),
):
    if not body.stream:
        events: list[dict] = []
        async for event in chat_service.send_message_stream(
            db,
            member,
            ragflow,
            llm_proxy,
            session_id=session_id,
            content=body.content,
        ):
            events.append(event)
        completed = next((e for e in events if e.get("event") == "message_completed"), None)
        error = next((e for e in events if e.get("event") == "error"), None)
        if error:
            return ApiResponse(
                code=50000,
                error_code=50000,
                message_key=error.get("data", {}).get("message_key", "errors.system.internal_error"),
                message=error.get("data", {}).get("message", "聊天失败"),
                data=None,
            )
        payload = completed.get("data", {}) if completed else {}
        return ApiResponse(
            data={
                "message_id": payload.get("message_id"),
                "content": payload.get("content"),
                "citations": payload.get("citations", []),
            }
        )

    async def event_stream() -> AsyncIterator[str]:
        async for event in chat_service.send_message_stream(
            db,
            member,
            ragflow,
            llm_proxy,
            session_id=session_id,
            content=body.content,
        ):
            yield chat_service.format_sse_event(event)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
