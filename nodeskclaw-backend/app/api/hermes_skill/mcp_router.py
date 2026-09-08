from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_org_member
from app.services.mcp_skill_gateway.errors import IDEMPOTENCY_CONFLICT
from app.services.mcp_skill_gateway.handler import dispatch_authenticated

router = APIRouter()


@router.post("/mcp")
async def mcp_jsonrpc(
    body: dict,
    request: Request,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    result = await dispatch_authenticated(body, user_org, db, request_headers=dict(request.headers))
    if (
        isinstance(result, dict)
        and isinstance(result.get("error"), dict)
        and isinstance(result["error"].get("data"), dict)
        and result["error"]["data"].get("errorCode") == IDEMPOTENCY_CONFLICT
    ):
        return JSONResponse(status_code=409, content=result)
    return result
