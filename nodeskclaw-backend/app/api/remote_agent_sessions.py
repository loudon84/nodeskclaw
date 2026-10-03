from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_org_member
from app.services.expert_gateway.expert_permission_service import ExpertPermissionService
from app.services.remote_agent_provider_service import RemoteAgentRouteError
from app.services.remote_agent_session_proof import RemoteAgentSessionProofService

router = APIRouter(prefix="/remote-agent/sessions", tags=["Remote Agent Sessions"])


def _error_response(exc: RemoteAgentRouteError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.http_status,
        content={
            "code": exc.code,
            "error_code": exc.symbol,
            "message_key": exc.message_key,
            "message": exc.message,
            "data": getattr(exc, "data", None),
        },
    )


@router.get("/{session_ref}")
async def get_remote_agent_session(
    session_ref: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
    expect_agent_ref: str | None = Query(default=None),
    expect_knowledge_ref: list[str] | None = Query(default=None),
    expect_connector_binding_ref: list[str] | None = Query(default=None),
    expect_integration_account_ref: list[str] | None = Query(default=None),
):
    user, org = user_org
    await ExpertPermissionService.require(db, user.id, org.id, "expert:invoke")
    expected = None
    if expect_agent_ref:
        expected = {
            "agent_ref": expect_agent_ref,
            "knowledge_refs": list(expect_knowledge_ref or []),
            "connector_binding_refs": list(expect_connector_binding_ref or []),
            "integration_account_refs": list(expect_integration_account_ref or []),
        }
    try:
        return await RemoteAgentSessionProofService(db).get_proof(
            org.id, user.id, session_ref, expected=expected
        )
    except RemoteAgentRouteError as exc:
        return _error_response(exc)
