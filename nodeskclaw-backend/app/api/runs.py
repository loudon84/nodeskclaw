"""Employee-facing Run projection — auth proxy to nodeskclaw-agent."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import httpx
from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_db, require_org_member
from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.base import not_deleted
from app.models.hermes_skill.hermes_task import HermesTask
from app.models.hermes_skill.run_dispatch_outbox import RunDispatchOutbox, RunDispatchStatus
from app.services.hermes_skill.permission_checker import PermissionChecker
from app.services.hermes_skill.runtime_skill_run_service import strip_internal_route_secrets
from app.services.hermes_skill.task_service import TaskService
from app.services.runtime.pg_notify import pg_notify_service
from sqlalchemy import select

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/runs", tags=["Runs"])


def _agent_headers(*, org_id: str | None = None, user_id: str | None = None) -> dict[str, str]:
    headers = {
        "X-Skill-Agent-Token": settings.SKILL_AGENT_INTERNAL_TOKEN,
        "Content-Type": "application/json",
    }
    if org_id:
        headers["X-Exec-Org-Id"] = org_id
    if user_id:
        headers["X-Exec-User-Id"] = user_id
    return headers


async def _agent_get(
    path: str,
    *,
    params: dict[str, Any] | None = None,
    org_id: str | None = None,
    user_id: str | None = None,
) -> Any:
    url = f"{settings.SKILL_AGENT_BASE_URL.rstrip('/')}{path}"
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=5.0)) as client:
        response = await client.get(
            url,
            headers=_agent_headers(org_id=org_id, user_id=user_id),
            params=params,
        )
        if response.status_code == 404:
            raise NotFoundError("Run 不存在", "errors.run.not_found")
        response.raise_for_status()
        return response.json()


async def _agent_post(
    path: str,
    *,
    json_body: dict | None = None,
    org_id: str | None = None,
    user_id: str | None = None,
) -> Any:
    url = f"{settings.SKILL_AGENT_BASE_URL.rstrip('/')}{path}"
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=5.0)) as client:
        response = await client.post(
            url,
            headers=_agent_headers(org_id=org_id, user_id=user_id),
            json=json_body or {},
        )
        if response.status_code == 404:
            raise NotFoundError("Run 不存在", "errors.run.not_found")
        response.raise_for_status()
        return response.json()


async def _authorize_run(db: AsyncSession, user_id: str, org_id: str, run_id: str) -> HermesTask:
    await PermissionChecker.require_permission(db, user_id, org_id, "skill:view")
    task = await TaskService(db).get_task(run_id, org_id)
    await TaskService(db).assert_task_access(task, user_id, org_id)
    return task


async def _get_outbox_entry(db: AsyncSession, run_id: str, org_id: str) -> RunDispatchOutbox | None:
    res = await db.execute(
        select(RunDispatchOutbox).where(
            not_deleted(RunDispatchOutbox),
            RunDispatchOutbox.run_id == run_id,
            RunDispatchOutbox.org_id == org_id,
        ).order_by(RunDispatchOutbox.created_at.desc()).limit(1)
    )
    return res.scalar_one_or_none()


def _is_outbox_undelivered(outbox: RunDispatchOutbox | None) -> bool:
    if not outbox:
        return False
    return outbox.status in (
        RunDispatchStatus.PENDING.value,
        RunDispatchStatus.DEAD_LETTER.value,
        RunDispatchStatus.CANCELLED.value,
    )


@router.get("/{run_id}")
async def get_run(
    run_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    task = await _authorize_run(db, user.id, org.id, run_id)
    outbox = await _get_outbox_entry(db, run_id, org.id)
    if _is_outbox_undelivered(outbox):
        derived_status = "DISPATCH_PENDING" if outbox.status == RunDispatchStatus.PENDING.value else "DISPATCH_FAILED"
        return {
            "code": 0,
            "data": {
                "run_id": task.id,
                "org_id": task.org_id,
                "user_id": task.user_id,
                "tool_name": task.tool_name,
                "status": derived_status,
                "snapshot": {},
                "result": None,
                "attempt_id": None,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "updated_at": task.updated_at.isoformat() if task.updated_at else None,
            },
        }

    data = await _agent_get(f"/internal/v1/runs/{run_id}", org_id=org.id, user_id=user.id)
    if str(data.get("org_id") or "") != org.id or str(data.get("run_id") or "") != run_id:
        raise ForbiddenError("无权访问该 Run", "errors.run.forbidden")
    return {"code": 0, "data": strip_internal_route_secrets(data)}


@router.get("/{run_id}/result")
async def get_run_result(
    run_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    task = await _authorize_run(db, user.id, org.id, run_id)
    outbox = await _get_outbox_entry(db, run_id, org.id)
    if _is_outbox_undelivered(outbox):
        return {"code": 0, "data": None}

    data = await _agent_get(f"/internal/v1/runs/{run_id}/result", org_id=org.id, user_id=user.id)
    if str(data.get("org_id") or "") != org.id or str(data.get("run_id") or "") != run_id:
        raise ForbiddenError("无权访问该 Run", "errors.run.forbidden")
    return {"code": 0, "data": strip_internal_route_secrets(data)}


@router.get("/{run_id}/artifacts")
async def get_run_artifacts(
    run_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    task = await _authorize_run(db, user.id, org.id, run_id)
    outbox = await _get_outbox_entry(db, run_id, org.id)
    if _is_outbox_undelivered(outbox):
        return {"code": 0, "data": {"items": []}}

    data = await _agent_get(f"/internal/v1/runs/{run_id}/artifacts", org_id=org.id, user_id=user.id)
    if str(data.get("org_id") or "") != org.id or str(data.get("run_id") or "") != run_id:
        raise ForbiddenError("无权访问该 Run", "errors.run.forbidden")
    return {"code": 0, "data": data}


@router.get("/{run_id}/artifacts/{artifact_id}/download")
async def download_run_artifact(
    run_id: str,
    artifact_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    task = await _authorize_run(db, user.id, org.id, run_id)
    outbox = await _get_outbox_entry(db, run_id, org.id)
    if _is_outbox_undelivered(outbox):
        raise NotFoundError("Artifact 不存在", "errors.run.artifact_not_found")

    artifacts_data = await _agent_get(f"/internal/v1/runs/{run_id}/artifacts", org_id=org.id, user_id=user.id)
    if str(artifacts_data.get("org_id") or "") != org.id or str(artifacts_data.get("run_id") or "") != run_id:
        raise ForbiddenError("无权访问该 Run", "errors.run.forbidden")
    items = artifacts_data.get("items") or []
    target_art = next((a for a in items if a.get("artifact_id") == artifact_id), None)
    if not target_art:
        raise NotFoundError("Artifact 不存在", "errors.run.artifact_not_found")

    url = f"{settings.SKILL_AGENT_BASE_URL.rstrip('/')}/internal/v1/runs/{run_id}/artifacts/{artifact_id}/bytes"
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=5.0)) as client:
        response = await client.get(url, headers=_agent_headers(org_id=org.id, user_id=user.id))
        if response.status_code == 404:
            raise NotFoundError("Artifact 不存在", "errors.run.artifact_not_found")
        response.raise_for_status()

        from urllib.parse import quote
        raw_name = target_art.get("name") or artifact_id
        safe_ascii = raw_name.encode("ascii", "ignore").decode("ascii") or "artifact"
        encoded_name = quote(raw_name)
        content_disposition = f'attachment; filename="{safe_ascii}"; filename*=UTF-8\'\'{encoded_name}'

        return Response(
            content=response.content,
            media_type=response.headers.get("content-type") or target_art.get("content_type") or "application/octet-stream",
            headers={
                "Content-Disposition": content_disposition,
            },
        )


@router.post("/{run_id}/cancel")
async def cancel_run(
    run_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    task = await _authorize_run(db, user.id, org.id, run_id)
    outbox = await _get_outbox_entry(db, run_id, org.id)
    if _is_outbox_undelivered(outbox):
        if outbox:
            outbox.status = RunDispatchStatus.CANCELLED.value
        task.status = "cancelled"
        await db.commit()
        return {
            "code": 0,
            "data": {
                "run_id": run_id,
                "status": "CANCELLED",
                "org_id": org.id,
            },
        }

    data = await _agent_post(f"/internal/v1/runs/{run_id}/cancel", org_id=org.id, user_id=user.id)
    if str(data.get("org_id") or "") != org.id or str(data.get("run_id") or "") != run_id:
        raise ForbiddenError("无权访问该 Run", "errors.run.forbidden")
    return {"code": 0, "data": data}


@router.post("/{run_id}/resume")
@router.post("/{run_id}/approvals/{approval_id}")
async def resume_or_approve_run(
    run_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
    approval_id: str | None = None,
):
    user, org = user_org
    await PermissionChecker.require_permission(db, user.id, org.id, "skill:invoke")
    task = await _authorize_run(db, user.id, org.id, run_id)
    outbox = await _get_outbox_entry(db, run_id, org.id)
    if _is_outbox_undelivered(outbox):
        raise ForbiddenError("未派发的 Run 无法执行审批或恢复", "errors.run.undelivered")

    path = (
        f"/internal/v1/runs/{run_id}/approvals/{approval_id}"
        if approval_id
        else f"/internal/v1/runs/{run_id}/resume"
    )
    data = await _agent_post(path, org_id=org.id, user_id=user.id)
    if str(data.get("org_id") or "") != org.id or str(data.get("run_id") or "") != run_id:
        raise ForbiddenError("无权访问该 Run", "errors.run.forbidden")
    return {"code": 0, "data": data}


@router.get("/{run_id}/events")
async def stream_run_events(
    run_id: str,
    request: Request,
    last_event_id: str | None = None,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
    last_event_id_header: str | None = Header(default=None, alias="Last-Event-ID"),
):
    user, org = user_org
    task = await _authorize_run(db, user.id, org.id, run_id)
    outbox = await _get_outbox_entry(db, run_id, org.id)

    resume = last_event_id_header or last_event_id or "0"
    try:
        after_seq = int(str(resume).split(":")[-1]) if resume else 0
    except ValueError:
        after_seq = 0

    wake = asyncio.Event()
    channel = f"skill_run_events:{run_id}"

    async def _on_notify(_channel: str, _payload: str) -> None:
        wake.set()

    pg_notify_service.subscribe(channel, _on_notify)

    async def event_generator():
        cursor = after_seq
        try:
            while True:
                if await request.is_disconnected():
                    break

                if _is_outbox_undelivered(outbox):
                    yield f": heartbeat\n\n"
                    wake.clear()
                    try:
                        await asyncio.wait_for(wake.wait(), timeout=1.0)
                    except asyncio.TimeoutError:
                        pass
                    continue

                payload = await _agent_get(
                    f"/internal/v1/runs/{run_id}/events",
                    params={"after_seq": cursor},
                    org_id=org.id,
                    user_id=user.id,
                )
                items = payload.get("items") or []
                for item in items:
                    cursor = max(cursor, int(item.get("event_seq") or 0))
                    event_id = str(item.get("event_seq") or cursor)
                    data = json.dumps(item, ensure_ascii=False)
                    yield f"id: {event_id}\nevent: {item.get('event_type') or 'message'}\ndata: {data}\n\n"
                    if item.get("event_type") in ("run.completed", "run.failed", "run.cancelled"):
                        return
                current = await _agent_get(
                    f"/internal/v1/runs/{run_id}",
                    org_id=org.id,
                    user_id=user.id,
                )
                if current.get("status") in ("COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT") and not items:
                    return
                wake.clear()
                try:
                    await asyncio.wait_for(wake.wait(), timeout=1.0)
                except asyncio.TimeoutError:
                    pass
        finally:
            pg_notify_service.unsubscribe(channel, _on_notify)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
