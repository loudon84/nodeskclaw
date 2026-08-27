from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, Header, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_db
from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.base import not_deleted
from app.models.connector.edge_job import EdgeJob, EdgeJobStatus
from app.models.connector.edge_node import EdgeNode, EdgeNodeStatus
from app.models.hermes_skill.skill_installation import HermesSkillInstallation
from app.services.connector.edge_node_service import hash_edge_token
from app.services.hermes_skill.runtime_skill_run_service import strip_internal_route_secrets
from app.services.runtime.pg_notify import PGNotifyService

router = APIRouter(prefix="/internal/edge", tags=["Internal Edge"])

HEARTBEAT_STALE_SECONDS = 90


class EdgeHeartbeatBody(BaseModel):
    node_id: str
    status_meta: dict | None = None


class EdgeJobEventsBody(BaseModel):
    events: list[dict] = Field(default_factory=list)
    delivery_generation: int | None = None


async def _authenticate_edge(
    db: AsyncSession,
    *,
    token: str | None,
    node_id: str | None = None,
) -> EdgeNode:
    if not token:
        raise ForbiddenError("Edge token 无效", "errors.connector.edge_token_invalid")
    token_hash = hash_edge_token(token)
    query = select(EdgeNode).where(
        not_deleted(EdgeNode),
        EdgeNode.token_hash == token_hash,
    )
    if node_id:
        query = query.where(EdgeNode.id == node_id)
    result = await db.execute(query.limit(1))
    node = result.scalar_one_or_none()
    if not node:
        raise ForbiddenError("Edge token 无效", "errors.connector.edge_token_invalid")
    if node.status == EdgeNodeStatus.DISABLED.value:
        raise ForbiddenError("Edge 节点已禁用", "errors.connector.edge_node_disabled")
    return node


@router.post("/heartbeat")
async def edge_heartbeat(
    body: EdgeHeartbeatBody,
    db: AsyncSession = Depends(get_db),
    x_edge_token: str | None = Header(default=None, alias="X-Edge-Token"),
):
    node = await _authenticate_edge(db, token=x_edge_token, node_id=body.node_id)
    if node.org_id and body.node_id != node.id:
        raise ForbiddenError("伪造 org/node 被拒绝", "errors.connector.edge_org_mismatch")
    now = datetime.now(timezone.utc)
    node.last_heartbeat_at = now
    node.status = EdgeNodeStatus.ONLINE.value
    if body.status_meta is not None:
        node.meta = {**(node.meta or {}), **body.status_meta}
    await db.commit()
    return {"code": 0, "data": {"node_id": node.id, "status": node.status}}


@router.get("/jobs")
async def claim_edge_job(
    db: AsyncSession = Depends(get_db),
    x_edge_token: str | None = Header(default=None, alias="X-Edge-Token"),
):
    node = await _authenticate_edge(db, token=x_edge_token)
    result = await db.execute(
        select(EdgeJob)
        .where(
            not_deleted(EdgeJob),
            EdgeJob.edge_node_id == node.id,
            EdgeJob.org_id == node.org_id,
            (
                (EdgeJob.status == EdgeJobStatus.QUEUED.value)
                | (
                    (EdgeJob.status.in_([EdgeJobStatus.CLAIMED.value, EdgeJobStatus.RUNNING.value]))
                    & (EdgeJob.lease_until.is_not(None))
                    & (EdgeJob.lease_until < datetime.now(timezone.utc))
                )
            ),
        )
        .order_by(EdgeJob.created_at.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    job = result.scalar_one_or_none()
    if not job:
        return Response(status_code=204)
    now = datetime.now(timezone.utc)
    job.status = EdgeJobStatus.CLAIMED.value
    job.claimed_at = now
    job.delivery_generation = (job.delivery_generation or 0) + 1
    job.lease_until = now + timedelta(seconds=60)
    await db.commit()
    payload = {
        "id": job.id,
        "run_id": job.run_id,
        "tool_name": job.tool_name,
        "arguments": job.arguments or {},
        "snapshot": strip_internal_route_secrets(job.snapshot or {}),
        "delivery_generation": job.delivery_generation,
    }
    return payload


@router.post("/jobs/{job_id}/events")
async def post_edge_job_events(
    job_id: str,
    body: EdgeJobEventsBody,
    db: AsyncSession = Depends(get_db),
    x_edge_token: str | None = Header(default=None, alias="X-Edge-Token"),
    x_delivery_generation: str | None = Header(default=None, alias="X-Delivery-Generation"),
):
    node = await _authenticate_edge(db, token=x_edge_token)
    result = await db.execute(
        select(EdgeJob).where(
            not_deleted(EdgeJob),
            EdgeJob.id == job_id,
            EdgeJob.edge_node_id == node.id,
            EdgeJob.org_id == node.org_id,
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise NotFoundError("Edge job 不存在", "errors.connector.edge_job_not_found")

    # Delivery generation validation: reject stale/mismatched delivery attempts
    req_gen = None
    if x_delivery_generation and isinstance(x_delivery_generation, str):
        try:
            req_gen = int(x_delivery_generation)
        except ValueError:
            pass
    if req_gen is None and body.delivery_generation is not None:
        req_gen = body.delivery_generation

    if job.delivery_generation is not None and req_gen is not None and req_gen != job.delivery_generation:
        raise ForbiddenError("过期的 delivery generation 请求已拒绝", "errors.connector.stale_delivery_generation")

    now = datetime.now(timezone.utc)
    terminal = None
    for event in body.events:
        event_type = str(event.get("event_type") or "")
        payload = event.get("payload") or {}
        if event_type == "run.completed":
            terminal = EdgeJobStatus.COMPLETED.value
            job.result = payload
        elif event_type == "run.failed":
            terminal = EdgeJobStatus.FAILED.value
            job.result = payload
        elif event_type == "run.started" and job.status == EdgeJobStatus.CLAIMED.value:
            job.status = EdgeJobStatus.RUNNING.value

    if terminal:
        job.status = terminal
        job.completed_at = now

    # Forward events into central agent run timeline (fail-closed) and wake SSE waiters.
    if body.events and settings.SKILL_AGENT_ENABLED and settings.SKILL_AGENT_BASE_URL:
        url = f"{settings.SKILL_AGENT_BASE_URL.rstrip('/')}/internal/v1/runs/{job.run_id}/events/ingest"
        headers = {
            "X-Skill-Agent-Token": settings.SKILL_AGENT_INTERNAL_TOKEN,
            "X-Exec-Org-Id": node.org_id,
            "X-Exec-User-Id": getattr(job, "user_id", "") or "",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=5.0)) as client:
                res = await client.post(url, headers=headers, json={"events": body.events})
                res.raise_for_status()
            await PGNotifyService.notify(db, f"skill_run_events:{job.run_id}", job.run_id)
        except Exception as exc:
            import logging
            logging.getLogger(__name__).error("failed to forward edge events to skill agent run_id=%s (fail-closed): %s", job.run_id, exc)
            raise ForbiddenError(f"中继事件失败: {exc}", "errors.connector.edge_relay_failed")

    await db.commit()
    return {"code": 0, "data": {"job_id": job.id, "status": job.status}}


class EdgeActualReportBody(BaseModel):
    installation_id: str
    actual_status: str
    meta: dict | None = None


@router.post("/installations/actual")
async def report_installation_actual(
    body: EdgeActualReportBody,
    db: AsyncSession = Depends(get_db),
    x_edge_token: str | None = Header(default=None, alias="X-Edge-Token"),
):
    node = await _authenticate_edge(db, token=x_edge_token)
    result = await db.execute(
        select(HermesSkillInstallation).where(
            not_deleted(HermesSkillInstallation),
            HermesSkillInstallation.id == body.installation_id,
            HermesSkillInstallation.org_id == node.org_id,
        )
    )
    installation = result.scalar_one_or_none()
    if not installation:
        raise NotFoundError("Installation 不存在", "errors.skill.installation_not_found")
    if installation.edge_node_id and installation.edge_node_id != node.id:
        raise ForbiddenError("伪造 org/node 被拒绝", "errors.connector.edge_org_mismatch")
    installation.actual_status = body.actual_status
    installation.actual_reported_at = datetime.now(timezone.utc)
    if body.meta:
        installation.routing_metadata = {**(installation.routing_metadata or {}), "actual_meta": body.meta}
    await db.commit()
    return {"code": 0, "data": {"installation_id": installation.id, "actual_status": installation.actual_status}}


def is_edge_node_online(node: EdgeNode, *, now: datetime | None = None) -> bool:
    if node.status == EdgeNodeStatus.DISABLED.value:
        return False
    if not node.last_heartbeat_at:
        return False
    current = now or datetime.now(timezone.utc)
    hb = node.last_heartbeat_at
    if hb.tzinfo is None:
        hb = hb.replace(tzinfo=timezone.utc)
    return current - hb <= timedelta(seconds=HEARTBEAT_STALE_SECONDS)
