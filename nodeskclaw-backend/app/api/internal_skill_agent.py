from __future__ import annotations

import hmac
from datetime import datetime, timedelta, timezone
from typing import Any
from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_db
from app.core.security import create_access_token
from app.models.base import not_deleted
from app.models.hermes_skill.hermes_agent_instance import HermesAgentInstance
from app.services.hermes_external.hermes_docker_binding_service import HermesDockerBindingService
from app.services.hermes_external.hermes_env_parser import parse_env_file

router = APIRouter(prefix="/internal/v1/skill-agent", tags=["Internal Skill Agent"])


def _verify_internal_token(x_skill_agent_token: str | None = Header(default=None, alias="X-Skill-Agent-Token")) -> None:
    expected_curr = settings.SKILL_AGENT_INTERNAL_TOKEN
    expected_prev = settings.SKILL_AGENT_INTERNAL_TOKEN_PREVIOUS
    if not x_skill_agent_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or missing skill agent internal token",
        )
    curr_match = expected_curr and hmac.compare_digest(x_skill_agent_token, expected_curr)
    prev_match = expected_prev and hmac.compare_digest(x_skill_agent_token, expected_prev)
    if not curr_match and not prev_match:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or missing skill agent internal token",
        )


class MintCredentialRequest(BaseModel):
    run_id: str
    attempt_id: str
    instance_id: str | None = None
    agent_profile: str | None = None
    scope: str = "hermes:invoke"
    target: str | None = None


class MintCredentialResponse(BaseModel):
    token: str
    expires_in: int
    gateway_url: str | None = None
    model: str | None = None


@router.post(
    "/credentials/mint",
    response_model=MintCredentialResponse,
    dependencies=[Depends(_verify_internal_token)],
)
async def mint_credential_lease(
    body: MintCredentialRequest,
    db: AsyncSession = Depends(get_db),
    x_exec_org_id: str | None = Header(default=None, alias="X-Exec-Org-Id"),
) -> MintCredentialResponse:
    if not x_exec_org_id:
        raise HTTPException(status_code=400, detail="missing X-Exec-Org-Id header")

    if not body.run_id or not body.run_id.strip() or not body.attempt_id or not body.attempt_id.strip():
        raise HTTPException(status_code=400, detail="missing run_id or attempt_id for credential lease binding")

    record: HermesAgentInstance | None = None
    if body.instance_id:
        result = await db.execute(
            select(HermesAgentInstance).where(
                not_deleted(HermesAgentInstance),
                HermesAgentInstance.id == body.instance_id,
                HermesAgentInstance.org_id == x_exec_org_id,
            )
        )
        record = result.scalar_one_or_none()

    if not record and body.agent_profile:
        record = await HermesDockerBindingService(db).get_by_profile(
            x_exec_org_id, body.agent_profile
        )

    if not record:
        raise HTTPException(status_code=404, detail="hermes agent instance not found")

    gateway_url = str(record.gateway_url).rstrip("/") if record.gateway_url else None
    model_name = None
    if record.env_file:
        try:
            env = parse_env_file(Path(record.env_file), require_gateway_port=False)
            model_name = (env.api_server_model_name or body.agent_profile or "").strip() or None
        except Exception:
            pass

    ttl_secs = settings.SKILL_AGENT_CREDENTIAL_LEASE_TTL_SECONDS
    token_lease = create_access_token(
        subject=f"hermes-lease:{record.id}",
        extra_claims={
            "org_id": x_exec_org_id,
            "run_id": body.run_id.strip(),
            "attempt_id": body.attempt_id.strip(),
            "instance_id": record.id,
            "target": (body.target or record.id).strip(),
            "scope": body.scope,
        },
        expires_delta=timedelta(seconds=ttl_secs),
    )

    return MintCredentialResponse(
        token=token_lease,
        expires_in=ttl_secs,
        gateway_url=gateway_url,
        model=model_name,
    )


class ReviewAttemptAuthorizationRequest(BaseModel):
    attempt_id: str
    run_id: str
    user_id: str
    tool_name: str
    skill_id: str | None = None
    skill_db_id: str | None = None
    agent_id: str | None = None


class ReviewAttemptAuthorizationResponse(BaseModel):
    allowed: bool
    attempt_id: str
    expires_in: int
    reason: str | None = None


@router.post(
    "/authorizations/review",
    response_model=ReviewAttemptAuthorizationResponse,
    dependencies=[Depends(_verify_internal_token)],
)
async def review_attempt_authorization(
    body: ReviewAttemptAuthorizationRequest,
    db: AsyncSession = Depends(get_db),
    x_exec_org_id: str | None = Header(default=None, alias="X-Exec-Org-Id"),
) -> ReviewAttemptAuthorizationResponse:
    if not x_exec_org_id:
        raise HTTPException(status_code=400, detail="missing X-Exec-Org-Id header")

    from app.services.hermes_skill.hermes_skill_authorization_service import (
        HermesSkillAuthorizationService,
    )

    auth_svc = HermesSkillAuthorizationService(db)
    skill_id = body.skill_id or body.tool_name
    skill_db_id = body.skill_db_id or skill_id

    try:
        allowed = await auth_svc.can_invoke(
            org_id=x_exec_org_id,
            user_id=body.user_id,
            skill_db_id=skill_db_id,
            skill_id=skill_id,
            agent_id=body.agent_id,
        )
    except Exception as exc:
        return ReviewAttemptAuthorizationResponse(
            allowed=False,
            attempt_id=body.attempt_id,
            expires_in=0,
            reason=f"authorization check failed: {exc}",
        )

    if not allowed:
        return ReviewAttemptAuthorizationResponse(
            allowed=False,
            attempt_id=body.attempt_id,
            expires_in=0,
            reason="authorization revoked or insufficient invoke permissions",
        )

    ttl = settings.SKILL_AGENT_CREDENTIAL_LEASE_TTL_SECONDS
    return ReviewAttemptAuthorizationResponse(
        allowed=True,
        attempt_id=body.attempt_id,
        expires_in=ttl,
        reason=None,
    )

