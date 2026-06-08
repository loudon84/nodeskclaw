from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.services.mcp_skill_gateway.handler import dispatch

router = APIRouter()


@router.get("/mcp/health", tags=["MCP Skill Gateway"])
async def mcp_health():
    return {"status": "ok"}


@router.post("/mcp", tags=["MCP Skill Gateway"])
async def mcp_jsonrpc(
    request: Request,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    authorization = request.headers.get("authorization")
    return await dispatch(body, authorization, db)
