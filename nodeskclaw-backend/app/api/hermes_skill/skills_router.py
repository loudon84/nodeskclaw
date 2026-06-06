import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_org_admin, require_org_member
from app.core.exceptions import NotFoundError, ConflictError, ForbiddenError
from app.models.base import not_deleted
from app.models.hermes_skill.skill import HermesSkill
from app.models.hermes_skill.skill_installation import HermesSkillInstallation
from app.schemas.hermes_skill.skill import (
    SkillRead,
    SkillFilterParams,
    SkillListResult,
    ScanTriggerResult,
)
from app.schemas.hermes_skill.common import READ_ONLY_SOURCE_TYPES
from app.services.hermes_skill.skill_scanner import SkillScanner, ScanError
from app.services.hermes_skill.permission_checker import PermissionChecker

router = APIRouter()


def _ok(data: Any = None, message: str = "success") -> dict:
    return {"code": 0, "message": message, "data": data}


@router.get("/skills")
async def list_skills(
    source_type: str | None = None,
    is_active: bool | None = None,
    is_mcp_exposed: bool | None = None,
    category: str | None = None,
    agent_type: str | None = None,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    _, org = user_org
    query = select(HermesSkill).where(
        not_deleted(HermesSkill),
        HermesSkill.org_id == org.id,
    )
    count_query = select(func.count()).select_from(HermesSkill).where(
        not_deleted(HermesSkill),
        HermesSkill.org_id == org.id,
    )

    if source_type:
        query = query.where(HermesSkill.source_type == source_type)
        count_query = count_query.where(HermesSkill.source_type == source_type)
    if is_active is not None:
        query = query.where(HermesSkill.is_active == is_active)
        count_query = count_query.where(HermesSkill.is_active == is_active)
    if is_mcp_exposed is not None:
        query = query.where(HermesSkill.is_mcp_exposed == is_mcp_exposed)
        count_query = count_query.where(HermesSkill.is_mcp_exposed == is_mcp_exposed)
    if category:
        query = query.where(HermesSkill.category == category)
        count_query = count_query.where(HermesSkill.category == category)
    if agent_type:
        query = query.where(HermesSkill.agent_type == agent_type)
        count_query = count_query.where(HermesSkill.agent_type == agent_type)
    if keyword:
        pattern = f"%{keyword}%"
        kw_filter = HermesSkill.name.ilike(pattern) | HermesSkill.skill_id.ilike(pattern)
        query = query.where(kw_filter)
        count_query = count_query.where(kw_filter)

    total = (await db.execute(count_query)).scalar() or 0
    offset = (page - 1) * page_size
    query = query.order_by(HermesSkill.created_at.desc()).offset(offset).limit(page_size)

    result = await db.execute(query)
    items = [SkillRead.model_validate(s).model_dump() for s in result.scalars().all()]

    return _ok(SkillListResult(items=items, total=total, page=page, page_size=page_size).model_dump())


@router.get("/skills/{skill_db_id}")
async def get_skill(
    skill_db_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    _, org = user_org
    skill = await db.get(HermesSkill, skill_db_id)
    if not skill or skill.deleted_at is not None or skill.org_id != org.id:
        raise NotFoundError("Skill 不存在", "errors.skill.not_found")
    return _ok(SkillRead.model_validate(skill).model_dump())


@router.post("/skills/scan")
async def trigger_scan(
    source_types: list[str] = Query(None),
    user_org=Depends(require_org_admin),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "skill:scan")
    scanner = SkillScanner(db)
    result = await scanner.scan_all(org_id=org.id, source_types=source_types or None)
    scan_data = ScanTriggerResult(
        scanned_count=result.scanned_count,
        added_count=result.added_count,
        updated_count=result.updated_count,
        deleted_count=result.deleted_count,
        failed_count=result.failed_count,
        is_partial=result.is_partial,
    ).model_dump()
    scan_data["errors"] = [
        {"path": e.path, "message": e.message} for e in result.errors
    ]
    return _ok(scan_data)


@router.post("/skills/{skill_db_id}/enable")
async def enable_skill(
    skill_db_id: str,
    user_org=Depends(require_org_admin),
    db: AsyncSession = Depends(get_db),
):
    _, org = user_org
    skill = await db.get(HermesSkill, skill_db_id)
    if not skill or skill.deleted_at is not None or skill.org_id != org.id:
        raise NotFoundError("Skill 不存在", "errors.skill.not_found")
    skill.is_active = True
    await db.commit()
    await db.refresh(skill)
    return _ok(SkillRead.model_validate(skill).model_dump())


@router.post("/skills/{skill_db_id}/disable")
async def disable_skill(
    skill_db_id: str,
    user_org=Depends(require_org_admin),
    db: AsyncSession = Depends(get_db),
):
    _, org = user_org
    skill = await db.get(HermesSkill, skill_db_id)
    if not skill or skill.deleted_at is not None or skill.org_id != org.id:
        raise NotFoundError("Skill 不存在", "errors.skill.not_found")
    skill.is_active = False
    await db.commit()
    await db.refresh(skill)
    return _ok(SkillRead.model_validate(skill).model_dump())


@router.delete("/skills/{skill_db_id}")
async def delete_skill(
    skill_db_id: str,
    user_org=Depends(require_org_admin),
    db: AsyncSession = Depends(get_db),
):
    _, org = user_org
    skill = await db.get(HermesSkill, skill_db_id)
    if not skill or skill.deleted_at is not None or skill.org_id != org.id:
        raise NotFoundError("Skill 不存在", "errors.skill.not_found")

    active_install = await db.execute(
        select(HermesSkillInstallation).where(
            not_deleted(HermesSkillInstallation),
            HermesSkillInstallation.skill_id == skill.skill_id,
            HermesSkillInstallation.status == "installed",
        )
    )
    if active_install.scalar_one_or_none():
        raise ConflictError("存在活跃安装，无法删除", "errors.skill.has_active_installations")

    skill.soft_delete()
    await db.commit()
    return _ok()
