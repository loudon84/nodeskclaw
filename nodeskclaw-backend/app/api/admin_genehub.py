"""Admin GeneHub API routes."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_org, get_db
from app.schemas.common import ApiResponse
from app.schemas.genehub import (
    AdminGeneHubSkillCreate,
    AdminGeneHubSkillInfo,
    AdminGeneHubSkillReview,
    AdminGeneHubSkillUpdate,
    AdminInstallJobAssign,
    AdminInstallJobAssignResult,
    AdminInstallJobInfo,
    GeneHubEntitlementGrant,
)
from app.services import genehub_service

router = APIRouter(prefix="/genehub")


@router.post("/skills", response_model=ApiResponse[AdminGeneHubSkillInfo])
async def create_skill(
    body: AdminGeneHubSkillCreate,
    user_org=Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    data = await genehub_service.create_skill(
        db, org_id=org.id, user_id=user.id, data=body
    )
    await db.commit()
    return ApiResponse(data=data)


@router.put("/skills/{gene_id}", response_model=ApiResponse[AdminGeneHubSkillInfo])
async def update_skill(
    gene_id: str,
    body: AdminGeneHubSkillUpdate,
    user_org=Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    data = await genehub_service.update_skill(
        db, gene_id=gene_id, org_id=org.id, user_id=user.id, data=body
    )
    await db.commit()
    return ApiResponse(data=data)


@router.put("/skills/{gene_id}/review", response_model=ApiResponse[AdminGeneHubSkillInfo])
async def review_skill(
    gene_id: str,
    body: AdminGeneHubSkillReview,
    user_org=Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    data = await genehub_service.review_skill(
        db,
        gene_id=gene_id,
        org_id=org.id,
        user_id=user.id,
        action=body.action,
        reason=body.reason,
    )
    await db.commit()
    return ApiResponse(data=data)


@router.post("/skills/{gene_id}/publish", response_model=ApiResponse[AdminGeneHubSkillInfo])
async def publish_skill(
    gene_id: str,
    user_org=Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    data = await genehub_service.publish_skill(
        db, gene_id=gene_id, org_id=org.id, user_id=user.id
    )
    await db.commit()
    return ApiResponse(data=data)


@router.post("/entitlements", response_model=ApiResponse[dict])
async def grant_entitlements(
    body: GeneHubEntitlementGrant,
    user_org=Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    created = await genehub_service.grant_entitlements(
        db,
        org_id=org.id,
        gene_id=body.gene_id,
        targets=body.targets,
        created_by=user.id,
    )
    await db.commit()
    return ApiResponse(data={"created": created})


@router.post("/install-jobs/assign", response_model=ApiResponse[AdminInstallJobAssignResult])
async def assign_install_jobs(
    body: AdminInstallJobAssign,
    user_org=Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    data = await genehub_service.create_assign_jobs(
        db,
        org_id=org.id,
        gene_slug=body.gene_slug,
        version=body.version,
        target_type=body.target_type,
        target_ids=body.target_ids,
        profile_name=body.profile_name,
        job_type=body.job_type,
        requested_by=user.id,
    )
    await db.commit()
    return ApiResponse(data=data)


@router.get("/install-jobs", response_model=ApiResponse[list[AdminInstallJobInfo]])
async def list_install_jobs(
    status: str | None = Query(None),
    user_id: str | None = Query(None),
    user_org=Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    _, org = user_org
    data = await genehub_service.list_admin_install_jobs(
        db, org_id=org.id, status=status, user_id=user_id
    )
    return ApiResponse(data=data)
