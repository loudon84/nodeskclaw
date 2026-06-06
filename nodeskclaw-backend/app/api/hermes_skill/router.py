from fastapi import APIRouter

from app.api.hermes_skill.skills_router import router as skills_router
from app.api.hermes_skill.installations_router import router as installations_router
from app.api.hermes_skill.collections_router import router as collections_router
from app.api.hermes_skill.registries_router import router as registries_router
from app.api.hermes_skill.imports_router import router as imports_router
from app.api.hermes_skill.mcp_router import router as mcp_router
from app.api.hermes_skill.audit_router import router as audit_router

router = APIRouter()

router.include_router(skills_router)
router.include_router(installations_router)
router.include_router(collections_router)
router.include_router(registries_router)
router.include_router(imports_router)
router.include_router(mcp_router)
router.include_router(audit_router)
