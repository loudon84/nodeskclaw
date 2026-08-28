from __future__ import annotations

import base64
import hashlib
import hmac
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_db
from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
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


class EdgeLeaseRenewBody(BaseModel):
    delivery_generation: int | None = None


class EdgeArtifactUploadBody(BaseModel):
    artifact_id: str
    name: str
    content_type: str = "application/octet-stream"
    content_base64: str
    checksum_sha256: str
    delivery_generation: int | None = None
    storage_state: str = "persisted"


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
        "job_id": job.id,
        "run_id": job.run_id,
        "attempt_id": job.attempt_id,
        "step_id": job.step_id,
        "run_generation": job.run_generation,
        "delivery_generation": job.delivery_generation,
        "request_trace_id": job.request_trace_id,
        "tool_name": job.tool_name,
        "arguments": job.arguments or {},
        "snapshot": strip_internal_route_secrets(job.snapshot or {}),
        "lease_until": job.lease_until.isoformat() if job.lease_until else None,
    }
    return payload


@router.post("/jobs/{job_id}/lease/renew")
async def renew_edge_job_lease(
    job_id: str,
    body: EdgeLeaseRenewBody | None = None,
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

    req_gen = None
    if x_delivery_generation and isinstance(x_delivery_generation, str):
        try:
            req_gen = int(x_delivery_generation)
        except ValueError:
            pass
    if req_gen is None and body and body.delivery_generation is not None:
        req_gen = body.delivery_generation

    if req_gen is None:
        raise ForbiddenError("必须提供有效的 delivery generation", "errors.connector.missing_delivery_generation")

    if job.delivery_generation is not None and req_gen != job.delivery_generation:
        raise ForbiddenError("过期的 delivery generation 请求已拒绝", "errors.connector.stale_delivery_generation")

    now = datetime.now(timezone.utc)
    job.lease_until = now + timedelta(seconds=60)
    await db.commit()
    return {
        "code": 0,
        "data": {
            "job_id": job.id,
            "lease_until": job.lease_until.isoformat() if job.lease_until else None,
            "delivery_generation": job.delivery_generation,
        },
    }


@router.get("/jobs/{job_id}/cancel")
async def check_edge_job_cancel(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    x_edge_token: str | None = Header(default=None, alias="X-Edge-Token"),
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
    is_cancelled = bool(job.cancel_requested_at or job.status in (EdgeJobStatus.FAILED.value, "cancelled"))
    return {"code": 0, "data": {"job_id": job.id, "cancel_requested": is_cancelled}}


@router.post("/jobs/{job_id}/cancel")
async def request_edge_job_cancel(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    x_edge_token: str | None = Header(default=None, alias="X-Edge-Token"),
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
    job.cancel_requested_at = datetime.now(timezone.utc)
    await db.commit()
    return {"code": 0, "data": {"job_id": job.id, "status": job.status, "cancel_requested": True}}


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

    if req_gen is None:
        raise ForbiddenError("必须提供有效的 delivery generation", "errors.connector.missing_delivery_generation")

    if job.delivery_generation is not None and req_gen != job.delivery_generation:
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


@router.post("/jobs/{job_id}/artifacts/upload")
async def upload_edge_job_artifact(
    job_id: str,
    body: EdgeArtifactUploadBody,
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

    req_gen = None
    if x_delivery_generation and isinstance(x_delivery_generation, str):
        try:
            req_gen = int(x_delivery_generation)
        except ValueError:
            pass
    if req_gen is None and body.delivery_generation is not None:
        req_gen = body.delivery_generation

    if req_gen is None:
        raise ForbiddenError("必须提供有效的 delivery generation", "errors.connector.missing_delivery_generation")

    if job.delivery_generation is not None and req_gen != job.delivery_generation:
        raise ForbiddenError("过期的 delivery generation 请求已拒绝", "errors.connector.stale_delivery_generation")

    # Verify checksum
    try:
        raw_bytes = base64.b64decode(body.content_base64)
    except Exception:
        raise BadRequestError("无效的 base64 内容", "errors.artifact.invalid_base64")
    calc_sha = hashlib.sha256(raw_bytes).hexdigest()
    if body.checksum_sha256 and calc_sha.lower() != body.checksum_sha256.lower():
        raise BadRequestError("Artifact checksum 不匹配", "errors.artifact.checksum_mismatch")

    # Relay to agent storage if enabled
    if settings.SKILL_AGENT_ENABLED and settings.SKILL_AGENT_BASE_URL:
        url = f"{settings.SKILL_AGENT_BASE_URL.rstrip('/')}/internal/v1/runs/{job.run_id}/artifacts/upload"
        headers = {
            "X-Skill-Agent-Token": settings.SKILL_AGENT_INTERNAL_TOKEN,
            "X-Exec-Org-Id": node.org_id,
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=5.0)) as client:
                res = await client.post(
                    url,
                    headers=headers,
                    json={
                        "artifact_id": body.artifact_id,
                        "name": body.name,
                        "content_type": body.content_type,
                        "content_base64": body.content_base64,
                        "checksum_sha256": calc_sha,
                        "storage_state": body.storage_state,
                    },
                )
                res.raise_for_status()
        except Exception as exc:
            import logging
            logging.getLogger(__name__).error("failed to forward edge artifact run_id=%s (fail-closed): %s", job.run_id, exc)
            raise ForbiddenError(f"中继产物失败: {exc}", "errors.connector.edge_artifact_relay_failed")

    return {
        "code": 0,
        "data": {
            "artifact_id": body.artifact_id,
            "status": "uploaded",
            "checksum_sha256": calc_sha,
        },
    }


@router.get("/installations/desired")
async def get_desired_installations(
    db: AsyncSession = Depends(get_db),
    x_edge_token: str | None = Header(default=None, alias="X-Edge-Token"),
):
    node = await _authenticate_edge(db, token=x_edge_token)
    result = await db.execute(
        select(HermesSkillInstallation).where(
            not_deleted(HermesSkillInstallation),
            HermesSkillInstallation.org_id == node.org_id,
            HermesSkillInstallation.target_kind == "edge",
            HermesSkillInstallation.edge_node_id == node.id,
        ).order_by(HermesSkillInstallation.created_at.asc())
    )
    items = []
    for inst in result.scalars().all():
        items.append({
            "id": inst.id,
            "skill_id": inst.skill_id,
            "desired_status": inst.status,
            "desired_generation": getattr(inst, "desired_generation", 1) or 1,
            "actual_generation": getattr(inst, "actual_generation", 0) or 0,
            "install_metadata": inst.install_metadata or {},
            "routing_metadata": inst.routing_metadata or {},
        })
    return {"code": 0, "data": {"items": items, "node_id": node.id}}


class EdgeActualReportBody(BaseModel):
    installation_id: str
    actual_status: str
    generation: int | None = None
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

    # If generation provided, check if actual generation is stale compared to current actual_generation
    if body.generation is not None and hasattr(installation, "actual_generation"):
        if installation.actual_generation and body.generation < installation.actual_generation:
            raise ForbiddenError("过期的 actual generation 上报已拒绝", "errors.skill.stale_actual_generation")
        installation.actual_generation = body.generation

    installation.actual_status = body.actual_status
    installation.actual_reported_at = datetime.now(timezone.utc)
    if body.meta:
        installation.routing_metadata = {**(installation.routing_metadata or {}), "actual_meta": body.meta}
    await db.commit()
    return {"code": 0, "data": {"installation_id": installation.id, "actual_status": installation.actual_status}}


class EnqueueEdgeJobRequest(BaseModel):
    edge_node_id: str
    run_id: str
    tool_name: str
    arguments: dict | None = None
    snapshot: dict | None = None
    idempotency_key: str | None = None
    attempt_id: str | None = None
    step_id: str | None = None
    run_generation: int = 1
    request_trace_id: str | None = None


@router.post("/jobs/enqueue")
async def enqueue_edge_job_endpoint(
    body: EnqueueEdgeJobRequest,
    db: AsyncSession = Depends(get_db),
    x_skill_agent_token: str | None = Header(default=None, alias="X-Skill-Agent-Token"),
    x_exec_org_id: str | None = Header(default=None, alias="X-Exec-Org-Id"),
):
    expected_curr = settings.SKILL_AGENT_INTERNAL_TOKEN
    expected_prev = settings.SKILL_AGENT_INTERNAL_TOKEN_PREVIOUS
    if not x_skill_agent_token:
        raise ForbiddenError("Internal skill agent token 无效", "errors.auth.invalid_token")
    curr_match = expected_curr and hmac.compare_digest(x_skill_agent_token, expected_curr)
    prev_match = expected_prev and hmac.compare_digest(x_skill_agent_token, expected_prev)
    if not curr_match and not prev_match:
        raise ForbiddenError("Internal skill agent token 无效", "errors.auth.invalid_token")

    if not x_exec_org_id:
        raise ForbiddenError("缺少 X-Exec-Org-Id header", "errors.auth.missing_org_header")

    from app.services.connector.edge_node_service import EdgeNodeService

    service = EdgeNodeService(db)
    job = await service.enqueue_edge_job(
        org_id=x_exec_org_id,
        edge_node_id=body.edge_node_id,
        run_id=body.run_id,
        tool_name=body.tool_name,
        arguments=body.arguments,
        snapshot=body.snapshot,
        idempotency_key=body.idempotency_key,
        attempt_id=body.attempt_id,
        step_id=body.step_id,
        run_generation=body.run_generation,
        request_trace_id=body.request_trace_id,
    )
    await db.commit()
    return {"code": 0, "data": {"job_id": job.id, "status": job.status, "run_id": job.run_id}}



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
