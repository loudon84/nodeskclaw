import io
import zipfile
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_org_member
from app.core.exceptions import (
    ArtifactBatchSizeExceededError,
    ArtifactBatchEmptyError,
    ArtifactForbiddenError,
    NotFoundError,
)
from app.schemas.hermes_skill.artifact_schema import ArtifactDetail, ArtifactSummary, ArtifactPreviewResponse
from app.services.hermes_skill.artifact_service import ArtifactService, _max_batch_download_bytes
from app.services.hermes_skill.path_guard import PathGuard
from app.services.hermes_skill.permission_checker import PermissionChecker
from app.services.hermes_skill.artifact_audit_service import ArtifactAuditService

router = APIRouter()


def _ok(data: Any = None, message: str = "success") -> dict:
    return {"code": 0, "message": message, "data": data}


@router.get("/artifacts")
async def list_artifacts(
    task_id: str | None = Query(None),
    workspace_id: str | None = Query(None),
    skill_id: str | None = Query(None),
    agent_id: str | None = Query(None),
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
        agent_id=agent_id,
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
    if user:
        await service.ensure_artifact_visible(artifact, user.id, org.id)
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
    artifact, content, truncated, preview_type = await service.preview(
        artifact_id, org.id, user_id=user.id if user else None,
    )
    resp = ArtifactPreviewResponse(
        artifact_id=artifact_id,
        file_name=artifact.file_name,
        content_type=artifact.content_type or "text/plain",
        preview_type=preview_type,
        content=content,
        truncated=truncated,
        size_bytes=artifact.size_bytes,
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
    result = await service.download(
        artifact_id, org.id,
        user_id=user.id if user else None,
        actor_name=user.name if user else None,
    )
    if isinstance(result, tuple):
        artifact, raw_bytes = result
        return StreamingResponse(
            io.BytesIO(raw_bytes),
            media_type=artifact.content_type or "application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{artifact.file_name}"'},
        )
    file_path = result
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
        user_id=user.id if user else None,
        actor_name=user.name if user else None,
    )
    return _ok(message="已删除")


@router.post("/tasks/{task_id}/artifacts/download")
async def batch_download_artifacts(
    task_id: str,
    artifact_ids: list[str],
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    from app.models.hermes_skill.hermes_task import HermesTask
    from app.models.base import not_deleted
    from sqlalchemy import select

    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_artifact:batch_download")

    task = await db.get(HermesTask, task_id)
    if not task or task.deleted_at is not None or task.org_id != org.id:
        raise NotFoundError("Task 不存在", "errors.task.not_found")

    service = ArtifactService(db)
    audit = ArtifactAuditService(db)

    max_batch = _max_batch_download_bytes()
    total_size = 0
    paths = []
    for aid in artifact_ids:
        artifact = await service.get_artifact(aid, org.id)

        if artifact.task_id != task_id:
            raise ArtifactForbiddenError()

        if user:
            await service.ensure_artifact_downloadable(artifact, user.id, org.id)
        size = artifact.size_bytes or 0
        total_size += size
        if total_size > max_batch:
            raise ArtifactBatchSizeExceededError()

        p = await service.resolve_and_validate(artifact, task)

        if p.is_file():
            rel = artifact.relative_path or artifact.file_name
            PathGuard.validate_zip_entry_name(rel)
            paths.append((rel, p))

            await audit.log_artifact_action(
                action="artifact.downloaded",
                artifact_id=aid,
                org_id=org.id,
                actor_id=user.id if user else "",
                actor_name=user.name if user else None,
                details={"download_mode": "batch", "task_id": task_id, "zip_name": "artifacts.zip"},
            )

    if not paths:
        raise ArtifactBatchEmptyError()

    if user:
        await audit.log_artifact_action(
            action="artifact.batch_downloaded",
            artifact_id=task_id,
            org_id=org.id,
            actor_id=user.id,
            actor_name=user.name if user else None,
            details={"task_id": task_id, "artifact_count": len(paths)},
        )

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
