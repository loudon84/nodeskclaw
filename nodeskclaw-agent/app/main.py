import asyncio
from contextlib import asynccontextmanager
import logging
import os
from typing import Any

import httpx
from fastapi import Depends, FastAPI, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internal_runs import router as internal_runs_router
from app.config import alembic_version_relation, settings
from app.db import get_db
from app.services.edge_worker import EdgeWorker
from app.services.storage_port import get_storage_driver
from app.services.worker import RunWorker

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # DDL operations are strictly handled by Alembic migrations.
    # App startup maintains zero-DDL policy in production.
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


@app.get("/health/ready")
@app.get("/healthz/ready")
@app.get("/health")
async def health_ready(response: Response, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    reasons: list[str] = []
    checks: dict[str, bool] = {
        "database": True,
        "migration": True,
        "config_security": True,
        "artifact_storage": True,
        "credential_broker": True,
        "worker": True,
    }

    # 1. DB connectivity
    db_ok = True
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
        checks["database"] = False
        reasons.append("database connectivity check failed")
        logger.exception("database health check failed")

    # 2. Migration status (alembic_version)
    if db_ok:
        try:
            res = await db.execute(
                text(f"SELECT version_num FROM {alembic_version_relation()} LIMIT 1")
            )
            version_row = res.first()
            if not version_row or not version_row[0]:
                checks["migration"] = False
                reasons.append("alembic migration head missing")
        except Exception:
            # Table might not exist yet if not migrated
            checks["migration"] = False
            reasons.append("alembic_version check failed")

    # 3. Safe production config check
    if not settings.SKILL_AGENT_INSECURE_MODE:
        if settings.SKILL_AGENT_INTERNAL_TOKEN in ("change-me-skill-agent-token", "", "default"):
            checks["config_security"] = False
            reasons.append("insecure default internal token in production")

        if settings.SKILL_AGENT_ARTIFACT_DIR.startswith("/tmp") or settings.SKILL_AGENT_ARTIFACT_DIR.startswith("\\tmp"):
            checks["config_security"] = False
            reasons.append("ephemeral artifact directory configured in production")

        if settings.SKILL_AGENT_ROLE == "edge":
            if not settings.SKILL_AGENT_EDGE_TOKEN:
                checks["config_security"] = False
                reasons.append("missing edge token")
            if not settings.SKILL_AGENT_EDGE_NODE_ID:
                checks["config_security"] = False
                reasons.append("missing edge node id")
            if not settings.SKILL_AGENT_CENTRAL_BASE_URL.startswith("https://"):
                checks["config_security"] = False
                reasons.append("insecure edge central base url (must be https://)")

    # 4. StoragePort isolation probe
    try:
        if settings.SKILL_AGENT_ROLE != "edge":
            driver = get_storage_driver()
            # Probe driver instance readiness without polluting business data
            if hasattr(driver, "exists"):
                res_exists = driver.exists(".probe_health_check_nonexistent")
                if asyncio.iscoroutine(res_exists):
                    await res_exists
        else:
            os.makedirs(settings.SKILL_AGENT_ARTIFACT_DIR, exist_ok=True)
    except Exception as exc:
        checks["artifact_storage"] = False
        reasons.append(f"cannot create or access artifact storage directory: {exc}")

    # 5. Worker loop / edge heartbeat freshness check
    if settings.SKILL_AGENT_WORKER_ENABLED:
        worker_inst = getattr(app.state, "worker", None)
        if not worker_inst:
            checks["worker"] = False
            reasons.append("worker enabled but worker instance not found")
        else:
            if settings.SKILL_AGENT_ROLE == "edge":
                # Edge role: verify last_heartbeat_at
                last_hb = getattr(worker_inst, "last_heartbeat_at", None)
                if last_hb is not None:
                    from datetime import datetime, timedelta, timezone
                    if datetime.now(timezone.utc) - last_hb > timedelta(seconds=120):
                        checks["worker"] = False
                        reasons.append("edge worker heartbeat stale")
            else:
                # Central role: verify last_loop_at
                last_loop = getattr(worker_inst, "last_loop_at", None)
                if last_loop is not None:
                    from datetime import datetime, timedelta, timezone
                    if datetime.now(timezone.utc) - last_loop > timedelta(seconds=120):
                        checks["worker"] = False
                        reasons.append("central run worker loop stale")

    # 6. Credential Broker check (production readiness)
    if not settings.SKILL_AGENT_INSECURE_MODE:
        if not settings.SKILL_AGENT_CENTRAL_BASE_URL:
            checks["credential_broker"] = False
            reasons.append("missing central base url for credential broker")
        else:
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(2.0, connect=1.0)) as client:
                    broker_health = f"{settings.SKILL_AGENT_CENTRAL_BASE_URL.rstrip('/')}/api/health"
                    res = await client.get(broker_health)
                    if res.status_code >= 500:
                        checks["credential_broker"] = False
                        reasons.append("credential broker returned server error")
            except Exception:
                checks["credential_broker"] = False
                reasons.append("credential broker connectivity check failed")

    all_ok = all(checks.values())
    if not all_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        status_str = "degraded" if not db_ok else "not_ready"
    else:
        status_str = "ok"

    return {
        "status": status_str,
        "database": "connected" if db_ok else "disconnected",
        "service": "nodeskclaw-agent",
        "role": settings.SKILL_AGENT_ROLE,
        "checks": checks,
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
    return {
        "service": "nodeskclaw-agent",
        "role": settings.SKILL_AGENT_ROLE,
        "runs_by_status": counts,
    }
