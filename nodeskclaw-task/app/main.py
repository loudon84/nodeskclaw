"""FastAPI application entry point."""

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router, mcp_router, worker_api_router
from app.core.access_log import AutotaskAccessLogMiddleware
from app.core.config import settings
from app.core.deps import engine
from app.core.exceptions import register_exception_handlers
from app.core.middleware import NoCacheAPIMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


async def _auto_migrate() -> None:
    from alembic.config import Config

    from alembic import command

    def _run() -> None:
        backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cfg = Config(os.path.join(backend_root, "alembic.ini"))
        cfg.set_main_option("script_location", os.path.join(backend_root, "alembic"))
        command.upgrade(cfg, "head")

    await asyncio.to_thread(_run)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("nodeskclaw-task %s starting", settings.APP_VERSION)

    if os.environ.get("SKIP_AUTO_MIGRATE") != "1":
        try:
            await _auto_migrate()
            logger.info("数据库迁移完成")
        except Exception:
            logger.exception("数据库迁移失败")
            raise

    if settings.SEED_DATA_ENABLED:
        from app.core.deps import async_session_factory
        from app.startup.seed import run_seed

        await run_seed(async_session_factory)

    yield
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/docs",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(NoCacheAPIMiddleware)
app.add_middleware(AutotaskAccessLogMiddleware)
register_exception_handlers(app)

app.include_router(api_router, prefix="/api/v1/autotask")
app.include_router(worker_api_router, prefix="/api/v1/autotask")
app.include_router(mcp_router, prefix="/api/v1/autotask")


@app.get("/health")
async def root_health():
    return {"status": "ok"}
