"""Workspace batch deploy from template — status and SSE progress."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_org, get_db
from app.models.base import not_deleted
from app.models.workspace import Workspace
from app.models.workspace_deploy import WorkspaceDeploy
from app.services.k8s.event_bus import SSEEvent, event_bus

logger = logging.getLogger(__name__)

router = APIRouter(tags=["办公室模板部署"])
TERMINAL_DEPLOY_STATUSES = {"success", "partial_success", "failed"}


def _org_id(org) -> str:
    return org.id if hasattr(org, "id") else org.get("org_id", "")


def _ok(data=None, message: str = "success"):
    return {"code": 0, "message": message, "data": data}


def _error(status_code: int, error_code: int, message_key: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"error_code": error_code, "message_key": message_key, "message": message},
    )


def _workspace_deploy_terminal_events(wd: WorkspaceDeploy) -> list[SSEEvent]:
    detail = wd.progress_detail if isinstance(wd.progress_detail, dict) else {}
    agents = detail.get("agents") if isinstance(detail, dict) else []
    events: list[SSEEvent] = []
    if isinstance(agents, list):
        for index, agent in enumerate(agents):
            if not isinstance(agent, dict):
                continue
            events.append(
                SSEEvent(
                    event="workspace_deploy_progress",
                    data={
                        "workspace_deploy_id": wd.id,
                        "event": "agent_progress",
                        "display_name": agent.get("display_name") or "",
                        "status": agent.get("status") or "pending",
                        "index": index,
                        "error": agent.get("error"),
                    },
                )
            )
    data = {
        "workspace_deploy_id": wd.id,
        "event": "complete",
        "status": wd.status,
        "success_count": wd.completed_agents or 0,
        "failed_count": wd.failed_agents or 0,
    }
    error = detail.get("error") if isinstance(detail, dict) else None
    if error:
        data["error"] = error
    events.append(SSEEvent(event="workspace_deploy_progress", data=data))
    return events


@router.get("/deploys/active")
async def list_active_deploys(
    org_ctx=Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    user, org = org_ctx
    oid = _org_id(org)
    r = await db.execute(
        select(WorkspaceDeploy, Workspace.name)
        .outerjoin(
            Workspace,
            (Workspace.id == WorkspaceDeploy.workspace_id) & (Workspace.deleted_at.is_(None)),
        )
        .where(
            WorkspaceDeploy.org_id == oid,
            WorkspaceDeploy.created_by == user.id,
            WorkspaceDeploy.status.in_(("pending", "deploying")),
            not_deleted(WorkspaceDeploy),
        )
        .order_by(WorkspaceDeploy.created_at.desc())
    )
    rows = []
    for wd, ws_name in r.all():
        rows.append({
            "id": wd.id,
            "workspace_id": wd.workspace_id,
            "workspace_name": ws_name or "",
            "template_id": wd.template_id,
            "status": wd.status,
            "total_agents": wd.total_agents,
            "completed_agents": wd.completed_agents,
            "failed_agents": wd.failed_agents,
        })
    return _ok(rows)


@router.get("/deploys/{deploy_id}")
async def get_workspace_deploy(
    deploy_id: str,
    org_ctx=Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    user, org = org_ctx
    oid = _org_id(org)
    r = await db.execute(
        select(WorkspaceDeploy, Workspace.name)
        .outerjoin(
            Workspace,
            (Workspace.id == WorkspaceDeploy.workspace_id) & (Workspace.deleted_at.is_(None)),
        )
        .where(
            WorkspaceDeploy.id == deploy_id,
            WorkspaceDeploy.org_id == oid,
            WorkspaceDeploy.created_by == user.id,
            not_deleted(WorkspaceDeploy),
        )
    )
    row = r.first()
    if not row:
        raise _error(404, 40461, "errors.workspace_deploy.not_found", "部署记录不存在")
    wd, ws_name = row
    return _ok({
        "id": wd.id,
        "workspace_id": wd.workspace_id,
        "workspace_name": ws_name or "",
        "template_id": wd.template_id,
        "status": wd.status,
        "total_agents": wd.total_agents,
        "completed_agents": wd.completed_agents,
        "failed_agents": wd.failed_agents,
        "progress_detail": wd.progress_detail,
        "config_snapshot": wd.config_snapshot,
        "created_at": wd.created_at.isoformat() if wd.created_at else None,
    })


@router.get("/deploys/{deploy_id}/progress")
async def workspace_deploy_progress_stream(
    deploy_id: str,
    org_ctx=Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    user, org = org_ctx
    oid = _org_id(org)
    r = await db.execute(
        select(WorkspaceDeploy.id).where(
            WorkspaceDeploy.id == deploy_id,
            WorkspaceDeploy.org_id == oid,
            WorkspaceDeploy.created_by == user.id,
            not_deleted(WorkspaceDeploy),
        )
    )
    if not r.scalar_one_or_none():
        raise _error(404, 40461, "errors.workspace_deploy.not_found", "部署记录不存在")

    queue, cleanup = event_bus.create_subscription("workspace_deploy_progress")
    try:
        snapshot_result = await db.execute(
            select(WorkspaceDeploy).where(
                WorkspaceDeploy.id == deploy_id,
                WorkspaceDeploy.org_id == oid,
                WorkspaceDeploy.created_by == user.id,
                not_deleted(WorkspaceDeploy),
            )
        )
        snapshot = snapshot_result.scalar_one_or_none()
    except Exception:
        cleanup()
        raise

    if not snapshot:
        cleanup()
        raise _error(404, 40461, "errors.workspace_deploy.not_found", "部署记录不存在")

    terminal_events = (
        _workspace_deploy_terminal_events(snapshot)
        if snapshot.status in TERMINAL_DEPLOY_STATUSES
        else None
    )
    if terminal_events:
        cleanup()

    async def generate():
        if terminal_events:
            for ev in terminal_events:
                yield ev.format()
            return

        try:
            while True:
                ev = await queue.get()
                if ev.data.get("workspace_deploy_id") != deploy_id:
                    continue
                yield ev.format()
                evt = ev.data.get("event")
                if evt == "complete":
                    break
        finally:
            cleanup()

    return StreamingResponse(generate(), media_type="text/event-stream")
