import uuid
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_org_admin, require_org_member
from app.core.exceptions import NotFoundError
from app.models.base import not_deleted
from app.models.hermes_skill.skill_registry_source import HermesSkillRegistry
from app.services.hermes_skill.registry_source_manager import RegistrySourceManager

router = APIRouter()


def _ok(data: Any = None, message: str = "success") -> dict:
    return {"code": 0, "message": message, "data": data}


@router.get("/skill-registries")
async def list_registries(
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    _, org = user_org
    result = await db.execute(
        select(HermesSkillRegistry).where(
            not_deleted(HermesSkillRegistry),
            HermesSkillRegistry.org_id == org.id,
        ).order_by(HermesSkillRegistry.created_at.desc())
    )
    items = [{"id": r.id, "name": r.name, "source_type": r.source_type, "url": r.url, "is_enabled": r.is_enabled, "last_sync_status": r.last_sync_status} for r in result.scalars().all()]
    return _ok(items)


@router.post("/skill-registries")
async def create_registry(
    name: str,
    source_type: str,
    url: str = "",
    branch: str = "main",
    auth_mode: str = "none",
    auth_secret_ref: str | None = None,
    user_org=Depends(require_org_admin),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    manager = RegistrySourceManager(db)
    registry = await manager.create_source(
        org_id=org.id,
        name=name,
        source_type=source_type,
        url=url,
        branch=branch,
        auth_mode=auth_mode,
        auth_secret_ref=auth_secret_ref,
        created_by=user.id if user else None,
    )
    await db.commit()
    return _ok({"id": registry.id, "name": registry.name})


@router.post("/skill-registries/{registry_id}/sync")
async def sync_registry(
    registry_id: str,
    user_org=Depends(require_org_admin),
    db: AsyncSession = Depends(get_db),
):
    _, org = user_org
    manager = RegistrySourceManager(db)
    registry = await manager.sync(registry_id, org.id)
    await db.commit()
    return _ok({"id": registry.id, "last_sync_status": registry.last_sync_status})


@router.delete("/skill-registries/{registry_id}")
async def delete_registry(
    registry_id: str,
    user_org=Depends(require_org_admin),
    db: AsyncSession = Depends(get_db),
):
    _, org = user_org
    manager = RegistrySourceManager(db)
    await manager.delete_source(registry_id, org.id)
    await db.commit()
    return _ok()
