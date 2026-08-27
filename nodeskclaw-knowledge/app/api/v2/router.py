"""API v2 router — domain sub-routers."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.agent_tools import router as agent_tools_router
from app.api.v2.applications import router as applications_router
from app.api.v2.artifacts import router as artifacts_router
from app.api.v2.assets import router as assets_router
from app.api.v2.engineering import router as engineering_router
from app.api.v2.evidence import router as evidence_router
from app.api.v2.knowledge_models import router as knowledge_models_router
from app.api.v2.quality import router as quality_router
from app.api.v2.query_intelligence import router as query_intelligence_router
from app.api.v2.retrieval import router as retrieval_router
from app.api.v2.runtime_admin import kb_runtime_router, router as runtime_admin_router
from app.api.v2.translations import router as translations_router
from app.mcp_server import router as mcp_router

router = APIRouter(tags=["v2"])
router.include_router(assets_router)
router.include_router(artifacts_router)
router.include_router(applications_router)
router.include_router(engineering_router)
router.include_router(knowledge_models_router)
router.include_router(quality_router)
router.include_router(query_intelligence_router)
router.include_router(retrieval_router)
router.include_router(evidence_router)
router.include_router(translations_router)
router.include_router(runtime_admin_router)
router.include_router(kb_runtime_router)
router.include_router(agent_tools_router)
router.include_router(mcp_router)
