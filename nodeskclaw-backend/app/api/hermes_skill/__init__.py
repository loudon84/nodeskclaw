from fastapi import APIRouter

from app.api.hermes_skill.skills_router import router as skills_router
from app.api.hermes_skill.installations_router import router as installations_router

router = APIRouter()

router.include_router(skills_router)
router.include_router(installations_router)
