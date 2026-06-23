from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_org_member
from app.schemas.hermes_skill.runtime_skill_registration import (
    RuntimeSkillRegisterRequest,
    RuntimeSkillRegisterResponse,
)
from app.services.hermes_skill.permission_checker import PermissionChecker
from app.services.hermes_skill.runtime_skill_registration_service import (
    RuntimeSkillRegistrationService,
)

router = APIRouter()


def _ok(data: RuntimeSkillRegisterResponse, message: str = "success") -> dict:
    return {"code": 0, "message": message, "data": data.model_dump()}


@router.post(
    "/agents/{agent_profile}/skills/{runtime_skill_id}/register-to-org-mcp",
    response_model=None,
)
async def register_runtime_skill_to_org_mcp(
    agent_profile: str,
    runtime_skill_id: str,
    body: RuntimeSkillRegisterRequest,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_agent:manage")
        await PermissionChecker.require_permission(db, user.id, org.id, "skill:authorize")

    service = RuntimeSkillRegistrationService(db)
    result = await service.register_to_org_mcp(
        org_id=org.id,
        operator_user_id=user.id if user else "",
        agent_profile=agent_profile,
        runtime_skill_id=runtime_skill_id,
        request=body,
    )
    await db.commit()
    return _ok(result)
