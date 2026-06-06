from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_org_member
from app.services.hermes_skill.artifact_share_service import ArtifactShareService
from app.services.hermes_skill.download_token_service import DownloadTokenService
from app.services.hermes_skill.artifact_service import ArtifactService
from app.services.hermes_skill.permission_checker import PermissionChecker
from app.schemas.hermes_skill.artifact_share_schema import ArtifactShareRequest, ArtifactShareResponse
from app.core.exceptions import ArtifactFileNotFoundError
from pathlib import Path

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
    artifact_service = ArtifactService(db)

    artifact = await artifact_service.get_artifact_by_token(token, token_service)
    if not artifact:
        from app.core.exceptions import ArtifactTokenExpiredError
        raise ArtifactTokenExpiredError()

    file_path = Path(artifact.file_path)
    workspace_root = artifact_service._get_workspace_root(artifact)
    if workspace_root:
        from app.services.hermes_skill.path_guard import PathGuard
        PathGuard.validate_file_for_download(file_path, workspace_root)
    else:
        from app.services.hermes_skill.path_guard import PathGuard
        PathGuard.validate_file_for_download(file_path, Path("/tmp"))

    if not file_path.is_file():
        raise ArtifactFileNotFoundError()

    return FileResponse(
        path=str(file_path),
        filename=artifact.file_name,
        media_type="application/octet-stream",
    )
