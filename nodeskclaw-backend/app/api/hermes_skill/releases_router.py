from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_org_member
from app.schemas.hermes_skill.skill_release import (
    SkillReleaseCreateRequest,
    SkillReleaseRead,
)
from app.services.hermes_skill.permission_checker import PermissionChecker
from app.services.hermes_skill.skill_release_service import SkillReleaseService

router = APIRouter()


def _ok(data: Any = None, message: str = "success") -> dict:
    return {"code": 0, "message": message, "data": data}


@router.get("/skills/{skill_id}/releases")
async def list_skill_releases(
    skill_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await PermissionChecker.require_permission(db, user.id, org.id, "skill:view")
    items = await SkillReleaseService(db).list_releases(org.id, skill_id)
    return _ok(
        {
            "items": [SkillReleaseRead.model_validate(i).model_dump() for i in items],
            "total": len(items),
        }
    )


@router.post("/skills/{skill_id}/releases")
async def create_skill_release(
    skill_id: str,
    body: SkillReleaseCreateRequest,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await PermissionChecker.require_permission(db, user.id, org.id, "skill:manage")
    release = await SkillReleaseService(db).create_draft_from_skill(
        org_id=org.id,
        skill_id=skill_id,
        operator_user_id=user.id,
        notes=body.notes,
        version=body.version,
        connector_instance_ids=body.connector_instance_ids,
        knowledge_refs=body.knowledge_refs,
    )
    await db.commit()
    return _ok(SkillReleaseRead.model_validate(release).model_dump())


@router.post("/skills/{skill_id}/releases/{release_id}/publish")
async def publish_skill_release(
    skill_id: str,
    release_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await PermissionChecker.require_permission(db, user.id, org.id, "skill:manage")
    release = await SkillReleaseService(db).publish(
        org_id=org.id,
        skill_id=skill_id,
        release_id=release_id,
        operator_user_id=user.id,
    )
    await db.commit()
    return _ok(SkillReleaseRead.model_validate(release).model_dump())


@router.post("/skills/{skill_id}/releases/{release_id}/deprecate")
async def deprecate_skill_release(
    skill_id: str,
    release_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await PermissionChecker.require_permission(db, user.id, org.id, "skill:manage")
    release = await SkillReleaseService(db).deprecate(
        org_id=org.id,
        skill_id=skill_id,
        release_id=release_id,
    )
    await db.commit()
    return _ok(SkillReleaseRead.model_validate(release).model_dump())
