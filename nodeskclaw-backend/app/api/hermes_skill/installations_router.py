import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_org_admin, require_org_member
from app.core.exceptions import NotFoundError
from app.models.base import not_deleted
from app.models.hermes_skill.skill_installation import HermesSkillInstallation
from app.schemas.hermes_skill.skill_installation import (
    InstallationCreate,
    InstallationRead,
    InstallationFilterParams,
    InstallationListResult,
)
from app.services.hermes_skill.skill_installer import SkillInstaller
from app.services.hermes_skill.permission_checker import PermissionChecker

router = APIRouter()


def _ok(data: Any = None, message: str = "success") -> dict:
    return {"code": 0, "message": message, "data": data}


@router.get("/skill-installations")
async def list_installations(
    skill_id: str | None = None,
    agent_id: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    _, org = user_org
    query = select(HermesSkillInstallation).where(
        not_deleted(HermesSkillInstallation),
        HermesSkillInstallation.org_id == org.id,
    )
    count_query = select(func.count()).select_from(HermesSkillInstallation).where(
        not_deleted(HermesSkillInstallation),
        HermesSkillInstallation.org_id == org.id,
    )

    if skill_id:
        query = query.where(HermesSkillInstallation.skill_id == skill_id)
        count_query = count_query.where(HermesSkillInstallation.skill_id == skill_id)
    if agent_id:
        query = query.where(HermesSkillInstallation.agent_id == agent_id)
        count_query = count_query.where(HermesSkillInstallation.agent_id == agent_id)
    if status:
        query = query.where(HermesSkillInstallation.status == status)
        count_query = count_query.where(HermesSkillInstallation.status == status)

    total = (await db.execute(count_query)).scalar() or 0
    offset = (page - 1) * page_size
    query = query.order_by(HermesSkillInstallation.created_at.desc()).offset(offset).limit(page_size)

    result = await db.execute(query)
    items = [InstallationRead.model_validate(i).model_dump() for i in result.scalars().all()]

    return _ok(InstallationListResult(items=items, total=total, page=page, page_size=page_size).model_dump())


@router.post("/skill-installations")
async def create_installation(
    body: InstallationCreate,
    user_org=Depends(require_org_admin),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "skill:install")
    installer = SkillInstaller(db)
    installation = await installer.install(
        skill_id=body.skill_id,
        agent_id=body.agent_id,
        org_id=org.id,
        profile_id=body.profile_id,
        workspace_id=body.workspace_id,
        install_mode=body.install_mode,
        conflict_strategy=body.conflict_strategy,
        installed_by=user.id if user else None,
    )
    await db.commit()
    return _ok(InstallationRead.model_validate(installation).model_dump())


@router.delete("/skill-installations/{installation_id}")
async def delete_installation(
    installation_id: str,
    user_org=Depends(require_org_admin),
    db: AsyncSession = Depends(get_db),
):
    _, org = user_org
    installer = SkillInstaller(db)
    installation = await installer.uninstall(installation_id, org.id)
    await db.commit()
    return _ok(InstallationRead.model_validate(installation).model_dump())


@router.post("/skill-installations/{installation_id}/sync")
async def sync_installation(
    installation_id: str,
    user_org=Depends(require_org_admin),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "skill:install")
    installer = SkillInstaller(db)
    installation = await installer.sync_installation(installation_id, org.id)
    await db.commit()
    return _ok(InstallationRead.model_validate(installation).model_dump())
