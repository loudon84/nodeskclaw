from contextlib import asynccontextmanager
import asyncio
import logging

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internal_runs import router as internal_runs_router
from app.config import settings
from app.db import get_db, init_schema
from app.services.edge_worker import EdgeWorker
from app.services.worker import RunWorker

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_schema()
    worker_task = None
    worker = None
    if settings.SKILL_AGENT_WORKER_ENABLED:
        if settings.SKILL_AGENT_ROLE == "edge":
            worker = EdgeWorker()
            worker_task = asyncio.create_task(worker.start())
            logger.info("nodeskclaw-agent edge worker enabled")
        else:
            worker = RunWorker()
            worker_task = asyncio.create_task(worker.start())
            logger.info("nodeskclaw-agent worker enabled")
    yield
    if worker:
        worker.stop()
    if worker_task and not worker_task.done():
        worker_task.cancel()


app = FastAPI(title="nodeskclaw-agent", version="0.1.0", lifespan=lifespan)
app.include_router(internal_runs_router)


@app.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    db_ok = True
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
        logger.exception("database health check failed")
    status_str = "ok" if db_ok else "degraded"
    return {
        "status": status_str,
        "database": "connected" if db_ok else "disconnected",
        "service": "nodeskclaw-agent",
        "role": settings.SKILL_AGENT_ROLE,
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
