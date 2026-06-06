import asyncio
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_api_key_or_jwt, require_org_member
from app.models.instance import Instance
from app.models.base import not_deleted
from app.services.gateway.sse_manager import SSEManager

logger = logging.getLogger(__name__)

router = APIRouter()

_sse_manager = SSEManager()

_HEARTBEAT_INTERVAL = 30


@router.get("/sse/{instance_id}", tags=["Gateway - SSE"])
async def sse_connect(
    instance_id: str,
    request: Request,
    auth_result=Depends(get_api_key_or_jwt),
    db: AsyncSession = Depends(get_db),
):
    user, org, auth_type, auth_key_id = auth_result

    result = await db.execute(
        select(Instance).where(
            Instance.id == instance_id,
            not_deleted(Instance),
            Instance.org_id == org.id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=403,
            detail={"error_code": 40300, "message_key": "errors.mcp.access_denied", "message": "无权访问该实例"},
        )

    client_id = user.id if user else f"apikey:{auth_key_id}"
    connection_id = await _sse_manager.register_connection(
        client_id=client_id,
        upstream_server_id="",
        instance_id=instance_id,
    )

    event_queue: asyncio.Queue[str | None] = asyncio.Queue()

    async def event_generator():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(event_queue.get(), timeout=_HEARTBEAT_INTERVAL)
                    if event is None:
                        break
                    yield event
                except asyncio.TimeoutError:
                    yield ":ping\n\n"
        finally:
            await _sse_manager.remove_connection(connection_id)
            logger.info("SSE 连接 %s 已断开", connection_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
