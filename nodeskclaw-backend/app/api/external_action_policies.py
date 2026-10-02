from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_org_member
from app.schemas.common import ApiResponse
from app.services.expert_external_action_policy_service import ExpertExternalActionPolicyService
from app.services.expert_gateway.expert_permission_service import ExpertPermissionService

router = APIRouter(prefix="/expert", tags=["Expert MCP Gateway"])


class PolicyReplaceBody(BaseModel):
    policies: list[dict[str, Any]] = Field(default_factory=list)


@router.get("/experts/{expert_id}/external-action-policies")
async def list_external_action_policies(
    expert_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await ExpertPermissionService.require(db, user.id, org.id, "expert:manage")
    rows = await ExpertExternalActionPolicyService(db).list_policies(org_id=org.id, expert_id=expert_id)
    return ApiResponse(data=rows)


@router.put("/experts/{expert_id}/external-action-policies")
async def replace_external_action_policies(
    expert_id: str,
    body: PolicyReplaceBody,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await ExpertPermissionService.require(db, user.id, org.id, "expert:manage")
    rows = await ExpertExternalActionPolicyService(db).replace_policies(
        org_id=org.id,
        expert_id=expert_id,
        policies=body.policies,
    )
    return ApiResponse(data=rows)
