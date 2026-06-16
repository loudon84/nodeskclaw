from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_org_member
from app.services.mcp_skill_gateway.handler import dispatch_authenticated

router = APIRouter()


@router.post("/mcp")
async def mcp_jsonrpc(
    body: dict,
    request: Request,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    return await dispatch_authenticated(body, user_org, db, request_headers=dict(request.headers))
