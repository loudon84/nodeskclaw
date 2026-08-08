"""Ingestion job API routes."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_member_context, get_ragflow_client
from app.integrations.ragflow.client import RagflowClient
from app.schemas.common import ApiResponse, PageData
from app.schemas.knowledge import IngestionJobOut
from app.schemas.principal import KnowledgePrincipal
from app.services import ingestion_service

router = APIRouter(prefix="/ingestion-jobs", tags=["ingestion-jobs"])


@router.get("", response_model=ApiResponse[PageData[IngestionJobOut]])
async def list_ingestion_jobs(
    status: str | None = None,
    knowledge_base_id: str | None = None,
    source_file_id: str | None = None,
    created_by: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    items, total = await ingestion_service.list_jobs(
        db,
        member,
        status=status,
        knowledge_base_id=knowledge_base_id,
        source_file_id=source_file_id,
        created_by=created_by,
        page=page,
        page_size=page_size,
    )
    return ApiResponse(
        data=PageData(
            items=[IngestionJobOut.model_validate(i) for i in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.get("/{job_id}", response_model=ApiResponse[IngestionJobOut])
async def get_ingestion_job(
    job_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    job = await ingestion_service.get_job(db, member, job_id)
    return ApiResponse(data=IngestionJobOut.model_validate(job))


@router.post("/{job_id}/retry", response_model=ApiResponse[IngestionJobOut])
async def retry_ingestion_job(
    job_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
    ragflow: RagflowClient = Depends(get_ragflow_client),
):
    job = await ingestion_service.retry_job(db, member, ragflow, job_id)
    return ApiResponse(data=IngestionJobOut.model_validate(job))


@router.post("/{job_id}/cancel", response_model=ApiResponse[IngestionJobOut])
async def cancel_ingestion_job(
    job_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
    ragflow: RagflowClient = Depends(get_ragflow_client),
):
    job = await ingestion_service.cancel_job(db, member, ragflow, job_id)
    return ApiResponse(data=IngestionJobOut.model_validate(job))
