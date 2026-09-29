from __future__ import annotations

import asyncio
import json
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.runs import (
    _AGENT_STATUS_TO_TERMINAL_EVENT,
    _PUBLIC_TERMINAL_EVENT_TYPES,
    _agent_get,
    _agent_headers,
    _agent_post,
    _get_outbox_entry,
    _is_outbox_undelivered,
    _public_artifact_descriptor,
    _public_run_event,
    _public_run_result,
    _public_run_status,
)
from app.core.config import settings
from app.core.deps import get_db, require_org_member
from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.hermes_skill.hermes_task import HermesTask, TaskStatus
from app.models.hermes_skill.run_dispatch_outbox import RunDispatchStatus
from app.services.expert_gateway.expert_permission_service import ExpertPermissionService
from app.services.hermes_skill.approval_decision_service import (
    ApprovalDecisionContractError,
    submit_approval_decision,
)
from app.services.remote_agent_provider_service import (
    REMOTE_AGENT_TOOL_NAME,
    RemoteAgentProviderService,
    RemoteAgentRouteError,
    public_run_body,
)
from app.services.hermes_skill.task_service import TaskService
from app.services.runtime.pg_notify import pg_notify_service

router = APIRouter(prefix="/remote-agent/runs", tags=["Remote Agent"])


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


def _not_found() -> RemoteAgentRouteError:
    return RemoteAgentRouteError(
        "REMOTE_AGENT_RUN_NOT_FOUND",
        404,
        40402,
        "errors.remote_agent.run_not_found",
        "运行不存在",
    )


async def _load_owned_run(db: AsyncSession, user_id: str, org_id: str, run_id: str):
    task = await db.get(HermesTask, run_id)
    if (
        task is None
        or task.deleted_at is not None
        or task.org_id != org_id
        or task.tool_name != REMOTE_AGENT_TOOL_NAME
    ):
        raise _not_found()
    await TaskService(db).assert_task_access(task, user_id, org_id)
    return task


@router.post("")
async def create_remote_agent_run(
    request: Request,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await ExpertPermissionService.require(db, user.id, org.id, "expert:invoke")
    try:
        payload = await request.json()
        task, _replay = await RemoteAgentProviderService(db).create(
            org_id=org.id,
            user_id=user.id,
            payload=payload,
        )
    except json.JSONDecodeError:
        return _error_response(
            RemoteAgentRouteError(
                "REMOTE_AGENT_CONTEXT_REJECTED",
                400,
                40004,
                "errors.remote_agent.context_rejected",
                "请求包含当前版本不接受的上下文字段",
            )
        )
    except RemoteAgentRouteError as exc:
        return _error_response(exc)
    return public_run_body(task, include_updated_at=False)


@router.get("/{run_id}")
async def get_remote_agent_run(
    run_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await ExpertPermissionService.require(db, user.id, org.id, "expert:view")
    try:
        task = await _load_owned_run(db, user.id, org.id, run_id)
    except RemoteAgentRouteError as exc:
        return _error_response(exc)
    body = public_run_body(task, include_updated_at=True)
    outbox = await _get_outbox_entry(db, run_id, org.id)
    if outbox and outbox.status == RunDispatchStatus.DEAD_LETTER.value:
        body["status"] = "FAILED"
        return body
    if _is_outbox_undelivered(outbox):
        body["status"] = "QUEUED"
        return body
    data = await _agent_get(f"/internal/v1/runs/{run_id}", org_id=org.id, user_id=user.id)
    if str(data.get("run_id") or "") == run_id:
        body["status"] = _public_run_status(data.get("status"), body["status"])
        if data.get("updated_at"):
            body["updated_at"] = data.get("updated_at")
    return body


@router.get("/{run_id}/result")
async def get_remote_agent_result(
    run_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await ExpertPermissionService.require(db, user.id, org.id, "expert:view")
    try:
        await _load_owned_run(db, user.id, org.id, run_id)
    except RemoteAgentRouteError as exc:
        return _error_response(exc)
    outbox = await _get_outbox_entry(db, run_id, org.id)
    if _is_outbox_undelivered(outbox):
        return {
            "run_id": run_id,
            "status": "FAILED" if outbox and outbox.status == RunDispatchStatus.DEAD_LETTER.value else "QUEUED",
            "text": None,
        }
    data = await _agent_get(f"/internal/v1/runs/{run_id}/result", org_id=org.id, user_id=user.id)
    if str(data.get("org_id") or "") != org.id or str(data.get("run_id") or "") != run_id:
        raise ForbiddenError("无权访问该运行", "errors.run.forbidden")
    return _public_run_result(data, run_id)


@router.get("/{run_id}/artifacts")
async def list_remote_agent_artifacts(
    run_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await ExpertPermissionService.require(db, user.id, org.id, "expert:view")
    try:
        await _load_owned_run(db, user.id, org.id, run_id)
    except RemoteAgentRouteError as exc:
        return _error_response(exc)
    outbox = await _get_outbox_entry(db, run_id, org.id)
    if _is_outbox_undelivered(outbox):
        return {"run_id": run_id, "items": []}
    data = await _agent_get(f"/internal/v1/runs/{run_id}/artifacts", org_id=org.id, user_id=user.id)
    if str(data.get("org_id") or "") != org.id or str(data.get("run_id") or "") != run_id:
        raise ForbiddenError("无权访问该运行", "errors.run.forbidden")
    return {
        "run_id": run_id,
        "items": [_public_artifact_descriptor(item) for item in data.get("items") or []],
    }


@router.get("/{run_id}/artifacts/{artifact_id}")
async def download_remote_agent_artifact(
    run_id: str,
    artifact_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await ExpertPermissionService.require(db, user.id, org.id, "expert:view")
    try:
        await _load_owned_run(db, user.id, org.id, run_id)
    except RemoteAgentRouteError as exc:
        return _error_response(exc)
    outbox = await _get_outbox_entry(db, run_id, org.id)
    if _is_outbox_undelivered(outbox):
        raise NotFoundError("Artifact 不存在", "errors.run.artifact_not_found")
    artifacts_data = await _agent_get(
        f"/internal/v1/runs/{run_id}/artifacts",
        org_id=org.id,
        user_id=user.id,
    )
    items = artifacts_data.get("items") or []
    target = next((item for item in items if item.get("artifact_id") == artifact_id), None)
    if not target:
        raise NotFoundError("Artifact 不存在", "errors.run.artifact_not_found")
    url = (
        f"{settings.SKILL_AGENT_BASE_URL.rstrip('/')}"
        f"/internal/v1/runs/{run_id}/artifacts/{artifact_id}/bytes"
    )
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=5.0)) as client:
        response = await client.get(url, headers=_agent_headers(org_id=org.id, user_id=user.id))
        if response.status_code == 404:
            raise NotFoundError("Artifact 不存在", "errors.run.artifact_not_found")
        response.raise_for_status()
        raw_name = target.get("name") or artifact_id
        safe_ascii = raw_name.encode("ascii", "ignore").decode("ascii") or "artifact"
        content_disposition = (
            f'attachment; filename="{safe_ascii}"; filename*=UTF-8\'\'{quote(raw_name)}'
        )
        return Response(
            content=response.content,
            media_type=target.get("content_type")
            or response.headers.get("content-type")
            or "application/octet-stream",
            headers={
                "Content-Disposition": content_disposition,
                "Content-Length": str(len(response.content)),
                "X-Checksum-SHA256": str(target.get("checksum_sha256") or target.get("sha256") or ""),
                "Cache-Control": "no-store",
            },
        )


@router.post("/{run_id}/cancel")
async def cancel_remote_agent_run(
    run_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await ExpertPermissionService.require(db, user.id, org.id, "expert:invoke")
    try:
        task = await _load_owned_run(db, user.id, org.id, run_id)
    except RemoteAgentRouteError as exc:
        return _error_response(exc)
    outbox = await _get_outbox_entry(db, run_id, org.id)
    if _is_outbox_undelivered(outbox):
        if outbox:
            outbox.status = RunDispatchStatus.CANCELLED.value
        task.status = TaskStatus.CANCELLED
        await db.commit()
        return public_run_body(task, include_updated_at=True)
    data = await _agent_post(f"/internal/v1/runs/{run_id}/cancel", org_id=org.id, user_id=user.id)
    if str(data.get("org_id") or "") != org.id or str(data.get("run_id") or "") != run_id:
        raise ForbiddenError("无权访问该运行", "errors.run.forbidden")
    task.status = TaskStatus.CANCELLED
    await db.commit()
    body = public_run_body(task, include_updated_at=True)
    body["status"] = _public_run_status(data.get("status"), "CANCELLED")
    return body


@router.post("/{run_id}/approvals/{approval_id}/decision")
async def decide_remote_agent_approval(
    run_id: str,
    approval_id: str,
    body: dict | None = None,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
):
    user, org = user_org
    await ExpertPermissionService.require(db, user.id, org.id, "expert:invoke")
    try:
        await _load_owned_run(db, user.id, org.id, run_id)
    except RemoteAgentRouteError as exc:
        return _error_response(exc)
    outbox = await _get_outbox_entry(db, run_id, org.id)
    if _is_outbox_undelivered(outbox):
        raise ForbiddenError("未派发的运行无法执行审批", "errors.run.undelivered")
    try:
        return await submit_approval_decision(
            db,
            org_id=org.id,
            user_id=user.id,
            run_id=run_id,
            approval_id=approval_id,
            body=body,
            idempotency_key=idempotency_key,
            require_idempotency_key=True,
            strict_body=True,
            allow_legacy_aliases=False,
            agent_post=_agent_post,
            agent_get=_agent_get,
            public_run_status=_public_run_status,
        )
    except ApprovalDecisionContractError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.status_code * 100,
                "error_code": exc.error_code,
                "message_key": exc.message_key,
                "message": exc.message,
                "data": None,
            },
        )


@router.get("/{run_id}/events")
async def stream_remote_agent_events(
    run_id: str,
    request: Request,
    last_event_id: str | None = None,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
    last_event_id_header: str | None = Header(default=None, alias="Last-Event-ID"),
):
    user, org = user_org
    await ExpertPermissionService.require(db, user.id, org.id, "expert:view")
    try:
        await _load_owned_run(db, user.id, org.id, run_id)
    except RemoteAgentRouteError as exc:
        return _error_response(exc)
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
        persisted_artifact_ids: set[str] = set()
        try:
            while True:
                if await request.is_disconnected():
                    break
                if _is_outbox_undelivered(outbox):
                    yield ": heartbeat\n\n"
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
                for item in payload.get("items") or []:
                    cursor = max(cursor, int(item.get("event_seq") or 0))
                    public_event = _public_run_event(
                        item,
                        run_id,
                        persisted_artifact_ids=persisted_artifact_ids,
                    )
                    if public_event is None:
                        continue
                    if public_event["event_type"] == "artifact.persisted":
                        artifact_id = (public_event.get("payload") or {}).get("artifact_id")
                        if isinstance(artifact_id, str) and artifact_id:
                            persisted_artifact_ids.add(artifact_id)
                    data = json.dumps(public_event, ensure_ascii=False)
                    yield f"id: {public_event['event_id']}\nevent: {public_event['event_type']}\ndata: {data}\n\n"
                    if public_event["event_type"] in _PUBLIC_TERMINAL_EVENT_TYPES:
                        return
                current = await _agent_get(
                    f"/internal/v1/runs/{run_id}",
                    org_id=org.id,
                    user_id=user.id,
                )
                terminal_event_type = _AGENT_STATUS_TO_TERMINAL_EVENT.get(str(current.get("status") or ""))
                if terminal_event_type:
                    public_event = _public_run_event(
                        {
                            "event_type": terminal_event_type,
                            "event_seq": cursor + 1,
                            "timestamp": current.get("updated_at"),
                            "payload": {"phase": str(current.get("status") or "")},
                        },
                        run_id,
                    )
                    if public_event is not None:
                        data = json.dumps(public_event, ensure_ascii=False)
                        yield f"id: {public_event['event_id']}\nevent: {public_event['event_type']}\ndata: {data}\n\n"
                    return
                wake.clear()
                try:
                    await asyncio.wait_for(wake.wait(), timeout=1.0)
                except asyncio.TimeoutError:
                    pass
        finally:
            pg_notify_service.unsubscribe(channel, _on_notify)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store"},
    )
