from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.exceptions import ForbiddenError
from app.core.security import get_current_user, require_tenant_access
from app.models.user_cache import UserCache
from app.schemas.common import ApiResponse
from app.services import agent_automation_service
from app.services.automation_permission import has_automation_permission
from app.services.remote_agent_dispatch_service import cancel_invocation, project_invocation_status

router = APIRouter()
hooks_router = APIRouter()


class AutomationCreateBody(BaseModel):
    name: str
    agent_ref: str
    description: str | None = None
    prompt_template: str = ""
    input_schema: dict[str, Any] = Field(default_factory=dict)
    knowledge_refs: list[str] = Field(default_factory=list)
    connector_binding_refs: list[str] = Field(default_factory=list)
    integration_account_refs: list[str] = Field(default_factory=list)
    manual_run_enabled: bool = True
    concurrency_policy: str = "SKIP_IF_RUNNING"
    max_concurrent_runs: int = 1
    timeout_seconds: int | None = None


class AutomationUpdateBody(BaseModel):
    name: str | None = None
    description: str | None = None
    agent_ref: str | None = None
    prompt_template: str | None = None
    input_schema: dict[str, Any] | None = None
    knowledge_refs: list[str] | None = None
    connector_binding_refs: list[str] | None = None
    integration_account_refs: list[str] | None = None
    manual_run_enabled: bool | None = None
    concurrency_policy: str | None = None
    max_concurrent_runs: int | None = None
    timeout_seconds: int | None = None
    owner_user_id: str | None = None


class StatusBody(BaseModel):
    status: str


class CronTriggerBody(BaseModel):
    cron_expr: str
    timezone: str = "UTC"


class ManualRunBody(BaseModel):
    client_request_id: str
    input: dict[str, Any] = Field(default_factory=dict)


@router.get("")
async def list_automations(
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    rows = await agent_automation_service.list_automations(db, user=user, tenant_id=tenant_id)
    return ApiResponse(data=[agent_automation_service.public_automation(row) for row in rows])


@router.post("")
async def create_automation(
    body: AutomationCreateBody,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    row = await agent_automation_service.create_automation(
        db, user=user, tenant_id=tenant_id, body=body.model_dump()
    )
    return ApiResponse(data=agent_automation_service.public_automation(row))


@router.get("/invocations/{invocation_id}")
async def get_invocation(
    invocation_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    if not has_automation_permission(user.org_role, "automation:view", is_super_admin=user.is_super_admin):
        raise ForbiddenError(message="缺少权限: automation:view", message_key="errors.automation.permission_denied")
    invocation = await agent_automation_service.get_invocation(
        db, tenant_id=tenant_id, invocation_id=invocation_id
    )
    invocation = await project_invocation_status(db, invocation=invocation)
    return ApiResponse(data=agent_automation_service.public_invocation(invocation))


@router.post("/invocations/{invocation_id}/cancel")
async def cancel_invocation_api(
    invocation_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    if not has_automation_permission(user.org_role, "automation:run", is_super_admin=user.is_super_admin):
        raise ForbiddenError(message="缺少权限: automation:run", message_key="errors.automation.permission_denied")
    invocation = await cancel_invocation(
        db, tenant_id=tenant_id, invocation_id=invocation_id, requested_by=user.user_id
    )
    return ApiResponse(data=agent_automation_service.public_invocation(invocation))


@router.get("/{automation_id}")
async def get_automation(
    automation_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    if not has_automation_permission(user.org_role, "automation:view", is_super_admin=user.is_super_admin):
        raise ForbiddenError(message="缺少权限: automation:view", message_key="errors.automation.permission_denied")
    row = await agent_automation_service.get_automation(
        db, tenant_id=tenant_id, automation_id=automation_id
    )
    return ApiResponse(data=agent_automation_service.public_automation(row))


@router.patch("/{automation_id}")
async def update_automation(
    automation_id: str,
    body: AutomationUpdateBody,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    row = await agent_automation_service.update_automation(
        db,
        user=user,
        tenant_id=tenant_id,
        automation_id=automation_id,
        body=body.model_dump(exclude_unset=True),
    )
    return ApiResponse(data=agent_automation_service.public_automation(row))


@router.post("/{automation_id}/status")
async def set_status(
    automation_id: str,
    body: StatusBody,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    row = await agent_automation_service.set_automation_status(
        db,
        user=user,
        tenant_id=tenant_id,
        automation_id=automation_id,
        status=body.status,
    )
    return ApiResponse(data=agent_automation_service.public_automation(row))


@router.post("/{automation_id}/triggers/cron")
async def upsert_cron(
    automation_id: str,
    body: CronTriggerBody,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    trigger = await agent_automation_service.upsert_cron_trigger(
        db,
        user=user,
        tenant_id=tenant_id,
        automation_id=automation_id,
        cron_expr=body.cron_expr,
        timezone_name=body.timezone,
    )
    return ApiResponse(data=agent_automation_service.public_trigger(trigger))


@router.post("/{automation_id}/triggers/webhook")
async def create_webhook(
    automation_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    trigger, secret = await agent_automation_service.create_webhook_trigger(
        db, user=user, tenant_id=tenant_id, automation_id=automation_id
    )
    return ApiResponse(data=agent_automation_service.public_trigger(trigger, webhook_secret=secret))


@router.post("/{automation_id}/runs")
async def manual_run(
    automation_id: str,
    body: ManualRunBody,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    invocation = await agent_automation_service.manual_run(
        db,
        user=user,
        tenant_id=tenant_id,
        automation_id=automation_id,
        client_request_id=body.client_request_id,
        input_payload=body.input,
    )
    return ApiResponse(data=agent_automation_service.public_invocation(invocation))


@hooks_router.post("/automation-hooks/{hook_id}")
async def webhook_ingress(
    hook_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_automation_timestamp: str | None = Header(default=None, alias="X-Automation-Timestamp"),
    x_automation_nonce: str | None = Header(default=None, alias="X-Automation-Nonce"),
    x_automation_signature: str | None = Header(default=None, alias="X-Automation-Signature"),
):
    raw = await request.body()
    try:
        payload = json.loads(raw.decode("utf-8") or "{}")
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    invocation = await agent_automation_service.accept_webhook(
        db,
        hook_id=hook_id,
        raw_body=raw,
        timestamp=x_automation_timestamp or "",
        nonce=x_automation_nonce or "",
        signature=x_automation_signature or "",
        payload=payload,
    )
    return ApiResponse(data=agent_automation_service.public_invocation(invocation))
