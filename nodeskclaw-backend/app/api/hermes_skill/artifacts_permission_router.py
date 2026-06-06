from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_org_member
from app.core.feature_gate import feature_gate
from app.core.exceptions import EERequiredError
from app.schemas.hermes_skill.artifact_permission_schema import (
    ArtifactPermissionDetail,
    ArtifactPermissionGrantRequest,
    ArtifactPermissionRevokeRequest,
    ArtifactScopeChangeRequest,
)
from app.services.hermes_skill.artifact_permission_service import ArtifactPermissionService
from app.services.hermes_skill.artifact_service import ArtifactService
from app.services.hermes_skill.permission_checker import PermissionChecker

router = APIRouter()


def _ok(data: Any = None, message: str = "success") -> dict:
    return {"code": 0, "message": message, "data": data}


@router.put("/artifacts/{artifact_id}/permission")
async def change_artifact_scope(
    artifact_id: str,
    body: ArtifactScopeChangeRequest,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    if not feature_gate.is_ee:
        raise EERequiredError()
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_artifact:manage_permission")
    artifact_svc = ArtifactService(db)
    artifact = await artifact_svc.get_artifact(artifact_id, org.id)
    if user:
        await artifact_svc.ensure_artifact_permission_manageable(artifact, user.id, org.id)
    service = ArtifactPermissionService(db)
    artifact = await service.change_scope(
        artifact_id=artifact_id,
        org_id=org.id,
        new_scope=body.permission_scope,
        actor_id=user.id if user else "",
        actor_name=user.display_name if user else None,
    )
    return _ok({"permission_scope": artifact.permission_scope})


@router.post("/artifacts/{artifact_id}/permissions/grant")
async def grant_artifact_permission(
    artifact_id: str,
    body: ArtifactPermissionGrantRequest,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    if not feature_gate.is_ee:
        raise EERequiredError()
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_artifact:manage_permission")
    artifact_svc = ArtifactService(db)
    artifact = await artifact_svc.get_artifact(artifact_id, org.id)
    if user:
        await artifact_svc.ensure_artifact_permission_manageable(artifact, user.id, org.id)
    service = ArtifactPermissionService(db)
    perm = await service.grant_permission(
        artifact_id=artifact_id,
        org_id=org.id,
        user_id=body.user_id,
        permission_level=body.permission_level,
        granted_by=user.id if user else "",
        granted_by_name=user.display_name if user else None,
    )
    return _ok(ArtifactPermissionDetail.model_validate(perm).model_dump())


@router.post("/artifacts/{artifact_id}/permissions/revoke")
async def revoke_artifact_permission(
    artifact_id: str,
    body: ArtifactPermissionRevokeRequest,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    if not feature_gate.is_ee:
        raise EERequiredError()
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_artifact:manage_permission")
    artifact_svc = ArtifactService(db)
    artifact = await artifact_svc.get_artifact(artifact_id, org.id)
    if user:
        await artifact_svc.ensure_artifact_permission_manageable(artifact, user.id, org.id)
    service = ArtifactPermissionService(db)
    await service.revoke_permission(
        artifact_id=artifact_id,
        org_id=org.id,
        user_id=body.user_id,
        revoked_by=user.id if user else "",
        revoked_by_name=user.display_name if user else None,
    )
    return _ok(message="已撤销")


@router.get("/artifacts/{artifact_id}/permissions")
async def list_artifact_permissions(
    artifact_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    if not feature_gate.is_ee:
        raise EERequiredError()
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_artifact:view")
    artifact_svc = ArtifactService(db)
    artifact = await artifact_svc.get_artifact(artifact_id, org.id)
    if user:
        await artifact_svc.ensure_artifact_permission_manageable(artifact, user.id, org.id)
    service = ArtifactPermissionService(db)
    perms = await service.list_permissions(artifact_id, org.id)
    items = [ArtifactPermissionDetail.model_validate(p).model_dump() for p in perms]
    return _ok(items)
