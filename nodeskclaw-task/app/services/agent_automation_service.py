from __future__ import annotations

import hashlib
import json
import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from croniter import croniter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError

logger = logging.getLogger("automation.integration_validate")
from app.models.agent_automation import (
    AgentAutomation,
    AutomationInvocation,
    AutomationTrigger,
    AutomationWebhookNonce,
    RemoteAgentDispatchJob,
)
from app.models.base import not_deleted
from app.models.user_cache import UserCache
from app.services.automation_permission import can_manage_automation, has_automation_permission
from app.services.prompt_renderer import map_rpa_output_to_input, render_prompt_template
from app.services.webhook_hmac import (
    hash_webhook_secret,
    open_webhook_secret,
    seal_webhook_secret,
    verify_webhook_signature,
)

ACTIVE_INVOCATION_STATUSES = frozenset({
    "DISPATCHING",
    "SUBMITTED",
    "RUNNING",
    "WAITING_APPROVAL",
    "RETRYING",
    "PENDING",
})
SEMANTIC_FIELDS = frozenset({
    "agent_ref",
    "prompt_template",
    "input_schema",
    "knowledge_refs",
    "connector_binding_refs",
    "integration_account_refs",
})
REMOTE_MAPPER = "RPA_OUTPUT_TO_REMOTE_AGENT_INPUT_V1"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _require_perm(user: UserCache, permission: str) -> None:
    if not has_automation_permission(
        user.org_role, permission, is_super_admin=user.is_super_admin
    ):
        raise ForbiddenError(
            message=f"缺少权限: {permission}",
            message_key="errors.automation.permission_denied",
        )


async def create_automation(
    db: AsyncSession,
    *,
    user: UserCache,
    tenant_id: str,
    body: dict[str, Any],
) -> AgentAutomation:
    _require_perm(user, "automation:run")
    name = str(body.get("name") or "").strip()
    agent_ref = str(body.get("agent_ref") or "").strip()
    if not name or not agent_ref:
        raise BadRequestError(
            message="name 与 agent_ref 必填",
            message_key="errors.automation.input_invalid",
        )
    row = AgentAutomation(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        name=name,
        description=body.get("description"),
        owner_user_id=user.user_id,
        agent_ref=agent_ref,
        status="DRAFT",
        generation=1,
        prompt_template=str(body.get("prompt_template") or ""),
        input_schema=dict(body.get("input_schema") or {}),
        knowledge_refs=list(body.get("knowledge_refs") or []),
        connector_binding_refs=list(body.get("connector_binding_refs") or []),
        integration_account_refs=list(body.get("integration_account_refs") or []),
        manual_run_enabled=bool(body.get("manual_run_enabled", True)),
        concurrency_policy=str(body.get("concurrency_policy") or "SKIP_IF_RUNNING"),
        max_concurrent_runs=int(body.get("max_concurrent_runs") or 1),
        timeout_seconds=body.get("timeout_seconds"),
        created_by=user.user_id,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def list_automations(
    db: AsyncSession,
    *,
    user: UserCache,
    tenant_id: str,
) -> list[AgentAutomation]:
    _require_perm(user, "automation:view")
    rows = (
        await db.execute(
            select(AgentAutomation)
            .where(AgentAutomation.tenant_id == tenant_id, not_deleted(AgentAutomation))
            .order_by(AgentAutomation.created_at.desc())
        )
    ).scalars().all()
    return list(rows)


async def get_automation(db: AsyncSession, *, tenant_id: str, automation_id: str) -> AgentAutomation:
    row = (
        await db.execute(
            select(AgentAutomation).where(
                AgentAutomation.id == automation_id,
                AgentAutomation.tenant_id == tenant_id,
                not_deleted(AgentAutomation),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError(
            message="自动化不存在",
            message_key="errors.automation.not_found",
        )
    return row


async def update_automation(
    db: AsyncSession,
    *,
    user: UserCache,
    tenant_id: str,
    automation_id: str,
    body: dict[str, Any],
) -> AgentAutomation:
    row = await get_automation(db, tenant_id=tenant_id, automation_id=automation_id)
    if not can_manage_automation(
        org_role=user.org_role,
        user_id=user.user_id,
        owner_user_id=row.owner_user_id,
        is_super_admin=user.is_super_admin,
    ):
        raise ForbiddenError(
            message="缺少权限: automation:manage",
            message_key="errors.automation.permission_denied",
        )
    bumped = False
    for key in (
        "name",
        "description",
        "agent_ref",
        "prompt_template",
        "input_schema",
        "knowledge_refs",
        "connector_binding_refs",
        "integration_account_refs",
        "manual_run_enabled",
        "concurrency_policy",
        "max_concurrent_runs",
        "timeout_seconds",
    ):
        if key not in body:
            continue
        setattr(row, key, body[key])
        if key in SEMANTIC_FIELDS:
            bumped = True
    if "owner_user_id" in body:
        if not has_automation_permission(
            user.org_role, "automation:manage", is_super_admin=user.is_super_admin
        ) and user.user_id != row.owner_user_id:
            raise ForbiddenError(
                message="缺少权限变更 owner",
                message_key="errors.automation.permission_denied",
            )
        row.owner_user_id = str(body["owner_user_id"])
    if bumped:
        row.generation = int(row.generation) + 1
    if "integration_account_refs" in body:
        await validate_owner_integration_accounts(
            org_id=tenant_id,
            owner_user_id=row.owner_user_id,
            integration_account_refs=list(row.integration_account_refs or []),
        )
    await db.commit()
    await db.refresh(row)
    return row


async def set_automation_status(
    db: AsyncSession,
    *,
    user: UserCache,
    tenant_id: str,
    automation_id: str,
    status: str,
) -> AgentAutomation:
    row = await get_automation(db, tenant_id=tenant_id, automation_id=automation_id)
    if not can_manage_automation(
        org_role=user.org_role,
        user_id=user.user_id,
        owner_user_id=row.owner_user_id,
        is_super_admin=user.is_super_admin,
    ):
        raise ForbiddenError(
            message="缺少权限: automation:manage",
            message_key="errors.automation.permission_denied",
        )
    if status not in {"ENABLED", "DISABLED", "DRAFT"}:
        raise BadRequestError(
            message="非法状态",
            message_key="errors.automation.input_invalid",
        )
    if status == "ENABLED":
        await validate_owner_integration_accounts(
            org_id=tenant_id,
            owner_user_id=row.owner_user_id,
            integration_account_refs=list(row.integration_account_refs or []),
        )
    row.status = status
    await db.commit()
    await db.refresh(row)
    return row


async def validate_owner_integration_accounts(
    *,
    org_id: str,
    owner_user_id: str,
    integration_account_refs: list[str],
) -> None:
    if not integration_account_refs:
        return
    if not settings.AUTOTASK_INTERNAL_TOKEN:
        raise BadRequestError(
            message="缺少内部校验令牌，无法验证共享账号",
            message_key="errors.automation.integration_validate_unavailable",
        )
    url = (
        f"{settings.NODESKCLAW_BACKEND_URL.rstrip('/')}"
        "/api/v1/internal/v1/automation/remote-agent/integration-accounts/validate"
    )
    try:
        async with httpx.AsyncClient(timeout=30.0) as http:
            response = await http.post(
                url,
                headers={"X-Autotask-Internal-Token": settings.AUTOTASK_INTERNAL_TOKEN},
                json={
                    "org_id": org_id,
                    "owner_user_id": owner_user_id,
                    "integration_account_refs": integration_account_refs,
                },
            )
    except httpx.HTTPError as exc:
        logger.warning("automation.integration_validate.transport_failed", exc_info=exc)
        raise BadRequestError(
            message="无法验证共享账号可用性",
            message_key="errors.automation.integration_validate_unavailable",
        ) from exc
    if response.status_code >= 400:
        body: dict[str, Any] = {}
        try:
            body = response.json()
        except Exception:
            body = {}
        raise BadRequestError(
            message=str(body.get("message") or "共享账号不可用"),
            message_key=str(body.get("message_key") or "errors.automation.integration_account_invalid"),
        )


async def upsert_cron_trigger(
    db: AsyncSession,
    *,
    user: UserCache,
    tenant_id: str,
    automation_id: str,
    cron_expr: str,
    timezone_name: str,
) -> AutomationTrigger:
    automation = await get_automation(db, tenant_id=tenant_id, automation_id=automation_id)
    if not can_manage_automation(
        org_role=user.org_role,
        user_id=user.user_id,
        owner_user_id=automation.owner_user_id,
        is_super_admin=user.is_super_admin,
    ):
        raise ForbiddenError(
            message="缺少权限: automation:manage",
            message_key="errors.automation.permission_denied",
        )
    try:
        base = datetime.now(UTC)
        iterator = croniter(cron_expr, base)
        next_fire = iterator.get_next(datetime)
    except (ValueError, KeyError, TypeError) as exc:
        raise BadRequestError(
            message="非法 cron 或时区",
            message_key="errors.automation.trigger_invalid",
        ) from exc
    existing = (
        await db.execute(
            select(AutomationTrigger).where(
                AutomationTrigger.automation_id == automation_id,
                AutomationTrigger.trigger_type == "CRON",
                not_deleted(AutomationTrigger),
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        existing = AutomationTrigger(
            id=str(uuid.uuid4()),
            automation_id=automation_id,
            trigger_type="CRON",
            status="ENABLED",
            timezone=timezone_name,
            cron_expr=cron_expr,
            next_fire_at=next_fire,
        )
        db.add(existing)
    else:
        existing.timezone = timezone_name
        existing.cron_expr = cron_expr
        existing.next_fire_at = next_fire
        existing.status = "ENABLED"
    await db.commit()
    await db.refresh(existing)
    return existing


async def create_webhook_trigger(
    db: AsyncSession,
    *,
    user: UserCache,
    tenant_id: str,
    automation_id: str,
) -> tuple[AutomationTrigger, str]:
    automation = await get_automation(db, tenant_id=tenant_id, automation_id=automation_id)
    if not can_manage_automation(
        org_role=user.org_role,
        user_id=user.user_id,
        owner_user_id=automation.owner_user_id,
        is_super_admin=user.is_super_admin,
    ):
        raise ForbiddenError(
            message="缺少权限: automation:manage",
            message_key="errors.automation.permission_denied",
        )
    secret = secrets.token_urlsafe(32)
    mapping = {"_secret_ciphertext": seal_webhook_secret(secret)}
    trigger = AutomationTrigger(
        id=str(uuid.uuid4()),
        automation_id=automation_id,
        trigger_type="WEBHOOK",
        status="ENABLED",
        webhook_secret_hash=hash_webhook_secret(secret),
        webhook_key_id=f"key_{secrets.token_hex(8)}",
        prompt_mapping=mapping,
    )
    db.add(trigger)
    await db.commit()
    await db.refresh(trigger)
    return trigger, secret


async def _count_active(db: AsyncSession, automation_id: str) -> int:
    rows = (
        await db.execute(
            select(AutomationInvocation).where(
                AutomationInvocation.automation_id == automation_id,
                AutomationInvocation.status.in_(ACTIVE_INVOCATION_STATUSES),
                not_deleted(AutomationInvocation),
            )
        )
    ).scalars().all()
    return len(rows)


async def _create_invocation_and_job(
    db: AsyncSession,
    *,
    automation: AgentAutomation,
    trigger_type: str,
    idempotency_key: str,
    input_payload: dict,
    trigger_id: str | None = None,
    source_event_id: str | None = None,
    scheduled_fire_at: datetime | None = None,
    status: str = "PENDING",
    commit: bool = True,
) -> AutomationInvocation:
    existing = (
        await db.execute(
            select(AutomationInvocation).where(
                AutomationInvocation.automation_id == automation.id,
                AutomationInvocation.idempotency_key == idempotency_key,
                not_deleted(AutomationInvocation),
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    final_status = status
    if (
        automation.concurrency_policy == "SKIP_IF_RUNNING"
        and status not in {"MISSED", "SKIPPED_CONCURRENCY"}
        and await _count_active(db, automation.id) >= int(automation.max_concurrent_runs or 1)
    ):
        final_status = "SKIPPED_CONCURRENCY"

    try:
        rendered = render_prompt_template(automation.prompt_template or "", input_payload)
    except ValueError as exc:
        raise BadRequestError(
            message=str(exc),
            message_key="errors.automation.input_invalid",
        ) from exc
    invocation = AutomationInvocation(
        id=str(uuid.uuid4()),
        automation_id=automation.id,
        automation_generation=int(automation.generation),
        trigger_id=trigger_id,
        trigger_type=trigger_type,
        source_event_id=source_event_id,
        scheduled_fire_at=scheduled_fire_at,
        idempotency_key=idempotency_key,
        owner_user_id_snapshot=automation.owner_user_id,
        input_payload=input_payload,
        input_payload_hash=_sha(json.dumps(input_payload, sort_keys=True, ensure_ascii=False)),
        rendered_prompt=rendered,
        rendered_prompt_hash=_sha(rendered),
        status=final_status,
    )
    db.add(invocation)
    await db.flush()
    if final_status == "PENDING":
        db.add(
            RemoteAgentDispatchJob(
                id=str(uuid.uuid4()),
                tenant_id=automation.tenant_id,
                invocation_id=invocation.id,
                automation_id=automation.id,
                status="PENDING",
                attempt_count=0,
                max_attempts=int(settings.SUCCESSOR_JOB_MAX_ATTEMPTS or 10),
                next_attempt_at=datetime.now(UTC),
            )
        )
    if commit:
        await db.commit()
        await db.refresh(invocation)
    return invocation


async def manual_run(
    db: AsyncSession,
    *,
    user: UserCache,
    tenant_id: str,
    automation_id: str,
    client_request_id: str,
    input_payload: dict | None = None,
) -> AutomationInvocation:
    _require_perm(user, "automation:run")
    automation = await get_automation(db, tenant_id=tenant_id, automation_id=automation_id)
    if automation.status != "ENABLED":
        raise BadRequestError(
            message="自动化未启用",
            message_key="errors.automation.disabled",
        )
    if not automation.manual_run_enabled:
        raise BadRequestError(
            message="未开启手动运行",
            message_key="errors.automation.disabled",
        )
    key = str(client_request_id or "").strip()
    if not key or len(key) > 128:
        raise BadRequestError(
            message="client_request_id 必须是 1 到 128 个字符",
            message_key="errors.automation.input_invalid",
        )
    return await _create_invocation_and_job(
        db,
        automation=automation,
        trigger_type="MANUAL",
        idempotency_key=key,
        input_payload=dict(input_payload or {}),
    )


async def accept_webhook(
    db: AsyncSession,
    *,
    hook_id: str,
    raw_body: bytes,
    timestamp: str,
    nonce: str,
    signature: str,
    payload: dict,
) -> AutomationInvocation:
    trigger = (
        await db.execute(
            select(AutomationTrigger).where(
                AutomationTrigger.id == hook_id,
                AutomationTrigger.trigger_type == "WEBHOOK",
                not_deleted(AutomationTrigger),
            )
        )
    ).scalar_one_or_none()
    if trigger is None or trigger.status != "ENABLED":
        raise NotFoundError(
            message="Webhook 不存在",
            message_key="errors.automation.trigger_invalid",
        )
    mapping = dict(trigger.prompt_mapping or {})
    secret = open_webhook_secret(str(mapping.get("_secret_ciphertext") or ""))
    if not secret or hash_webhook_secret(secret) != (trigger.webhook_secret_hash or ""):
        raise ForbiddenError(
            message="Webhook 认证失败",
            message_key="errors.automation.webhook_auth_failed",
        )
    auth_error = verify_webhook_signature(
        secret=secret,
        timestamp=timestamp,
        nonce=nonce,
        signature=signature,
        raw_body=raw_body,
    )
    if auth_error:
        raise ForbiddenError(
            message="Webhook 认证失败",
            message_key="errors.automation.webhook_auth_failed",
        )
    source_event_id = str(payload.get("source_event_id") or "").strip()
    if not source_event_id:
        raise BadRequestError(
            message="source_event_id 必填",
            message_key="errors.automation.input_invalid",
        )
    now = datetime.now(UTC)
    expires = now + timedelta(seconds=600)
    existing_nonce = (
        await db.execute(
            select(AutomationWebhookNonce).where(
                AutomationWebhookNonce.trigger_id == trigger.id,
                AutomationWebhookNonce.nonce == nonce,
                not_deleted(AutomationWebhookNonce),
            )
        )
    ).scalar_one_or_none()
    if existing_nonce is not None:
        raise ForbiddenError(
            message="Webhook 重放被拒绝",
            message_key="errors.automation.webhook_replay",
        )
    db.add(
        AutomationWebhookNonce(
            id=str(uuid.uuid4()),
            trigger_id=trigger.id,
            nonce=nonce,
            expires_at=expires,
        )
    )
    automation = (
        await db.execute(
            select(AgentAutomation).where(
                AgentAutomation.id == trigger.automation_id,
                not_deleted(AgentAutomation),
            )
        )
    ).scalar_one_or_none()
    if automation is None:
        raise NotFoundError(
            message="自动化不存在",
            message_key="errors.automation.not_found",
        )
    if automation.status != "ENABLED":
        raise BadRequestError(
            message="自动化未启用",
            message_key="errors.automation.disabled",
        )
    clean = {k: v for k, v in payload.items() if k != "source_event_id"}
    return await _create_invocation_and_job(
        db,
        automation=automation,
        trigger_type="WEBHOOK",
        idempotency_key=f"{trigger.id}:{source_event_id}",
        input_payload=clean,
        trigger_id=trigger.id,
        source_event_id=source_event_id,
    )


async def fire_due_cron_triggers(db: AsyncSession, *, now: datetime | None = None) -> list[str]:
    current = now or datetime.now(UTC)
    grace = timedelta(seconds=int(settings.MISFIRE_GRACE_SECONDS or 300))
    result = await db.execute(
        select(AutomationTrigger)
        .where(
            AutomationTrigger.trigger_type == "CRON",
            AutomationTrigger.status == "ENABLED",
            AutomationTrigger.next_fire_at.is_not(None),
            AutomationTrigger.next_fire_at <= current,
            not_deleted(AutomationTrigger),
        )
        .with_for_update(skip_locked=True)
        .limit(20)
    )
    created: list[str] = []
    for trigger in result.scalars().all():
        automation = (
            await db.execute(
                select(AgentAutomation).where(
                    AgentAutomation.id == trigger.automation_id,
                    not_deleted(AgentAutomation),
                )
            )
        ).scalar_one_or_none()
        if automation is None or automation.status != "ENABLED":
            try:
                iterator = croniter(trigger.cron_expr or "", current)
                trigger.next_fire_at = iterator.get_next(datetime)
            except Exception:
                trigger.status = "DISABLED"
            await db.commit()
            continue
        scheduled = trigger.next_fire_at
        assert scheduled is not None
        if scheduled.tzinfo is None:
            scheduled = scheduled.replace(tzinfo=UTC)
        late = current - scheduled
        status = "PENDING" if late <= grace else "MISSED"
        invocation = await _create_invocation_and_job(
            db,
            automation=automation,
            trigger_type="CRON",
            idempotency_key=f"{trigger.id}:{scheduled.astimezone(UTC).isoformat()}",
            input_payload={},
            trigger_id=trigger.id,
            scheduled_fire_at=scheduled,
            status=status,
            commit=False,
        )
        created.append(invocation.id)
        try:
            iterator = croniter(trigger.cron_expr or "", current)
            trigger.next_fire_at = iterator.get_next(datetime)
        except Exception:
            trigger.status = "DISABLED"
        trigger.last_fired_at = current
        await db.commit()
    return created


async def create_successor_invocation(
    db: AsyncSession,
    *,
    tenant_id: str,
    target_automation_id: str,
    source_run_id: str,
    input_mapper: str,
    source_output: dict,
    commit: bool = True,
) -> AutomationInvocation:
    if input_mapper != REMOTE_MAPPER:
        raise BadRequestError(
            message="后继映射器不受支持",
            message_key="errors.automation.input_invalid",
        )
    automation = await get_automation(db, tenant_id=tenant_id, automation_id=target_automation_id)
    if automation.status != "ENABLED":
        raise BadRequestError(
            message="自动化未启用",
            message_key="errors.automation.disabled",
        )
    mapped = map_rpa_output_to_input(source_output, automation.input_schema or {})
    return await _create_invocation_and_job(
        db,
        automation=automation,
        trigger_type="SUCCESSOR",
        idempotency_key=f"{source_run_id}:{target_automation_id}",
        input_payload=mapped,
        commit=commit,
    )


async def get_invocation(
    db: AsyncSession,
    *,
    tenant_id: str,
    invocation_id: str,
) -> AutomationInvocation:
    row = (
        await db.execute(
            select(AutomationInvocation)
            .join(AgentAutomation, AgentAutomation.id == AutomationInvocation.automation_id)
            .where(
                AutomationInvocation.id == invocation_id,
                AgentAutomation.tenant_id == tenant_id,
                not_deleted(AutomationInvocation),
                not_deleted(AgentAutomation),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError(
            message="调用不存在",
            message_key="errors.automation.invocation_not_found",
        )
    return row


def public_automation(row: AgentAutomation) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "description": row.description,
        "owner_user_id": row.owner_user_id,
        "agent_ref": row.agent_ref,
        "status": row.status,
        "generation": row.generation,
        "concurrency_policy": row.concurrency_policy,
        "max_concurrent_runs": row.max_concurrent_runs,
        "manual_run_enabled": row.manual_run_enabled,
        "knowledge_refs": list(row.knowledge_refs or []),
        "connector_binding_refs": list(row.connector_binding_refs or []),
        "integration_account_refs": list(row.integration_account_refs or []),
    }


def public_invocation(row: AutomationInvocation) -> dict:
    return {
        "id": row.id,
        "automation_id": row.automation_id,
        "automation_generation": row.automation_generation,
        "trigger_type": row.trigger_type,
        "status": row.status,
        "remote_agent_run_id": row.remote_agent_run_id,
        "error_code": row.error_code,
        "idempotency_key": row.idempotency_key,
    }


def public_trigger(row: AutomationTrigger, *, webhook_secret: str | None = None) -> dict:
    body = {
        "id": row.id,
        "automation_id": row.automation_id,
        "trigger_type": row.trigger_type,
        "status": row.status,
        "timezone": row.timezone,
        "cron_expr": row.cron_expr,
        "webhook_key_id": row.webhook_key_id,
        "next_fire_at": row.next_fire_at.isoformat() if row.next_fire_at else None,
    }
    if webhook_secret:
        body["webhook_secret"] = webhook_secret
        body["hook_id"] = row.id
    return body
