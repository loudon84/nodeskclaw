from app.core.feature_gate import feature_gate
from fastapi import APIRouter

from app.api.hermes_skill.skills_router import router as skills_router
from app.api.hermes_skill.installations_router import router as installations_router
from app.api.hermes_skill.collections_router import router as collections_router
from app.api.hermes_skill.registries_router import router as registries_router
from app.api.hermes_skill.imports_router import router as imports_router
from app.api.hermes_skill.mcp_router import router as mcp_router
from app.api.hermes_skill.audit_router import router as audit_router
from app.api.hermes_skill.tasks_router import router as tasks_router
from app.api.hermes_skill.artifacts_router import router as artifacts_router
from app.api.hermes_skill.diagnostics_router import router as diagnostics_router
from app.api.hermes_skill.compat_router import router as compat_router
from app.api.hermes_skill.agents_runtime_router import router as agents_runtime_router
from app.api.hermes_skill.agents_bind_router import router as agents_bind_router
from app.api.hermes_skill.queue_router import router as queue_router
from app.api.hermes_skill.runtime_control_router import router as runtime_control_router
from app.api.hermes_skill.authorizations_router import router as authorizations_router
from app.api.hermes_skill.metrics_router import router as metrics_router
from app.api.hermes_skill.client_router import router as client_router
from app.api.hermes_skill.task_result_router import router as task_result_router

router = APIRouter()

router.include_router(skills_router)
router.include_router(installations_router)
router.include_router(collections_router)
router.include_router(registries_router)
router.include_router(imports_router)
router.include_router(mcp_router)
router.include_router(audit_router)
router.include_router(tasks_router)
router.include_router(artifacts_router)
router.include_router(diagnostics_router)
router.include_router(agents_bind_router)
router.include_router(agents_runtime_router)
router.include_router(queue_router)
router.include_router(runtime_control_router)
router.include_router(authorizations_router)
router.include_router(metrics_router)
router.include_router(client_router)
router.include_router(task_result_router)
router.include_router(compat_router)

if feature_gate.is_ee:
    from app.api.hermes_skill.artifacts_permission_router import router as artifacts_permission_router
    from app.api.hermes_skill.artifacts_share_router import router as artifacts_share_router
    from app.api.hermes_skill.artifacts_audit_router import router as artifacts_audit_router

    router.include_router(artifacts_permission_router)
    router.include_router(artifacts_share_router)
    router.include_router(artifacts_audit_router)
