"""FastAPI application entry point."""

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def _restore_logging_after_alembic(saved_handlers: list, saved_level: int) -> None:
    root_log = logging.getLogger()
    root_log.handlers = saved_handlers
    root_log.level = saved_level
    for name in logging.Logger.manager.loggerDict:
        obj = logging.Logger.manager.loggerDict[name]
        if isinstance(obj, logging.Logger) and obj.disabled:
            obj.disabled = False


async def _auto_migrate() -> None:
    from alembic.config import Config

    from alembic import command

    def _run() -> None:
        root_log = logging.getLogger()
        saved_handlers = root_log.handlers[:]
        saved_level = root_log.level
        backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cfg = Config(os.path.join(backend_root, "alembic.ini"))
        cfg.set_main_option("script_location", os.path.join(backend_root, "alembic"))
        try:
            command.upgrade(cfg, "head")
        finally:
            _restore_logging_after_alembic(saved_handlers, saved_level)

    await asyncio.to_thread(_run)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("%s %s starting", settings.APP_NAME, settings.APP_VERSION)
    if os.environ.get("SKIP_AUTO_MIGRATE") != "1":
        try:
            logger.info("running alembic upgrade head")
            await _auto_migrate()
            logger.info("migration complete")
        except Exception:
            logger.exception("migration failed")
            raise
    else:
        logger.info("SKIP_AUTO_MIGRATE=1")
    yield


app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
register_exception_handlers(app)
app.include_router(api_router, prefix="/api/v1")
