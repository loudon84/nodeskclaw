from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_org_member
from app.services.hermes_skill.hermes_skill_authorization_service import HermesSkillAuthorizationService
from app.services.hermes_skill.permission_checker import PermissionChecker
from app.services.hermes_skill.skill_audit_logger import SkillAuditLogger

router = APIRouter()


def _ok(data: Any = None, message: str = "success") -> dict:
    return {"code": 0, "message": message, "data": data}


class GrantBody(BaseModel):
    skill_id: str
    skill_db_id: str | None = None
    subject_type: str
    subject_id: str
    workspace_id: str | None = None
    can_list: bool = True
    can_invoke: bool = False
    can_install: bool = False
    can_manage: bool = False
    expires_at: datetime | None = None


class BulkGrantBody(BaseModel):
    skill_id: str
    skill_db_id: str | None = None
    subject_type: str
    subject_ids: list[str]
    workspace_id: str | None = None
    can_list: bool = True
    can_invoke: bool = False
    can_install: bool = False
    can_manage: bool = False


def _grant_dict(g) -> dict:
    return {
        "id": g.id,
        "org_id": g.org_id,
        "skill_id": g.skill_id,
        "skill_db_id": g.skill_db_id,
        "subject_type": g.subject_type,
        "subject_id": g.subject_id,
        "workspace_id": g.workspace_id,
        "can_list": g.can_list,
        "can_invoke": g.can_invoke,
        "can_install": g.can_install,
        "can_manage": g.can_manage,
        "expires_at": g.expires_at.isoformat() if g.expires_at else None,
        "granted_by": g.granted_by,
        "created_at": g.created_at.isoformat() if g.created_at else None,
    }


@router.get("/skill-authorizations")
async def list_authorizations(
    skill_id: str | None = Query(None),
    workspace_id: str | None = Query(None),
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "skill:authorize")
    service = HermesSkillAuthorizationService(db)
    grants = await service.list_grants(org.id, skill_id=skill_id, workspace_id=workspace_id)
    return _ok([_grant_dict(g) for g in grants])


@router.post("/skill-authorizations")
async def create_authorization(
    body: GrantBody,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "skill:authorize")
    service = HermesSkillAuthorizationService(db)
    grant = await service.create_grant(
        org.id,
        body.skill_id,
        body.subject_type,
        body.subject_id,
        skill_db_id=body.skill_db_id,
        workspace_id=body.workspace_id,
        can_list=body.can_list,
        can_invoke=body.can_invoke,
        can_install=body.can_install,
        can_manage=body.can_manage,
        expires_at=body.expires_at,
        granted_by=user.id if user else None,
    )
    audit = SkillAuditLogger(db)
    await audit.log(
        action="hermes.skill.authorization.granted",
        target_id=grant.id,
        org_id=org.id,
        actor_id=user.id if user else "",
        details={"skill_id": body.skill_id, "subject_type": body.subject_type},
    )
    await db.commit()
    return _ok(_grant_dict(grant))


@router.post("/skill-authorizations/bulk")
async def bulk_authorization(
    body: BulkGrantBody,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "skill:bulk_authorize")
    service = HermesSkillAuthorizationService(db)
    grants = await service.bulk_grant(
        org.id,
        body.skill_id,
        body.subject_type,
        body.subject_ids,
        skill_db_id=body.skill_db_id,
        workspace_id=body.workspace_id,
        can_list=body.can_list,
        can_invoke=body.can_invoke,
        can_install=body.can_install,
        can_manage=body.can_manage,
        granted_by=user.id if user else None,
    )
    audit = SkillAuditLogger(db)
    await audit.log(
        action="hermes.skill.authorization.bulk_granted",
        target_id=body.skill_id,
        org_id=org.id,
        actor_id=user.id if user else "",
        details={"count": len(grants), "subject_type": body.subject_type},
    )
    await db.commit()
    return _ok([_grant_dict(g) for g in grants])


@router.delete("/skill-authorizations/{grant_id}")
async def revoke_authorization(
    grant_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "skill:authorize")
    service = HermesSkillAuthorizationService(db)
    await service.revoke_grant(org.id, grant_id)
    audit = SkillAuditLogger(db)
    await audit.log(
        action="hermes.skill.authorization.revoked",
        target_id=grant_id,
        org_id=org.id,
        actor_id=user.id if user else "",
    )
    await db.commit()
    return _ok({"revoked": True})
