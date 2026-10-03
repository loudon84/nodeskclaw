from __future__ import annotations

import hmac
import json

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.remote_agent_runs import _load_owned_run
from app.api.runs import _agent_post
from app.core.config import settings
from app.core.deps import get_db
from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.base import not_deleted
from app.models.org_membership import OrgMembership
from app.models.user import User
from app.services.expert_gateway.expert_permission_service import ExpertPermissionService
from app.services.hermes_skill.permission_checker import PermissionChecker
from app.services.remote_agent_provider_service import (
    RemoteAgentProviderService,
    RemoteAgentRouteError,
    public_run_body,
)
from sqlalchemy import select

router = APIRouter(prefix="/internal/v1/automation/remote-agent", tags=["Internal Automation"])


def _verify_autotask_token(
    x_autotask_internal_token: str | None = Header(default=None, alias="X-Autotask-Internal-Token"),
) -> None:
    expected_curr = settings.AUTOTASK_INTERNAL_TOKEN
    expected_prev = settings.AUTOTASK_INTERNAL_TOKEN_PREVIOUS
    if not x_autotask_internal_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or missing autotask internal token",
        )
    curr_match = expected_curr and hmac.compare_digest(x_autotask_internal_token, expected_curr)
    prev_match = expected_prev and hmac.compare_digest(x_autotask_internal_token, expected_prev)
    if not curr_match and not prev_match:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or missing autotask internal token",
        )


def _error_response(exc: RemoteAgentRouteError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.http_status,
        content={
            "code": exc.code,
            "error_code": exc.symbol,
            "message_key": exc.message_key,
            "message": exc.message,
            "data": None,
        },
    )


class AutomationDispatchBody(BaseModel):
    dispatch_id: str
    invocation_id: str
    org_id: str
    owner_user_id: str
    client_request_id: str
    agent_ref: str
    prompt: str
    knowledge_refs: list[str] = Field(default_factory=list)
    connector_binding_refs: list[str] = Field(default_factory=list)
    integration_account_refs: list[str] = Field(default_factory=list)
    session_ref: str | None = None
    automation_context: dict = Field(default_factory=dict)


async def _assert_owner_active(db: AsyncSession, *, org_id: str, owner_user_id: str) -> None:
    user = await db.get(User, owner_user_id)
    if user is None or not user.is_active or getattr(user, "deleted_at", None) is not None:
        raise RemoteAgentRouteError(
            "AUTOMATION_OWNER_INVALID",
            403,
            40300,
            "errors.automation.owner_invalid",
            "自动化所有者无效",
        )
    membership = await db.execute(
        select(OrgMembership).where(
            OrgMembership.org_id == org_id,
            OrgMembership.user_id == owner_user_id,
            not_deleted(OrgMembership),
        )
    )
    if membership.scalar_one_or_none() is None:
        raise RemoteAgentRouteError(
            "AUTOMATION_OWNER_INVALID",
            403,
            40300,
            "errors.automation.owner_invalid",
            "自动化所有者无效",
        )
    if not await PermissionChecker.has_permission(db, owner_user_id, org_id, "expert:invoke"):
        raise ForbiddenError("缺少权限: expert:invoke", "errors.skill.permission_denied")


@router.post("/runs", dependencies=[Depends(_verify_autotask_token)])
async def create_automation_remote_agent_run(
    body: AutomationDispatchBody,
    db: AsyncSession = Depends(get_db),
):
    try:
        await _assert_owner_active(db, org_id=body.org_id, owner_user_id=body.owner_user_id)
        await ExpertPermissionService.require(db, body.owner_user_id, body.org_id, "expert:invoke")
        payload = {
            "client_request_id": body.client_request_id,
            "agent_ref": body.agent_ref,
            "prompt": body.prompt,
            "knowledge_refs": body.knowledge_refs,
            "connector_binding_refs": body.connector_binding_refs,
            "integration_account_refs": body.integration_account_refs,
            "session_ref": body.session_ref,
        }
        task, replayed = await RemoteAgentProviderService(db).create(
            org_id=body.org_id,
            user_id=body.owner_user_id,
            payload=payload,
        )
        metadata = dict(task.routing_metadata or {})
        if body.automation_context:
            metadata["automation_context"] = body.automation_context
            metadata["automation_dispatch_id"] = body.dispatch_id
            metadata["automation_invocation_id"] = body.invocation_id
            task.routing_metadata = metadata
            await db.commit()
            await db.refresh(task)
        body_out = public_run_body(task, include_updated_at=True)
        body_out["replayed"] = replayed
        return body_out
    except RemoteAgentRouteError as exc:
        return _error_response(exc)
    except ForbiddenError as exc:
        return JSONResponse(
            status_code=403,
            content={
                "code": 40300,
                "error_code": "AUTOMATION_DISPATCH_FORBIDDEN",
                "message_key": exc.message_key,
                "message": exc.message,
                "data": None,
            },
        )


@router.get("/runs/{run_id}", dependencies=[Depends(_verify_autotask_token)])
async def get_automation_remote_agent_run(
    run_id: str,
    org_id: str,
    owner_user_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        task = await _load_owned_run(db, owner_user_id, org_id, run_id)
        return public_run_body(task, include_updated_at=True)
    except RemoteAgentRouteError as exc:
        return _error_response(exc)
    except NotFoundError:
        return _error_response(
            RemoteAgentRouteError(
                "REMOTE_AGENT_RUN_NOT_FOUND",
                404,
                40402,
                "errors.remote_agent.run_not_found",
                "运行不存在",
            )
        )


@router.post("/runs/{run_id}/cancel", dependencies=[Depends(_verify_autotask_token)])
async def cancel_automation_remote_agent_run(
    run_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    try:
        payload = await request.json()
    except json.JSONDecodeError:
        payload = {}
    org_id = str(payload.get("org_id") or "")
    owner_user_id = str(payload.get("owner_user_id") or "")
    if not org_id or not owner_user_id:
        return JSONResponse(
            status_code=400,
            content={
                "code": 40004,
                "error_code": "REMOTE_AGENT_CONTEXT_REJECTED",
                "message_key": "errors.remote_agent.context_rejected",
                "message": "请求包含当前版本不接受的上下文字段",
                "data": None,
            },
        )
    try:
        await _load_owned_run(db, owner_user_id, org_id, run_id)
        data = await _agent_post(f"/internal/v1/runs/{run_id}/cancel", org_id=org_id, user_id=owner_user_id)
        return data
    except RemoteAgentRouteError as exc:
        return _error_response(exc)
    except NotFoundError:
        return _error_response(
            RemoteAgentRouteError(
                "REMOTE_AGENT_RUN_NOT_FOUND",
                404,
                40402,
                "errors.remote_agent.run_not_found",
                "运行不存在",
            )
        )
