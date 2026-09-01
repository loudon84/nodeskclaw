from __future__ import annotations

import base64
import hashlib
import hmac
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_db
from app.core.exceptions import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from app.models.base import not_deleted
from app.models.connector.edge_artifact_on_demand_request import EdgeArtifactOnDemandRequest, OnDemandRequestStatus
from app.models.connector.edge_job import EdgeJob, EdgeJobStatus
from app.models.connector.edge_node import EdgeNode, EdgeNodeStatus
from app.models.hermes_skill.skill_installation import HermesSkillInstallation
from app.services.connector.edge_node_service import EdgeNodeService, hash_edge_token
from app.services.hermes_skill.runtime_skill_run_service import RuntimeSkillRunService, strip_internal_route_secrets
from app.services.hermes_skill.skill_release_service import (
    SkillReleaseService,
    bundle_descriptor_from_release,
    bundle_zip_path,
)
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
    artifact_id: str | None = None
    name: str
    content_type: str = "application/octet-stream"
    content_base64: str
    checksum_sha256: str
    delivery_generation: int | None = None
    attempt_id: str | None = None
    step_id: str | None = None
    run_generation: int | None = None
    size: int | None = None
    upload_mode: str | None = "eager"
    idempotency_key: str | None = None
    storage_state: str = "persisted"


class EdgeArtifactRequestBody(BaseModel):
    artifact_id: str | None = None
    name: str
    reason: str | None = None


class IssueOnDemandRequestBody(BaseModel):
    name: str
    artifact_id: str | None = None
    attempt_id: str | None = None
    step_id: str | None = None
    run_generation: int | None = None
    delivery_generation: int | None = None
    ttl_seconds: int = 300



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


ACTUAL_ALIGN_STATUSES = frozenset({"ready", "uninstalled", "removed"})
ACTUAL_ERROR_STATUSES = frozenset({"error", "failed"})


async def _resolve_published_bundle(
    db: AsyncSession,
    *,
    org_id: str,
    skill_id: str,
) -> dict | None:
    release = await SkillReleaseService(db).get_published(org_id, skill_id)
    if not release:
        return None
    return bundle_descriptor_from_release(release)


async def _ensure_pinned_bundle(
    db: AsyncSession,
    inst: HermesSkillInstallation,
) -> dict | None:
    if inst.status == "uninstalling":
        return None
    desired_gen = getattr(inst, "desired_generation", 1) or 1
    metadata = dict(inst.install_metadata or {})
    pinned = metadata.get("published_bundle")
    if (
        isinstance(pinned, dict)
        and pinned.get("generation") == desired_gen
        and pinned.get("release_id")
        and pinned.get("bundle_ref")
        and pinned.get("sha256")
        and pinned.get("size") is not None
    ):
        return {
            "release_id": pinned["release_id"],
            "bundle_ref": pinned["bundle_ref"],
            "version": pinned.get("version"),
            "size": pinned["size"],
            "sha256": pinned["sha256"],
        }
    bundle = await _resolve_published_bundle(db, org_id=inst.org_id, skill_id=inst.skill_id)
    if not bundle:
        return None
    metadata["published_bundle"] = {
        **bundle,
        "generation": desired_gen,
    }
    inst.install_metadata = metadata
    await db.flush()
    return bundle


def _read_pinned_bundle(inst: HermesSkillInstallation) -> dict | None:
    desired_gen = getattr(inst, "desired_generation", 1) or 1
    if inst.status == "uninstalling":
        return None
    pinned = (inst.install_metadata or {}).get("published_bundle")
    if not isinstance(pinned, dict) or pinned.get("generation") != desired_gen:
        return None
    if not pinned.get("bundle_ref") or not pinned.get("sha256") or pinned.get("size") is None:
        return None
    return {
        "release_id": pinned.get("release_id"),
        "bundle_ref": pinned["bundle_ref"],
        "version": pinned.get("version"),
        "size": pinned["size"],
        "sha256": pinned["sha256"],
    }


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

    import json
    for event in body.events:
        payload = event.get("payload") or {}
        payload_bytes = len(json.dumps(payload, default=str).encode("utf-8"))
        if payload_bytes > 65536:
            raise BadRequestError(
                "Event payload 超过 64KB 限制，请使用 /artifacts/upload 独立上传产物",
                "errors.connector.payload_too_large",
            )

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

    agent_data = None
    # Relay to agent storage if enabled
    if settings.SKILL_AGENT_ENABLED and settings.SKILL_AGENT_BASE_URL:
        url = f"{settings.SKILL_AGENT_BASE_URL.rstrip('/')}/internal/v1/runs/{job.run_id}/artifacts"
        headers = {
            "X-Skill-Agent-Token": settings.SKILL_AGENT_INTERNAL_TOKEN,
            "X-Exec-Org-Id": node.org_id,
            "Content-Type": "application/json",
        }
        payload = {
            "name": body.name,
            "content_type": body.content_type,
            "content_base64": body.content_base64,
            "checksum_sha256": calc_sha,
            "attempt_id": body.attempt_id or job.attempt_id,
            "step_id": body.step_id or job.step_id,
            "generation": body.run_generation or job.run_generation,
            "size": body.size or len(raw_bytes),
            "upload_mode": body.upload_mode or "eager",
            "idempotency_key": body.idempotency_key,
        }
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=5.0)) as client:
                res = await client.post(url, headers=headers, json=payload)
                if res.status_code >= 400:
                    try:
                        res_json = res.json()
                        err_code = res_json.get("error_code") or res_json.get("message_key") or "errors.connector.edge_artifact_relay_failed"
                        msg = res_json.get("message") or res_json.get("detail") or "中继产物失败"
                    except Exception:
                        err_code = "errors.connector.edge_artifact_relay_failed"
                        msg = f"中继产物失败: {res.text}"
                    if res.status_code == 400:
                        raise BadRequestError(msg, err_code)
                    elif res.status_code == 403:
                        raise ForbiddenError(msg, err_code)
                    elif res.status_code == 404:
                        raise NotFoundError(msg, err_code)
                    elif res.status_code == 409:
                        raise ConflictError(msg, err_code)
                    else:
                        raise HTTPException(status_code=res.status_code, detail={"error_code": err_code, "message_key": err_code, "message": msg, "detail": msg})
                agent_data = res.json() if res.content else {}
        except (BadRequestError, ForbiddenError, NotFoundError, ConflictError, HTTPException):
            raise
        except Exception as exc:
            import logging
            logging.getLogger(__name__).error("failed to forward edge artifact run_id=%s (fail-closed): %s", job.run_id, exc)
            raise ForbiddenError(f"中继产物失败: {exc}", "errors.connector.edge_artifact_relay_failed")

    edge_service = EdgeNodeService(db)
    await edge_service.consume_on_demand_request(
        org_id=node.org_id,
        job_id=job.id,
        name=body.name,
        artifact_id=agent_data.get("artifact_id") if isinstance(agent_data, dict) else body.artifact_id,
        run_generation=job.run_generation,
    )
    await db.commit()

    return {
        "code": 0,
        "data": agent_data if isinstance(agent_data, dict) else {
            "artifact_id": body.artifact_id,
            "status": "uploaded",
            "checksum_sha256": calc_sha,
        },
    }


@router.get("/artifacts/on-demand-requests")
async def pull_edge_artifact_on_demand_requests(
    db: AsyncSession = Depends(get_db),
    x_edge_token: str | None = Header(default=None, alias="X-Edge-Token"),
):
    node = await _authenticate_edge(db, token=x_edge_token)
    edge_service = EdgeNodeService(db)
    items = await edge_service.pull_on_demand_requests(org_id=node.org_id, edge_node_id=node.id)
    await db.commit()
    return {
        "code": 0,
        "data": {
            "items": [
                {
                    "id": item.id,
                    "org_id": item.org_id,
                    "edge_node_id": item.edge_node_id,
                    "job_id": item.job_id,
                    "run_id": item.run_id,
                    "attempt_id": item.attempt_id,
                    "step_id": item.step_id,
                    "run_generation": item.run_generation,
                    "delivery_generation": item.delivery_generation,
                    "artifact_id": item.artifact_id,
                    "name": item.name,
                    "status": item.status,
                    "expires_at": item.expires_at.isoformat() if item.expires_at else None,
                }
                for item in items
            ]
        },
    }


@router.post("/jobs/{job_id}/artifacts/on-demand-request")
async def create_edge_job_artifact_on_demand_request(
    job_id: str,
    body: IssueOnDemandRequestBody,
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
        raise NotFoundError("Edge job 不存在", "errors.artifact.on_demand_not_found")

    edge_service = EdgeNodeService(db)
    req = await edge_service.issue_on_demand_request(
        org_id=node.org_id,
        edge_node_id=node.id,
        job_id=job.id,
        run_id=job.run_id,
        name=body.name,
        artifact_id=body.artifact_id,
        attempt_id=body.attempt_id or job.attempt_id,
        step_id=body.step_id or job.step_id,
        run_generation=body.run_generation or job.run_generation,
        delivery_generation=body.delivery_generation or job.delivery_generation,
        ttl_seconds=body.ttl_seconds,
    )
    await db.commit()
    return {
        "code": 0,
        "data": {
            "id": req.id,
            "job_id": req.job_id,
            "name": req.name,
            "status": req.status,
            "expires_at": req.expires_at.isoformat() if req.expires_at else None,
        },
    }


@router.post("/jobs/{job_id}/artifacts/request")
async def request_edge_job_artifact(
    job_id: str,
    body: EdgeArtifactRequestBody,
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

    if req_gen is None:
        raise ForbiddenError("必须提供有效的 delivery generation", "errors.connector.missing_delivery_generation")

    if job.delivery_generation is not None and req_gen != job.delivery_generation:
        raise ForbiddenError("过期的 delivery generation 请求已拒绝", "errors.connector.stale_delivery_generation")

    if not settings.SKILL_AGENT_ENABLED or not settings.SKILL_AGENT_BASE_URL:
        raise NotFoundError("Skill Agent 未启用或产物不存在", "errors.artifact.not_found")

    headers = {
        "X-Skill-Agent-Token": settings.SKILL_AGENT_INTERNAL_TOKEN,
        "X-Exec-Org-Id": node.org_id,
        "X-Exec-User-Id": getattr(job, "user_id", "") or "",
    }

    target_artifact_id = body.artifact_id
    if not target_artifact_id:
        list_url = f"{settings.SKILL_AGENT_BASE_URL.rstrip('/')}/internal/v1/runs/{job.run_id}/artifacts"
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=5.0)) as client:
                res = await client.get(list_url, headers=headers)
                res.raise_for_status()
                artifacts_data = res.json().get("items") or []
                for item in artifacts_data:
                    if item.get("name") == body.name:
                        target_artifact_id = item.get("artifact_id")
                        break
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning("failed to list artifacts for run_id=%s: %s", job.run_id, exc)
            raise NotFoundError(f"查找产物失败: {exc}", "errors.artifact.not_found")

    if not target_artifact_id:
        raise NotFoundError("未找到指定名称的产物", "errors.artifact.not_found")

    bytes_url = f"{settings.SKILL_AGENT_BASE_URL.rstrip('/')}/internal/v1/runs/{job.run_id}/artifacts/{target_artifact_id}/bytes"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=5.0)) as client:
            res = await client.get(bytes_url, headers=headers)
            if res.status_code == 404:
                raise NotFoundError("产物不存在", "errors.artifact.not_found")
            res.raise_for_status()
            content_bytes = res.content
            content_type = res.headers.get("content-type") or "application/octet-stream"
            checksum = res.headers.get("x-checksum-sha256") or hashlib.sha256(content_bytes).hexdigest()
            b64_content = base64.b64encode(content_bytes).decode("ascii")
            return {
                "code": 0,
                "data": {
                    "artifact_id": target_artifact_id,
                    "name": body.name,
                    "content_type": content_type,
                    "content_base64": b64_content,
                    "checksum_sha256": checksum,
                    "size_bytes": len(content_bytes),
                },
            }
    except NotFoundError:
        raise
    except Exception as exc:
        import logging
        logging.getLogger(__name__).error("failed to fetch artifact bytes from skill agent: %s", exc)
        raise ForbiddenError(f"获取产物失败: {exc}", "errors.artifact.fetch_failed")



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
        bundle = await _ensure_pinned_bundle(db, inst)
        item = {
            "id": inst.id,
            "skill_id": inst.skill_id,
            "desired_status": inst.status,
            "desired_generation": getattr(inst, "desired_generation", 1) or 1,
            "actual_generation": getattr(inst, "actual_generation", 0) or 0,
            "install_metadata": inst.install_metadata or {},
            "routing_metadata": inst.routing_metadata or {},
        }
        if bundle:
            item["bundle"] = bundle
        items.append(item)
    await db.commit()
    return {"code": 0, "data": {"items": items, "node_id": node.id}}


@router.get("/installations/{installation_id}/bundle")
async def download_installation_bundle(
    installation_id: str,
    generation: int = Query(..., ge=1),
    db: AsyncSession = Depends(get_db),
    x_edge_token: str | None = Header(default=None, alias="X-Edge-Token"),
):
    node = await _authenticate_edge(db, token=x_edge_token)
    result = await db.execute(
        select(HermesSkillInstallation).where(
            not_deleted(HermesSkillInstallation),
            HermesSkillInstallation.id == installation_id,
            HermesSkillInstallation.org_id == node.org_id,
        )
    )
    installation = result.scalar_one_or_none()
    if not installation:
        raise NotFoundError("Installation 不存在", "errors.skill.installation_not_found")
    if installation.edge_node_id != node.id:
        raise ForbiddenError("伪造 org/node 被拒绝", "errors.connector.edge_org_mismatch")
    if installation.target_kind != "edge":
        raise ForbiddenError("非 Edge Installation", "errors.skill.installation_not_found")
    if installation.status == "uninstalling":
        raise BadRequestError("卸载态不可下载 Bundle", "errors.skill.bundle_unavailable")
    desired_gen = getattr(installation, "desired_generation", 1) or 1
    if generation != desired_gen:
        if generation < desired_gen:
            raise ForbiddenError("过期的 generation 请求已拒绝", "errors.skill.stale_actual_generation")
        raise BadRequestError("超前的 generation 请求已拒绝", "errors.skill.future_generation")
    bundle = _read_pinned_bundle(installation)
    if not bundle:
        bundle = await _ensure_pinned_bundle(db, installation)
        await db.commit()
    if not bundle:
        raise NotFoundError("Bundle 不可用", "errors.skill.bundle_unavailable")
    bundle_path = bundle_zip_path(str(bundle["bundle_ref"]))
    if not bundle_path.is_file():
        raise NotFoundError("Bundle 不可用", "errors.skill.bundle_unavailable")

    def iterfile():
        with bundle_path.open("rb") as handle:
            while chunk := handle.read(65536):
                yield chunk

    return StreamingResponse(iterfile(), media_type="application/zip")


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
    if installation.edge_node_id != node.id:
        raise ForbiddenError("伪造 org/node 被拒绝", "errors.connector.edge_org_mismatch")
    if installation.target_kind != "edge":
        raise ForbiddenError("非 Edge Installation", "errors.skill.installation_not_found")

    if body.generation is None:
        raise BadRequestError("缺少 generation 字段", "errors.skill.missing_generation")

    desired_gen = getattr(installation, "desired_generation", 1) or 1
    if body.generation < desired_gen:
        raise ForbiddenError("过期的 actual generation 上报已拒绝", "errors.skill.stale_actual_generation")
    if body.generation > desired_gen:
        raise BadRequestError("超前的 generation 上报已拒绝", "errors.skill.future_generation")

    status = body.actual_status
    if status not in ACTUAL_ALIGN_STATUSES and status not in ACTUAL_ERROR_STATUSES:
        raise BadRequestError("Actual status 无效", "errors.skill.actual_status_invalid")
    if installation.status == "uninstalling":
        if status == "ready":
            raise BadRequestError("Actual status 与 Desired 状态不匹配", "errors.skill.actual_status_invalid")
    elif status in {"uninstalled", "removed"}:
        raise BadRequestError("Actual status 与 Desired 状态不匹配", "errors.skill.actual_status_invalid")
    installation.actual_status = status
    installation.actual_reported_at = datetime.now(timezone.utc)
    if body.meta:
        installation.routing_metadata = {**(installation.routing_metadata or {}), "actual_meta": body.meta}

    if status in ACTUAL_ALIGN_STATUSES:
        installation.actual_generation = body.generation
        installation.error_message = None
    elif status in ACTUAL_ERROR_STATUSES:
        error_code = None
        if body.meta and isinstance(body.meta.get("error_code"), str):
            error_code = body.meta["error_code"].strip()
        installation.error_message = (error_code or status)[:1024]

    if installation.status == "uninstalling" and status in ("uninstalled", "removed"):
        installation.status = "removed"
        installation.deleted_at = datetime.now(timezone.utc)

    await db.commit()
    return {"code": 0, "data": {"installation_id": installation.id, "actual_status": installation.actual_status}}


class RevalidateExecutionContextBody(BaseModel):
    run_id: str
    user_id: str
    context_version: int
    execution_context: dict = Field(default_factory=dict)
    attempt_id: str | None = None
    generation: int | None = None


def _authenticate_internal_skill_agent(
    x_skill_agent_token: str | None,
) -> None:
    expected_curr = settings.SKILL_AGENT_INTERNAL_TOKEN
    expected_prev = settings.SKILL_AGENT_INTERNAL_TOKEN_PREVIOUS
    if not x_skill_agent_token:
        raise ForbiddenError("Internal skill agent token 无效", "errors.auth.invalid_token")
    curr_match = expected_curr and hmac.compare_digest(x_skill_agent_token, expected_curr)
    prev_match = expected_prev and hmac.compare_digest(x_skill_agent_token, expected_prev)
    if not curr_match and not prev_match:
        raise ForbiddenError("Internal skill agent token 无效", "errors.auth.invalid_token")


@router.post("/skill-run/revalidate")
async def revalidate_skill_run_execution_context(
    body: RevalidateExecutionContextBody,
    db: AsyncSession = Depends(get_db),
    x_skill_agent_token: str | None = Header(default=None, alias="X-Skill-Agent-Token"),
    x_exec_org_id: str | None = Header(default=None, alias="X-Exec-Org-Id"),
):
    _authenticate_internal_skill_agent(x_skill_agent_token)
    if not x_exec_org_id:
        raise ForbiddenError("缺少 X-Exec-Org-Id header", "errors.auth.missing_org_header")
    service = RuntimeSkillRunService(db)
    await service.revalidate_execution_context(
        org_id=x_exec_org_id,
        user_id=body.user_id,
        execution_context=body.execution_context,
        context_version=body.context_version,
    )
    return {"code": 0, "data": {"run_id": body.run_id, "ok": True}}


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
    _authenticate_internal_skill_agent(x_skill_agent_token)

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
