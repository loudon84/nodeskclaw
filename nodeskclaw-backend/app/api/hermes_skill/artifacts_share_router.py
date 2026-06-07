from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_org_member
from app.core.exceptions import ArtifactFileNotFoundError, ArtifactTokenExpiredError, ArtifactNotFoundError, ArtifactWorkspaceRootUnresolvedError
from app.models.hermes_skill.hermes_artifact import HermesArtifact
from app.models.hermes_skill.hermes_task import HermesTask
from app.schemas.hermes_skill.artifact_share_schema import ArtifactShareRequest, ArtifactShareResponse
from app.services.hermes_skill.artifact_share_service import ArtifactShareService
from app.services.hermes_skill.download_token_service import DownloadTokenService
from app.services.hermes_skill.artifact_service import ArtifactService
from app.services.hermes_skill.permission_checker import PermissionChecker
from app.services.hermes_skill.artifact_audit_service import ArtifactAuditService

router = APIRouter()


def _ok(data: Any = None, message: str = "success") -> dict:
    return {"code": 0, "message": message, "data": data}


@router.post("/artifacts/{artifact_id}/share")
async def share_artifact(
    artifact_id: str,
    body: ArtifactShareRequest,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_artifact:share")
    service = ArtifactShareService(db)
    result = await service.share_artifact(
        artifact_id=artifact_id,
        org_id=org.id,
        actor_id=user.id if user else "",
        actor_name=user.display_name if user else None,
        max_uses=body.max_uses,
        expires_hours=body.expires_hours,
    )
    resp = ArtifactShareResponse(
        token=result["token"],
        share_url=result["share_url"],
        expires_at=result["expires_at"],
        max_uses=result["max_uses"],
    )
    return _ok(resp.model_dump())


@router.get("/artifacts/download-by-token/{token}")
async def download_by_token(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    token_service = DownloadTokenService(db)

    try:
        token_record = await token_service.get_valid_token(token)
    except ArtifactTokenExpiredError:
        raise

    artifact = await db.get(HermesArtifact, token_record.artifact_id)
    if not artifact or artifact.deleted_at is not None:
        raise ArtifactNotFoundError()

    task = await db.get(HermesTask, artifact.task_id)
    if not task or task.deleted_at is not None:
        raise ArtifactNotFoundError()

    artifact_service = ArtifactService(db)
    try:
        file_path = await artifact_service.resolve_and_validate(artifact, task)
    except ArtifactWorkspaceRootUnresolvedError:
        raise

    if not file_path.is_file():
        raise ArtifactFileNotFoundError()

    await token_service.consume_token(token_record)

    audit = ArtifactAuditService(db)
    await audit.log_artifact_action(
        action="artifact.downloaded_by_token",
        artifact_id=artifact.id,
        org_id=artifact.org_id,
        details={
            "token_id": token_record.id,
            "uses_remaining": token_record.uses_remaining,
        },
    )

    return FileResponse(
        path=str(file_path),
        filename=artifact.file_name,
        media_type="application/octet-stream",
    )
