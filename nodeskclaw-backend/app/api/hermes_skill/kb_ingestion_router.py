from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_org_admin, require_org_member
from app.services.hermes_skill.permission_checker import PermissionChecker
from app.services.mcp_skill_gateway.kb_ingestion_service import KbIngestionService

router = APIRouter()


def _ok(data: Any = None, message: str = "success") -> dict:
    return {"code": 0, "message": message, "data": data}


class KbIngestionRejectBody(BaseModel):
    comment: str | None = None


class KbManualIngestBody(BaseModel):
    knowledge_base: str = "general"
    tags: list[str] = Field(default_factory=list)


@router.get("/artifacts/kb-ingestion-jobs")
async def list_kb_ingestion_jobs(
    status: str | None = Query(None),
    knowledge_base: str | None = Query(None),
    task_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_artifact:view")
    service = KbIngestionService(db)
    jobs, total = await service.list_jobs(
        org.id,
        status=status,
        knowledge_base=knowledge_base,
        task_id=task_id,
        limit=limit,
        offset=offset,
    )
    items = [
        {
            "id": job.id,
            "artifact_id": job.artifact_id,
            "task_id": job.task_id,
            "knowledge_base": job.knowledge_base,
            "status": job.status,
            "tags": job.tags or [],
            "metadata_json": job.metadata_json,
            "reviewed_by": job.reviewed_by,
            "reviewed_at": job.reviewed_at.isoformat() if job.reviewed_at else None,
            "review_comment": job.review_comment,
            "indexed_at": job.indexed_at.isoformat() if job.indexed_at else None,
            "index_error": job.index_error,
            "created_at": job.created_at.isoformat() if job.created_at else None,
        }
        for job in jobs
    ]
    return _ok({"items": items, "total": total, "limit": limit, "offset": offset})


@router.post("/artifacts/kb-ingestion-jobs/{job_id}/approve")
async def approve_kb_ingestion_job(
    job_id: str,
    user_org=Depends(require_org_admin),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    service = KbIngestionService(db)
    job = await service.approve(job_id, org.id, user.id)
    await db.commit()
    return _ok({"id": job.id, "status": job.status})


@router.post("/artifacts/kb-ingestion-jobs/{job_id}/reject")
async def reject_kb_ingestion_job(
    job_id: str,
    body: KbIngestionRejectBody | None = None,
    user_org=Depends(require_org_admin),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    service = KbIngestionService(db)
    job = await service.reject(job_id, org.id, user.id, body.comment if body else None)
    await db.commit()
    return _ok({"id": job.id, "status": job.status})


@router.post("/artifacts/{artifact_id}/kb-ingest")
async def manual_kb_ingest(
    artifact_id: str,
    body: KbManualIngestBody | None = None,
    user_org=Depends(require_org_admin),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    payload = body or KbManualIngestBody()
    service = KbIngestionService(db)
    job = await service.manual_ingest(
        artifact_id,
        org.id,
        user.id,
        knowledge_base=payload.knowledge_base,
        tags=payload.tags,
    )
    await db.commit()
    return _ok({"id": job.id, "status": job.status})
