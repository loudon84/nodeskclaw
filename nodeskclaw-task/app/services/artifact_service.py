"""Artifact storage and metadata."""

import hashlib
import hmac
import time
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.models.artifact import Artifact
from app.models.automation_task import AutomationTask
from app.models.base import not_deleted
from app.models.user_cache import UserCache
from app.schemas.resource import ArtifactUploadUrlRequest


def _artifact_root() -> Path:
    root = Path(settings.ARTIFACT_LOCAL_DIR)
    root.mkdir(parents=True, exist_ok=True)
    return root


def build_storage_key(tenant_id: str, task_id: str, run_id: str | None, name: str) -> str:
    safe_name = name.replace("\\", "_").replace("/", "_")
    parts = [tenant_id, task_id]
    if run_id:
        parts.append(run_id)
    parts.append(safe_name)
    return "/".join(parts)


def _sign_download(storage_key: str, expires: int) -> str:
    payload = f"{storage_key}:{expires}"
    return hmac.new(settings.JWT_SECRET.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


async def list_artifacts(
    db: AsyncSession,
    tenant_id: str,
    task_id: str | None = None,
    run_id: str | None = None,
) -> list[Artifact]:
    query = select(Artifact).where(Artifact.tenant_id == tenant_id, not_deleted(Artifact))
    if task_id:
        query = query.where(Artifact.task_id == task_id)
    if run_id:
        query = query.where(Artifact.run_id == run_id)
    result = await db.execute(query.order_by(Artifact.created_at.desc()))
    return list(result.scalars().all())


async def get_artifact(db: AsyncSession, tenant_id: str, artifact_id: str) -> Artifact:
    artifact = (
        await db.execute(
            select(Artifact).where(
                Artifact.id == artifact_id,
                Artifact.tenant_id == tenant_id,
                not_deleted(Artifact),
            )
        )
    ).scalar_one_or_none()
    if artifact is None:
        raise NotFoundError(message="Artifact 不存在", message_key="errors.autotask.artifact_not_found")
    return artifact


async def create_upload_url(
    db: AsyncSession,
    tenant_id: str,
    user: UserCache,
    body: ArtifactUploadUrlRequest,
) -> tuple[str, str]:
    task = (
        await db.execute(
            select(AutomationTask).where(
                AutomationTask.id == body.task_id,
                AutomationTask.tenant_id == tenant_id,
                not_deleted(AutomationTask),
            )
        )
    ).scalar_one_or_none()
    if task is None:
        raise NotFoundError(message="任务不存在", message_key="errors.autotask.task_not_found")

    storage_key = build_storage_key(tenant_id, body.task_id, body.run_id, body.name)
    target = _artifact_root() / storage_key
    target.parent.mkdir(parents=True, exist_ok=True)
    upload_url = f"/api/v1/autotask/artifacts/upload/{storage_key}"
    return upload_url, storage_key


def get_download_url(storage_key: str) -> str:
    expires = int(time.time()) + 3600
    sig = _sign_download(storage_key, expires)
    return f"/api/v1/autotask/artifacts/download/{storage_key}?expires={expires}&sig={sig}"


def verify_download_signature(storage_key: str, expires: int, sig: str) -> bool:
    if expires < int(time.time()):
        return False
    expected = _sign_download(storage_key, expires)
    return hmac.compare_digest(expected, sig)


async def create_artifact_record(
    db: AsyncSession,
    tenant_id: str,
    task_id: str,
    run_id: str | None,
    artifact_type: str,
    name: str,
    storage_key: str,
    size: int,
    mime_type: str | None,
    created_by: str | None,
) -> Artifact:
    artifact = Artifact(
        tenant_id=tenant_id,
        task_id=task_id,
        run_id=run_id,
        type=artifact_type,
        name=name,
        storage_key=storage_key,
        size=size,
        mime_type=mime_type,
        created_by=created_by,
    )
    db.add(artifact)
    await db.flush()
    return artifact
