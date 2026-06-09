"""Desktop GeneHub API routes."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_current_org, get_db
from app.schemas.common import ApiResponse
from app.schemas.genehub import (
    DesktopBundleInfo,
    DesktopDeviceInfo,
    DesktopDeviceRegister,
    DesktopHeartbeat,
    DesktopHeartbeatResponse,
    DesktopHermesProfileInfo,
    DesktopHermesProfileRegister,
    DesktopInstallJobInfo,
    DesktopInstallJobStatusUpdate,
    DesktopInstalledSkillSync,
    DesktopPendingJobInfo,
    DesktopSelfServiceInstallJobCreate,
    DesktopSkillInfo,
)
from app.services import desktop_device_service, genehub_service, hermes_desktop_sync_service

router = APIRouter(prefix="/desktop")


@router.get("/genehub/health", response_model=ApiResponse[dict])
async def genehub_health(
    user_org=Depends(get_current_org),
):
    user, org = user_org
    return ApiResponse(data={
        "status": "ok" if settings.GENEHUB_DESKTOP_SYNC_ENABLED else "disabled",
        "genehub_enabled": settings.GENEHUB_DESKTOP_SYNC_ENABLED,
        "org_id": org.id,
        "user_id": user.id,
    })


@router.post("/devices/register", response_model=ApiResponse[DesktopDeviceInfo])
async def register_device(
    body: DesktopDeviceRegister,
    user_org=Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    data = await desktop_device_service.register_device(
        db, org_id=org.id, user_id=user.id, data=body
    )
    await db.commit()
    return ApiResponse(data=data)


@router.post("/hermes/profiles/register", response_model=ApiResponse[DesktopHermesProfileInfo])
async def register_profile(
    body: DesktopHermesProfileRegister,
    user_org=Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    data = await desktop_device_service.register_profile(
        db, org_id=org.id, user_id=user.id, data=body
    )
    await db.commit()
    return ApiResponse(data=data)


@router.post("/heartbeat", response_model=ApiResponse[DesktopHeartbeatResponse])
async def heartbeat(
    body: DesktopHeartbeat,
    user_org=Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    user, _ = user_org
    data = await desktop_device_service.heartbeat(
        db, user_id=user.id, data=body
    )
    await db.commit()
    return ApiResponse(data=data)


@router.get("/genehub/skills", response_model=ApiResponse[list[DesktopSkillInfo]])
async def list_skills(
    profile_id: str = Query(...),
    keyword: str | None = Query(None),
    category: str | None = Query(None),
    tag: str | None = Query(None),
    user_org=Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    data = await genehub_service.list_desktop_visible_skills(
        db,
        org_id=org.id,
        user_id=user.id,
        profile_id=profile_id,
        keyword=keyword,
        category=category,
        tag=tag,
    )
    return ApiResponse(data=data)


@router.post("/hermes/install-jobs", response_model=ApiResponse[DesktopInstallJobInfo])
async def create_install_job(
    body: DesktopSelfServiceInstallJobCreate,
    user_org=Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    job = await genehub_service.create_self_service_job(
        db,
        org_id=org.id,
        user_id=user.id,
        profile_id=body.profile_id,
        gene_slug=body.gene_slug,
        version=body.version,
        job_type=body.job_type,
    )
    await db.commit()
    return ApiResponse(data=DesktopInstallJobInfo(job_id=job.id, status=job.status))


@router.get("/hermes/install-jobs/pending", response_model=ApiResponse[list[DesktopPendingJobInfo]])
async def list_pending_jobs(
    profile_id: str = Query(...),
    user_org=Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    data = await hermes_desktop_sync_service.get_pending_jobs(
        db, org_id=org.id, user_id=user.id, profile_id=profile_id
    )
    await db.commit()
    return ApiResponse(data=data)


@router.post("/hermes/install-jobs/{job_id}/claim", response_model=ApiResponse[DesktopInstallJobInfo])
async def claim_install_job(
    job_id: str,
    user_org=Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    user, _ = user_org
    data = await hermes_desktop_sync_service.claim_job(
        db, user_id=user.id, job_id=job_id
    )
    await db.commit()
    return ApiResponse(data=data)


@router.get("/hermes/install-jobs/{job_id}/bundle", response_model=ApiResponse[DesktopBundleInfo])
async def download_install_bundle(
    job_id: str,
    user_org=Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    user, _ = user_org
    bundle = await hermes_desktop_sync_service.get_job_bundle(
        db, user_id=user.id, job_id=job_id
    )
    await db.commit()
    return ApiResponse(data=DesktopBundleInfo(**bundle))


@router.post("/hermes/install-jobs/{job_id}/status", response_model=ApiResponse[DesktopInstallJobInfo])
async def update_install_job_status(
    job_id: str,
    body: DesktopInstallJobStatusUpdate,
    user_org=Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    user, _ = user_org
    data = await hermes_desktop_sync_service.update_job_status(
        db, user_id=user.id, job_id=job_id, data=body
    )
    await db.commit()
    return ApiResponse(data=data)


@router.post("/hermes/installed-skills/sync", response_model=ApiResponse[dict])
async def sync_installed_skills(
    body: DesktopInstalledSkillSync,
    user_org=Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    data = await hermes_desktop_sync_service.sync_installed_skills(
        db, org_id=org.id, user_id=user.id, data=body
    )
    await db.commit()
    return ApiResponse(data=data)
