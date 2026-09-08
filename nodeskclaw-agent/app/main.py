import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import logging
from typing import Any

import httpx
from fastapi import Depends, FastAPI, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internal_runs import router as internal_runs_router
from app.config import alembic_version_relation, settings
from app.db import SessionLocal, get_db
from app.services.edge_control_channel import EdgeControlChannel
from app.services.edge_worker import EdgeWorker
from app.services.readiness import expected_alembic_heads
from app.services.storage_port import StorageProbeError, get_storage_driver
from app.services.execution_observability import get_registry
from app.services.worker import RunWorker

logger = logging.getLogger(__name__)


# @lat: [[architecture/skill-agent#Role Modes]]
@asynccontextmanager
async def lifespan(app: FastAPI):
    worker_task = None
    worker = None
    if settings.SKILL_AGENT_WORKER_ENABLED:
        if settings.SKILL_AGENT_ROLE == "edge":
            worker = EdgeWorker()
            app.state.worker = worker
            worker_task = asyncio.create_task(worker.start())
            logger.info("nodeskclaw-agent edge worker enabled")
        else:
            worker = RunWorker()
            app.state.worker = worker
            worker_task = asyncio.create_task(worker.start())
            logger.info("nodeskclaw-agent worker enabled")
    yield
    if worker:
        worker.stop()
    if worker_task and not worker_task.done():
        worker_task.cancel()


app = FastAPI(title="nodeskclaw-agent", version="0.1.0", lifespan=lifespan)
app.include_router(internal_runs_router)


@app.get("/health/live")
@app.get("/healthz/live")
async def health_live():
    return {
        "status": "ok",
        "service": "nodeskclaw-agent",
        "role": settings.SKILL_AGENT_ROLE,
    }


def _append_failure(
    checks: dict[str, bool],
    reasons: list[str],
    codes: list[str],
    check_key: str,
    code: str,
    reason: str,
) -> None:
    checks[check_key] = False
    codes.append(code)
    reasons.append(reason)


@app.get("/health/ready")
@app.get("/healthz/ready")
@app.get("/health")
async def health_ready(response: Response) -> dict[str, Any]:
    reasons: list[str] = []
    codes: list[str] = []
    is_edge = settings.SKILL_AGENT_ROLE == "edge"
    checks: dict[str, bool] = {
        "config_security": True,
        "worker": True,
    }
    if not is_edge:
        checks.update({"database": True, "migration": True, "artifact_storage": True, "credential_broker": True})

    db_ok = True
    if not is_edge:
        try:
            async with SessionLocal() as db:
                await db.execute(text("SELECT 1"))

                try:
                    expected_heads = expected_alembic_heads()
                    if len(expected_heads) != 1:
                        _append_failure(
                            checks,
                            reasons,
                            codes,
                            "migration",
                            "migration.multiple_heads",
                            "multiple alembic heads configured in code",
                        )
                    else:
                        expected_head = next(iter(expected_heads))
                        res = await db.execute(
                            text(f"SELECT version_num FROM {alembic_version_relation()}")
                        )
                        db_versions = {row[0] for row in res.fetchall() if row and row[0]}
                        if not db_versions:
                            _append_failure(
                                checks,
                                reasons,
                                codes,
                                "migration",
                                "migration.head_missing",
                                "alembic migration head missing",
                            )
                        elif db_versions != {expected_head}:
                            _append_failure(
                                checks,
                                reasons,
                                codes,
                                "migration",
                                "migration.head_mismatch",
                                f"alembic migration head mismatch: db={sorted(db_versions)} expected={expected_head}",
                            )
                except Exception:
                    checks["migration"] = False
                    codes.append("migration.check_failed")
                    reasons.append("alembic_version check failed")
                    logger.exception("migration health check failed")
        except Exception:
            db_ok = False
            checks["database"] = False
            codes.append("database.connectivity_failed")
            reasons.append("database connectivity check failed")
            logger.exception("database health check failed")

    if not settings.SKILL_AGENT_INSECURE_MODE:
        if settings.SKILL_AGENT_INTERNAL_TOKEN in ("change-me-skill-agent-token", "", "default"):
            _append_failure(
                checks,
                reasons,
                codes,
                "config_security",
                "config.security.insecure_token",
                "insecure default internal token in production",
            )

        if settings.SKILL_AGENT_ARTIFACT_DIR.startswith("/tmp") or settings.SKILL_AGENT_ARTIFACT_DIR.startswith(
            "\\tmp"
        ):
            _append_failure(
                checks,
                reasons,
                codes,
                "config_security",
                "config.security.ephemeral_artifact_dir",
                "ephemeral artifact directory configured in production",
            )

        if is_edge:
            identity = EdgeControlChannel(settings.SKILL_AGENT_SECRET_STORE).load()
            has_bound_identity = bool(
                identity
                and identity.identity_version > 0
                and identity.issuer_key_id
                and identity.node_id
            )
            has_bootstrap_enrollment = bool(
                settings.SKILL_AGENT_EDGE_TOKEN and settings.SKILL_AGENT_EDGE_NODE_ID
            )
            if not has_bound_identity and not has_bootstrap_enrollment:
                _append_failure(
                    checks,
                    reasons,
                    codes,
                    "config_security",
                    "config.security.missing_edge_identity",
                    "missing bound edge identity or bootstrap enrollment material",
                )
            effective_node_id = (
                identity.node_id if identity and identity.node_id else settings.SKILL_AGENT_EDGE_NODE_ID
            )
            if not effective_node_id:
                _append_failure(
                    checks,
                    reasons,
                    codes,
                    "config_security",
                    "config.security.missing_edge_node_id",
                    "missing edge node id",
                )
            if not settings.SKILL_AGENT_CENTRAL_BASE_URL.startswith("https://"):
                _append_failure(
                    checks,
                    reasons,
                    codes,
                    "config_security",
                    "config.security.insecure_edge_central_url",
                    "insecure edge central base url (must be https://)",
                )

    if not is_edge:
        driver = None
        try:
            driver = get_storage_driver()
            probe_result = await driver.probe_isolation()
            if probe_result.get("cleanup_failed"):
                _append_failure(
                    checks,
                    reasons,
                    codes,
                    "artifact_storage",
                    "storage.probe.cleanup_failed",
                    "storage probe cleanup failed",
                )
        except StorageProbeError as exc:
            _append_failure(
                checks,
                reasons,
                codes,
                "artifact_storage",
                "storage.probe.failed",
                f"storage probe failed: {exc}",
            )
        except Exception as exc:
            _append_failure(
                checks,
                reasons,
                codes,
                "artifact_storage",
                "storage.probe.failed",
                f"storage probe failed: {exc}",
            )
        finally:
            if driver is not None:
                try:
                    await driver.close()
                except Exception as exc:
                    _append_failure(
                        checks,
                        reasons,
                        codes,
                        "artifact_storage",
                        "storage.probe.close_failed",
                        f"storage probe client close failed: {exc}",
                    )
    stale_after = timedelta(seconds=settings.SKILL_AGENT_READINESS_STALE_SECONDS)
    now = datetime.now(timezone.utc)

    if is_edge:
        worker_inst = getattr(app.state, "worker", None)
        if not worker_inst:
            _append_failure(
                checks,
                reasons,
                codes,
                "worker",
                "edge.heartbeat.missing",
                "edge worker heartbeat missing",
            )
        else:
            last_hb = getattr(worker_inst, "last_heartbeat_at", None)
            if last_hb is None:
                _append_failure(
                    checks,
                    reasons,
                    codes,
                    "worker",
                    "edge.heartbeat.missing",
                    "edge worker heartbeat missing",
                )
            elif now - last_hb > stale_after:
                _append_failure(
                    checks,
                    reasons,
                    codes,
                    "worker",
                    "edge.heartbeat.stale",
                    "edge worker heartbeat stale",
                )
    elif settings.SKILL_AGENT_WORKER_ENABLED:
        worker_inst = getattr(app.state, "worker", None)
        if not worker_inst:
            _append_failure(
                checks,
                reasons,
                codes,
                "worker",
                "worker.instance_missing",
                "worker enabled but worker instance not found",
            )
        else:
            last_success = getattr(worker_inst, "last_successful_loop_at", None)
            if last_success is None:
                _append_failure(
                    checks,
                    reasons,
                    codes,
                    "worker",
                    "worker.loop.missing",
                    "central run worker successful loop missing",
                )
            elif now - last_success > stale_after:
                _append_failure(
                    checks,
                    reasons,
                    codes,
                    "worker",
                    "worker.loop.stale",
                    "central run worker loop stale",
                )

    if not is_edge and not settings.SKILL_AGENT_INSECURE_MODE:
        if not settings.SKILL_AGENT_CENTRAL_BASE_URL:
            _append_failure(
                checks,
                reasons,
                codes,
                "credential_broker",
                "credential_broker.missing_base_url",
                "missing central base url for credential broker",
            )
        else:
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(2.0, connect=1.0)) as client:
                    broker_health = f"{settings.SKILL_AGENT_CENTRAL_BASE_URL.rstrip('/')}/api/v1/health"
                    res = await client.get(broker_health)
                    if res.status_code >= 500:
                        _append_failure(
                            checks,
                            reasons,
                            codes,
                            "credential_broker",
                            "credential_broker.server_error",
                            "credential broker returned server error",
                        )
            except Exception:
                _append_failure(
                    checks,
                    reasons,
                    codes,
                    "credential_broker",
                    "credential_broker.connectivity_failed",
                    "credential broker connectivity check failed",
                )

    all_ok = all(checks.values())
    if not all_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        status_str = "degraded" if not db_ok else "not_ready"
    else:
        status_str = "ok"

    return {
        "status": status_str,
        "database": "not_required" if is_edge else "connected" if db_ok else "disconnected",
        "service": "nodeskclaw-agent",
        "role": settings.SKILL_AGENT_ROLE,
        "checks": checks,
        "codes": codes,
        "reasons": reasons,
    }


@app.get("/metrics")
async def metrics(db: AsyncSession = Depends(get_db)):
    schema = settings.SKILL_AGENT_SCHEMA
    counts = {}
    try:
        res = await db.execute(
            text(
                f"""
                SELECT status, count(*) as count
                FROM "{schema}".runs
                GROUP BY status
                """
            )
        )
        for row in res.mappings().all():
            counts[row["status"]] = row["count"]
    except Exception:
        logger.exception("metrics query failed")
    metrics_payload: dict[str, Any] = {"definitions": {}, "counters": [], "histograms": []}
    try:
        metrics_payload = get_registry().snapshot()
    except Exception:
        logger.exception("metrics registry snapshot failed")
    return {
        "service": "nodeskclaw-agent",
        "role": settings.SKILL_AGENT_ROLE,
        "runs_by_status": counts,
        "metrics": metrics_payload,
    }
