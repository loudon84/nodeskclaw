import io
import zipfile
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_org_member
from app.core.exceptions import ArtifactBatchSizeExceededError
from app.schemas.hermes_skill.artifact_schema import ArtifactDetail, ArtifactSummary, ArtifactPreviewResponse
from app.services.hermes_skill.artifact_service import ArtifactService, MAX_BATCH_DOWNLOAD_BYTES
from app.services.hermes_skill.permission_checker import PermissionChecker

router = APIRouter()


def _ok(data: Any = None, message: str = "success") -> dict:
    return {"code": 0, "message": message, "data": data}


@router.get("/artifacts")
async def list_artifacts(
    task_id: str | None = Query(None),
    workspace_id: str | None = Query(None),
    skill_id: str | None = Query(None),
    content_type: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_artifact:view")
    service = ArtifactService(db)
    items, total = await service.list_artifacts(
        org_id=org.id,
        user_id=user.id if user else None,
        task_id=task_id,
        workspace_id=workspace_id,
        skill_id=skill_id,
        content_type=content_type,
        page=page,
        page_size=page_size,
    )
    summaries = [ArtifactSummary.model_validate(a).model_dump() for a in items]
    return _ok({"items": summaries, "total": total, "page": page, "page_size": page_size})


@router.get("/artifacts/{artifact_id}")
async def get_artifact(
    artifact_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_artifact:view")
    service = ArtifactService(db)
    artifact = await service.get_artifact(artifact_id, org.id)
    return _ok(ArtifactDetail.model_validate(artifact).model_dump())


@router.get("/artifacts/{artifact_id}/preview")
async def preview_artifact(
    artifact_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_artifact:view")
    service = ArtifactService(db)
    artifact, content = await service.preview(artifact_id, org.id)
    resp = ArtifactPreviewResponse(
        artifact_id=artifact_id,
        content_type=artifact.content_type or "text/plain",
        content=content,
    )
    return _ok(resp.model_dump())


@router.get("/artifacts/{artifact_id}/download")
async def download_artifact(
    artifact_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_artifact:download")
    service = ArtifactService(db)
    file_path = await service.download(
        artifact_id, org.id,
        actor_id=user.id if user else "",
        actor_name=user.display_name if user else None,
    )
    return FileResponse(
        path=str(file_path),
        filename=file_path.name,
        media_type="application/octet-stream",
    )


@router.delete("/artifacts/{artifact_id}")
async def delete_artifact(
    artifact_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_artifact:delete")
    service = ArtifactService(db)
    await service.soft_delete(
        artifact_id, org.id,
        actor_id=user.id if user else "",
        actor_name=user.display_name if user else None,
    )
    return _ok(message="已删除")


@router.post("/tasks/{task_id}/artifacts/download")
async def batch_download_artifacts(
    task_id: str,
    artifact_ids: list[str],
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_artifact:download")
    service = ArtifactService(db)

    total_size = 0
    paths = []
    for aid in artifact_ids:
        artifact = await service.get_artifact(aid, org.id)
        size = artifact.size_bytes or 0
        total_size += size
        if total_size > MAX_BATCH_DOWNLOAD_BYTES:
            raise ArtifactBatchSizeExceededError()
        from pathlib import Path
        p = Path(artifact.file_path)
        if p.is_file():
            paths.append((artifact.file_name, p))

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, path in paths:
            zf.write(path, name)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=artifacts.zip"},
    )
