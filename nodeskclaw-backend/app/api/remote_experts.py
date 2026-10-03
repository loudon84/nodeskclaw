from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_org_member
from app.services.expert_gateway.expert_permission_service import ExpertPermissionService
from app.services.remote_expert_catalog_service import RemoteExpertCatalogService

router = APIRouter(prefix="/remote-experts", tags=["Remote Experts"])


@router.get("")
async def list_remote_experts(
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await ExpertPermissionService.require(db, user.id, org.id, "expert:invoke")
    items = await RemoteExpertCatalogService(db).list_items(org.id)
    return {"items": items}


@router.get("/{agent_ref}")
async def get_remote_expert(
    agent_ref: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await ExpertPermissionService.require(db, user.id, org.id, "expert:invoke")
    return await RemoteExpertCatalogService(db).get_item(org.id, agent_ref)
