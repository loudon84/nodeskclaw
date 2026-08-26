"""FastAPI application entry point."""

import logging

import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from sqlalchemy import text

from app.api.router import api_router
from app.api.v2.router import router as api_v2_router
from app.core.config import settings
from app.core.deps import async_session_factory
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_structured_logging
from app.integrations.nodeskclaw_backend.client import NodeskclawBackendClient
from app.integrations.ragflow.client import RagflowClient
from app.middleware.correlation import CorrelationIdMiddleware
from app.services import metrics_service

configure_structured_logging(logging.INFO)
logger = logging.getLogger(__name__)


# @lat: [[knowledge#Shared Http Clients]]
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

    from app.integrations.llm_proxy.client import LlmProxyClient

    app.state.llm_proxy_client = LlmProxyClient(http_client=llm_http)

    yield

    await backend_client.aclose()
    await ragflow_client.aclose()
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
app.add_middleware(CorrelationIdMiddleware)
register_exception_handlers(app)
app.include_router(api_router, prefix="/api/v1")
app.include_router(api_v2_router, prefix="/api/v2")


# @lat: [[knowledge#Observability Metrics]]
@app.get("/metrics")
async def metrics():
    return Response(content=metrics_service.render_metrics(), media_type=metrics_service.METRICS_CONTENT_TYPE)


@app.get("/health/live")
async def health_live():
    return {"status": "ok"}


# @lat: [[knowledge#Health Probes]]
@app.get("/health/ready")
async def health_ready():
    checks: dict[str, bool] = {}
    details: dict = {}
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        checks["database"] = False

    from app.runtime.ragflow import RagflowRuntimeAdapter

    adapter = RagflowRuntimeAdapter()
    try:
        health = await adapter.check_health()
        checks["ragflow"] = health.chunk_retrieval_ok
        details["ragflow_version"] = health.version
        details["ragflow_capabilities"] = health.capabilities
        details["ragflow_degraded"] = health.degraded_reasons
    finally:
        await adapter.aclose()

    backend = NodeskclawBackendClient()
    try:
        checks["backend"] = await backend.health_check()
    finally:
        await backend.aclose()

    ready = all(checks.values())
    payload = {
        "status": "ok" if ready else "not_ready",
        "checks": checks,
        "details": details,
    }
    if not ready:
        return JSONResponse(status_code=503, content=payload)
    return payload


@app.get("/health")
async def health():
    return {"status": "ok"}
