from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internal_skill_agent import _verify_internal_token
from app.core.config import settings
from app.core.deps import get_db
from app.core.exceptions import ForbiddenError
from app.services.hermes_skill.public_attachment_service import PublicAttachmentContractError
from app.services.remote_acp.capability import verify_execution_capability
from app.services.remote_acp.errors import RemoteAcpError
from app.services.remote_acp.run_context import build_run_context

router = APIRouter(prefix="/internal/remote-acp", tags=["Internal Remote ACP"])


class RunContextBody(BaseModel):
    org_id: str
    user_id: str
    agent_ref: str
    session_id: str
    attachment_refs: list[str] = Field(default_factory=list)
    knowledge_refs: list[str] = Field(default_factory=list)
    prompt_digest: str | None = None


@router.post("/run-context", dependencies=[Depends(_verify_internal_token)])
async def create_run_context(
    body: RunContextBody,
    db: AsyncSession = Depends(get_db),
    capability: str | None = Header(default=None, alias="X-NodeSkClaw-Execution-Capability"),
    x_trace_id: str | None = Header(default=None, alias="X-Trace-Id"),
) -> dict[str, Any]:
    claims, error = verify_execution_capability(
        capability,
        current_token=settings.SKILL_AGENT_INTERNAL_TOKEN,
        previous_token=settings.SKILL_AGENT_INTERNAL_TOKEN_PREVIOUS,
    )
    if not claims:
        raise ForbiddenError("capability invalid", "errors.acp.capability_invalid")
    if error:
        raise ForbiddenError(error, "errors.acp.capability_invalid")
    if (
        str(claims.get("org_id")) != body.org_id
        or str(claims.get("user_id")) != body.user_id
        or str(claims.get("agent_ref")) != body.agent_ref
    ):
        raise ForbiddenError("capability subject mismatch", "errors.acp.context_revalidation_denied")
    try:
        data = await build_run_context(
            db,
            org_id=body.org_id,
            user_id=body.user_id,
            agent_ref=body.agent_ref,
            session_id=body.session_id,
            attachment_refs=body.attachment_refs,
            knowledge_refs=body.knowledge_refs,
        )
    except RemoteAcpError as exc:
        return exc.to_response()
    except PublicAttachmentContractError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error_code": exc.error_code,
                "message_key": exc.message_key,
                "message": exc.message,
            },
        )
    return {"code": 0, "data": data, "trace_id": x_trace_id}
