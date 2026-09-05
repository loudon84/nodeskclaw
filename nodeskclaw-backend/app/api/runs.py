"""Employee-facing Run projection — auth proxy to nodeskclaw-agent."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_db, require_org_member
from app.core.exceptions import AppException, ForbiddenError, NotFoundError
from app.models.base import not_deleted
from app.models.connector.edge_job import EdgeJob, EdgeJobStatus
from app.models.hermes_skill.hermes_task import HermesTask
from app.models.hermes_skill.run_dispatch_outbox import RunDispatchOutbox, RunDispatchStatus
from app.services.hermes_skill.permission_checker import PermissionChecker
from app.services.hermes_skill.task_service import TaskService
from app.services.runtime.pg_notify import pg_notify_service
from sqlalchemy import select, update

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/runs", tags=["Runs"])

_PUBLIC_RUN_STATUSES = frozenset(
    {
        "CREATED",
        "QUEUED",
        "PREPARING",
        "RUNNING",
        "WAITING_APPROVAL",
        "RESUMING",
        "CANCELLING",
        "COMPLETED",
        "FAILED",
        "CANCELLED",
        "TIMED_OUT",
    }
)


_PUBLIC_TERMINAL_EVENT_TYPES = frozenset(
    {
        "run.completed",
        "run.failed",
        "run.cancelled",
        "run.timed_out",
    }
)
_AGENT_STATUS_TO_TERMINAL_EVENT = {
    "COMPLETED": "run.completed",
    "FAILED": "run.failed",
    "CANCELLED": "run.cancelled",
    "TIMED_OUT": "run.timed_out",
}


def _public_run_status(value: Any, fallback: str = "FAILED") -> str:
    normalized = str(value or "").upper()
    if normalized == "DISPATCH_PENDING":
        return "QUEUED"
    if normalized == "DISPATCH_FAILED":
        return "FAILED"
    return normalized if normalized in _PUBLIC_RUN_STATUSES else fallback


def _public_run_view(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": str(data["run_id"]),
        "tool_name": str(data["tool_name"]),
        "status": _public_run_status(data.get("status")),
        "created_at": data.get("created_at"),
        "updated_at": data.get("updated_at"),
    }


def _public_run_result(data: dict[str, Any], run_id: str) -> dict[str, Any]:
    error = data.get("error") if isinstance(data.get("error"), dict) else {}
    text = next(
        (
            value
            for value in (data.get("result_content"), data.get("content"), data.get("message"))
            if isinstance(value, str)
        ),
        None,
    )
    return {
        "run_id": run_id,
        "status": _public_run_status(data.get("status"), fallback="QUEUED"),
        "text": text,
        "error_code": data.get("error_code") or error.get("code"),
        "error_message": data.get("error_message") or error.get("message"),
    }


def _public_artifact_descriptor(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifact_id": str(data.get("artifact_id") or data.get("id")),
        "name": str(data.get("name") or data.get("file_name") or "artifact"),
        "content_type": data.get("content_type"),
        "size_bytes": int(data.get("size_bytes") or 0),
        "checksum_sha256": str(data.get("checksum_sha256") or data.get("sha256") or ""),
    }


_TOOL_CALL_STATUSES = frozenset({"started", "completed", "failed"})


# @lat: [[decisions/skill-platform-execution#Employee Contract]]
def _public_run_event(data: dict[str, Any], run_id: str) -> dict[str, Any] | None:
    event_type = str(data.get("event_type") or "")
    event_seq = int(data.get("event_seq") or 0)
    payload = data.get("payload") if isinstance(data.get("payload"), dict) else {}
    event = {
        "event_id": f"{run_id}:{event_seq}",
        "run_id": run_id,
        "event_type": event_type,
        "event_seq": event_seq,
        "timestamp": data.get("timestamp"),
    }
    if event_type in {
        "run.created",
        "run.progress",
        "run.completed",
        "run.failed",
        "run.cancelled",
        "run.timed_out",
    }:
        event["payload"] = {
            "phase": str(payload.get("phase") or payload.get("stage") or event_type.rsplit(".", 1)[-1]).upper(),
            **({"stage": payload["stage"]} if isinstance(payload.get("stage"), str) else {}),
            **({"message": payload["message"]} if isinstance(payload.get("message"), str) else {}),
        }
        if "stage" not in event["payload"]:
            event["payload"]["stage"] = event["payload"]["phase"].lower()
        return event
    if event_type == "assistant.message" and isinstance(payload.get("text"), str):
        event["payload"] = {"text": payload["text"]}
        return event
    if event_type == "reasoning.summary" and isinstance(payload.get("summary"), str):
        event["payload"] = {"summary": payload["summary"]}
        return event
    if event_type == "tool.call":
        tool_name = payload.get("tool_name")
        call_id = payload.get("call_id")
        status = payload.get("status")
        if (
            isinstance(tool_name, str)
            and tool_name
            and isinstance(call_id, str)
            and call_id
            and status in _TOOL_CALL_STATUSES
        ):
            event["payload"] = {
                "tool_name": tool_name,
                "call_id": call_id,
                "status": status,
            }
            return event
        return None
    if event_type == "clarify.requested" and isinstance(payload.get("question"), str):
        projected: dict[str, Any] = {"question": payload["question"]}
        options = payload.get("options")
        if options is None or isinstance(options, list):
            projected["options"] = options
        event["payload"] = projected
        return event
    if event_type == "approval.requested":
        approval_id = payload.get("approval_id")
        summary = payload.get("summary")
        if isinstance(approval_id, str) and approval_id and isinstance(summary, str):
            event["payload"] = {"approval_id": approval_id, "summary": summary}
            return event
        return None
    if event_type == "artifact.persisted":
        event["payload"] = _public_artifact_descriptor(payload)
        return event
    return None


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


def _handle_agent_error_response(response: httpx.Response) -> None:
    status_code = response.status_code
    if status_code == 404:
        raise NotFoundError("Run 不存在", "errors.run.not_found")
    if 400 <= status_code < 500:
        msg = "Agent 请求失败"
        msg_key = "errors.run.agent_error"
        err_code = status_code * 100
        try:
            err_payload = response.json()
            if isinstance(err_payload, dict):
                msg = err_payload.get("message") or err_payload.get("detail") or msg
                msg_key = err_payload.get("message_key") or msg_key
                raw_code = err_payload.get("error_code") or err_payload.get("code")
                if raw_code is not None:
                    try:
                        err_code = int(raw_code)
                    except (ValueError, TypeError):
                        pass
        except Exception:
            pass
        raise AppException(
            code=err_code,
            message=str(msg),
            status_code=status_code,
            message_key=str(msg_key),
        )
    response.raise_for_status()


async def _agent_get(
    path: str,
    *,
    params: dict[str, Any] | None = None,
    org_id: str | None = None,
    user_id: str | None = None,
) -> Any:
    url = f"{settings.SKILL_AGENT_BASE_URL.rstrip('/')}{path}"
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=5.0)) as client:
        try:
            response = await client.get(
                url,
                headers=_agent_headers(org_id=org_id, user_id=user_id),
                params=params,
            )
            _handle_agent_error_response(response)
            return response.json()
        except httpx.HTTPStatusError as exc:
            _handle_agent_error_response(exc.response)


async def _agent_post(
    path: str,
    *,
    json_body: dict | None = None,
    org_id: str | None = None,
    user_id: str | None = None,
) -> Any:
    url = f"{settings.SKILL_AGENT_BASE_URL.rstrip('/')}{path}"
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=5.0)) as client:
        try:
            response = await client.post(
                url,
                headers=_agent_headers(org_id=org_id, user_id=user_id),
                json=json_body or {},
            )
            _handle_agent_error_response(response)
            return response.json()
        except httpx.HTTPStatusError as exc:
            _handle_agent_error_response(exc.response)


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
        return _public_run_view(
            {
                "run_id": task.id,
                "tool_name": task.tool_name,
                "status": derived_status,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "updated_at": task.updated_at.isoformat() if task.updated_at else None,
            }
        )

    data = await _agent_get(f"/internal/v1/runs/{run_id}", org_id=org.id, user_id=user.id)
    if str(data.get("org_id") or "") != org.id or str(data.get("run_id") or "") != run_id:
        raise ForbiddenError("无权访问该 Run", "errors.run.forbidden")
    return _public_run_view(data)


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
        return _public_run_result({"status": "QUEUED"}, run_id)

    data = await _agent_get(f"/internal/v1/runs/{run_id}/result", org_id=org.id, user_id=user.id)
    if str(data.get("org_id") or "") != org.id or str(data.get("run_id") or "") != run_id:
        raise ForbiddenError("无权访问该 Run", "errors.run.forbidden")
    return _public_run_result(data, run_id)


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
        return {"run_id": run_id, "items": []}

    data = await _agent_get(f"/internal/v1/runs/{run_id}/artifacts", org_id=org.id, user_id=user.id)
    if str(data.get("org_id") or "") != org.id or str(data.get("run_id") or "") != run_id:
        raise ForbiddenError("无权访问该 Run", "errors.run.forbidden")
    return {
        "run_id": run_id,
        "items": [_public_artifact_descriptor(item) for item in data.get("items") or []],
    }


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

        public_headers = {
            "Content-Disposition": content_disposition,
            "Content-Length": str(len(response.content)),
            "X-Checksum-SHA256": str(target_art.get("checksum_sha256") or target_art.get("sha256") or ""),
            "Cache-Control": "no-store",
        }
        return Response(
            content=response.content,
            media_type=target_art.get("content_type")
            or response.headers.get("content-type")
            or "application/octet-stream",
            headers=public_headers,
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
        return _public_run_view({
            "run_id": run_id,
            "tool_name": task.tool_name,
            "status": "CANCELLED",
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "updated_at": task.updated_at.isoformat() if task.updated_at else None,
        })

    data = await _agent_post(f"/internal/v1/runs/{run_id}/cancel", org_id=org.id, user_id=user.id)
    if str(data.get("org_id") or "") != org.id or str(data.get("run_id") or "") != run_id:
        raise ForbiddenError("无权访问该 Run", "errors.run.forbidden")
    await db.execute(
        update(EdgeJob)
        .where(
            not_deleted(EdgeJob),
            EdgeJob.org_id == org.id,
            EdgeJob.run_id == run_id,
            EdgeJob.status.in_(
                [
                    EdgeJobStatus.QUEUED.value,
                    EdgeJobStatus.CLAIMED.value,
                    EdgeJobStatus.RUNNING.value,
                ]
            ),
        )
        .values(cancel_requested_at=datetime.now(timezone.utc))
    )
    await db.commit()
    return _public_run_view(data)


@router.post("/{run_id}/resume")
async def resume_run(
    run_id: str,
    body: dict | None = None,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await PermissionChecker.require_permission(db, user.id, org.id, "skill:invoke")
    task = await _authorize_run(db, user.id, org.id, run_id)
    outbox = await _get_outbox_entry(db, run_id, org.id)
    if _is_outbox_undelivered(outbox):
        if outbox and outbox.status == RunDispatchStatus.DEAD_LETTER.value:
            # Replay authorized dead letter dispatch
            outbox.status = RunDispatchStatus.PENDING.value
            outbox.retry_count = 0
            outbox.next_retry_at = None
            outbox.last_error = None
            await db.commit()
            return {
                "code": 0,
                "data": {
                    "run_id": run_id,
                    "status": "REPLAY_QUEUED",
                    "org_id": org.id,
                },
            }
        raise ForbiddenError("未派发的 Run 无法执行恢复", "errors.run.undelivered")

    payload = body or {}
    data = await _agent_post(
        f"/internal/v1/runs/{run_id}/resume",
        json_body=payload,
        org_id=org.id,
        user_id=user.id,
    )
    if str(data.get("org_id") or "") != org.id or str(data.get("run_id") or "") != run_id:
        raise ForbiddenError("无权访问该 Run", "errors.run.forbidden")
    return {"code": 0, "data": data}


@router.post("/{run_id}/approvals/{approval_id}")
async def approve_run(
    run_id: str,
    approval_id: str,
    body: dict | None = None,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await PermissionChecker.require_permission(db, user.id, org.id, "skill:invoke")
    task = await _authorize_run(db, user.id, org.id, run_id)
    outbox = await _get_outbox_entry(db, run_id, org.id)
    if _is_outbox_undelivered(outbox):
        raise ForbiddenError("未派发的 Run 无法执行审批", "errors.run.undelivered")

    payload = body or {}
    data = await _agent_post(
        f"/internal/v1/runs/{run_id}/approvals/{approval_id}",
        json_body=payload,
        org_id=org.id,
        user_id=user.id,
    )
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
                    public_event = _public_run_event(item, run_id)
                    if public_event is None:
                        continue
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
                    synthetic = {
                        "event_type": terminal_event_type,
                        "event_seq": cursor + 1,
                        "timestamp": current.get("updated_at"),
                        "payload": {"phase": str(current.get("status") or "")},
                    }
                    public_event = _public_run_event(synthetic, run_id)
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
