from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.services.mcp_skill_gateway.constants import MCP_SERVER_NAME
from app.services.mcp_skill_gateway.handler import dispatch
from app.services.mcp_skill_gateway.hermes_docker_tools import list_tools as list_docker_tools

router = APIRouter()


@router.get("/mcp/health", tags=["MCP Skill Gateway"])
async def mcp_health(db: AsyncSession = Depends(get_db)):
    tool_count = len(list_docker_tools())
    return {
        "ok": True,
        "service": MCP_SERVER_NAME,
        "status": "running",
        "tools": {"count": tool_count},
    }


@router.post("/mcp", tags=["MCP Skill Gateway"])
async def mcp_jsonrpc(
    request: Request,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    authorization = request.headers.get("authorization")
    return await dispatch(body, authorization, db)


@router.post("/hermes/mcp", tags=["MCP Skill Gateway"])
async def hermes_mcp_jsonrpc(
    request: Request,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    authorization = request.headers.get("authorization")
    return await dispatch(body, authorization, db)
