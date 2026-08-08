"""API router aggregation."""

from fastapi import APIRouter

from app.api.knowledge_bases import router as knowledge_bases_router
from app.api.knowledge_sets import router as knowledge_sets_router
from app.api.retrieval import router as retrieval_router
from app.api.source_files import kb_files_router, router as source_files_router

api_router = APIRouter()
api_router.include_router(knowledge_bases_router)
api_router.include_router(kb_files_router)
api_router.include_router(knowledge_sets_router)
api_router.include_router(source_files_router)
api_router.include_router(retrieval_router)


@api_router.get("/health")
async def health():
    return {"status": "ok"}
