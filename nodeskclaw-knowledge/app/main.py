"""FastAPI application entry point."""

import logging

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.integrations.nodeskclaw_backend.client import NodeskclawBackendClient
from app.integrations.ragflow.client import RagflowClient
from contextlib import asynccontextmanager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("%s %s starting", settings.APP_NAME, settings.APP_VERSION)
    backend_http = httpx.AsyncClient(timeout=10.0)
    ragflow_http = httpx.AsyncClient(
        base_url=settings.RAGFLOW_BASE_URL.rstrip("/"),
        timeout=settings.RAGFLOW_TIMEOUT_SECONDS,
        headers={"Authorization": f"Bearer {settings.RAGFLOW_API_KEY}"},
    )
    llm_http = httpx.AsyncClient(timeout=120.0)

    backend_client = NodeskclawBackendClient(http_client=backend_http)
    ragflow_client = RagflowClient(http_client=ragflow_http)
    app.state.backend_http = backend_http
    app.state.ragflow_http = ragflow_http
    app.state.llm_http = llm_http
    app.state.backend_client = backend_client
    app.state.ragflow_client = ragflow_client

    try:
        from app.integrations.llm_proxy.client import LlmProxyClient

        app.state.llm_proxy_client = LlmProxyClient(http_client=llm_http)
    except Exception:
        app.state.llm_proxy_client = None

    yield

    await backend_client.aclose()
    await ragflow_client.aclose()
    if app.state.llm_proxy_client is not None:
        await app.state.llm_proxy_client.aclose()
    await backend_http.aclose()
    await ragflow_http.aclose()
    await llm_http.aclose()
    logger.info("%s stopped", settings.APP_NAME)


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


@app.get("/health/live")
async def health_live():
    return {"status": "ok"}


@app.get("/health")
async def health():
    return {"status": "ok"}
