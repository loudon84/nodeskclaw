from fastapi import APIRouter

from app.api.hermes_skill.connectors_router import router as connectors_router
from app.api.hermes_skill.edge_nodes_router import router as edge_nodes_router
from app.api.hermes_skill.skills_router import router as skills_router
from app.api.hermes_skill.releases_router import router as releases_router
from app.api.hermes_skill.installations_router import router as installations_router

router = APIRouter()

router.include_router(skills_router)
router.include_router(releases_router)
router.include_router(installations_router)
router.include_router(connectors_router)
router.include_router(edge_nodes_router)
