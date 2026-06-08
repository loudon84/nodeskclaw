from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_org_member
from app.services.mcp_skill_gateway.handler import dispatch_authenticated

router = APIRouter()


@router.post("/mcp")
async def mcp_jsonrpc(
    body: dict,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    return await dispatch_authenticated(body, user_org, db)
