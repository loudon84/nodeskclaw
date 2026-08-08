"""API router aggregation."""

from fastapi import APIRouter

from app.api.audit import router as audit_router
from app.api.chat import router as chat_router
from app.api.citations import router as citations_router
from app.api.dashboard import router as dashboard_router
from app.api.ingestion_jobs import router as ingestion_jobs_router
from app.api.knowledge_bases import router as knowledge_bases_router
from app.api.knowledge_sets import router as knowledge_sets_router
from app.api.retrieval import router as retrieval_router
from app.api.retrieval_profiles import profiles_router, set_profiles_router
from app.api.source_files import kb_files_router, router as source_files_router

api_router = APIRouter()
api_router.include_router(dashboard_router)
api_router.include_router(audit_router)
api_router.include_router(chat_router)
api_router.include_router(citations_router)
api_router.include_router(knowledge_bases_router)
api_router.include_router(kb_files_router)
api_router.include_router(knowledge_sets_router)
api_router.include_router(set_profiles_router)
api_router.include_router(profiles_router)
api_router.include_router(source_files_router)
api_router.include_router(ingestion_jobs_router)
api_router.include_router(retrieval_router)


@api_router.get("/health")
async def health():
    return {"status": "ok"}
