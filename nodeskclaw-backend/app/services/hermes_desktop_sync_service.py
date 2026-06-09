"""Hermes desktop install job sync and status management."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.models.desktop_hermes_profile import DesktopHermesProfile
from app.models.hermes_installed_skill import HermesInstalledSkill, InstalledSkillStatus
from app.models.hermes_skill_install_job import (
    ACTIVE_JOB_STATUSES,
    HermesSkillInstallJob,
    InstallJobStatus,
    InstallJobType,
)
from app.schemas.genehub import (
    DesktopInstallJobInfo,
    DesktopInstallJobStatusUpdate,
    DesktopInstalledSkillSync,
    DesktopPendingJobInfo,
)
from app.services.genehub_bundle_service import build_hermes_desktop_bundle
from app.services.hermes_skill.skill_audit_logger import SkillAuditLogger


CLAIMABLE_STATUSES = frozenset({
    InstallJobStatus.claimed,
    InstallJobStatus.downloading,
    InstallJobStatus.validating,
    InstallJobStatus.installing,
})

CLIENT_REPORTABLE_STATUSES = frozenset({
    InstallJobStatus.downloading,
    InstallJobStatus.validating,
    InstallJobStatus.installing,
    InstallJobStatus.installed,
    InstallJobStatus.failed,
})


async def _get_user_job(db: AsyncSession, *, user_id: str, job_id: str) -> HermesSkillInstallJob:
    result = await db.execute(
        select(HermesSkillInstallJob).where(
            HermesSkillInstallJob.id == job_id,
            HermesSkillInstallJob.user_id == user_id,
            HermesSkillInstallJob.deleted_at.is_(None),
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise NotFoundError(
            "安装任务不存在",
            message_key="errors.genehub.install_job_not_found",
        )
    return job


async def get_pending_jobs(
    db: AsyncSession,
    *,
    org_id: str,
    user_id: str,
    profile_id: str,
) -> list[DesktopPendingJobInfo]:
    profile_result = await db.execute(
        select(DesktopHermesProfile).where(
            DesktopHermesProfile.id == profile_id,
            DesktopHermesProfile.user_id == user_id,
            DesktopHermesProfile.org_id == org_id,
            DesktopHermesProfile.deleted_at.is_(None),
        )
    )
    profile = profile_result.scalar_one_or_none()
    if not profile:
        raise NotFoundError(
            "Profile 不存在",
            message_key="errors.desktop.profile_not_found",
        )

    result = await db.execute(
        select(HermesSkillInstallJob).where(
            HermesSkillInstallJob.org_id == org_id,
            HermesSkillInstallJob.user_id == user_id,
            HermesSkillInstallJob.status == InstallJobStatus.pending,
            HermesSkillInstallJob.deleted_at.is_(None),
            or_(
                HermesSkillInstallJob.profile_id == profile_id,
                HermesSkillInstallJob.profile_id.is_(None),
            ),
        )
    )
    jobs = result.scalars().all()
    for job in jobs:
        if not job.profile_id:
            job.profile_id = profile.id
            job.desktop_device_id = profile.desktop_device_id
    await db.flush()

    return [
        DesktopPendingJobInfo(
            job_id=job.id,
            profile_id=job.profile_id,
            job_type=job.job_type,
            action=job.job_type,
            gene_slug=job.gene_slug,
            gene_version=job.gene_version,
            skill_name=job.skill_name,
            status=job.status,
        )
        for job in jobs
    ]


async def claim_job(
    db: AsyncSession,
    *,
    user_id: str,
    job_id: str,
) -> DesktopInstallJobInfo:
    job = await _get_user_job(db, user_id=user_id, job_id=job_id)

    if job.status == InstallJobStatus.claimed:
        return DesktopInstallJobInfo(job_id=job.id, status=job.status)

    if job.status != InstallJobStatus.pending:
        raise BadRequestError(
            "安装任务状态无效",
            message_key="errors.genehub.install_job_invalid_status",
        )

    job.status = InstallJobStatus.claimed
    job.claimed_at = datetime.now(timezone.utc)
    await db.flush()

    audit = SkillAuditLogger(db)
    await audit.log(
        action="genehub.install_job.claim",
        target_id=job.id,
        org_id=job.org_id,
        actor_id=user_id,
        details={"gene_slug": job.gene_slug},
    )
    return DesktopInstallJobInfo(job_id=job.id, status=job.status)


async def get_job_bundle(
    db: AsyncSession,
    *,
    user_id: str,
    job_id: str,
) -> dict:
    job = await _get_user_job(db, user_id=user_id, job_id=job_id)
    if job.status not in CLAIMABLE_STATUSES:
        raise BadRequestError(
            "安装任务状态无效",
            message_key="errors.genehub.install_job_invalid_status",
        )

    if job.status == InstallJobStatus.claimed:
        job.status = InstallJobStatus.downloading

    bundle = await build_hermes_desktop_bundle(db, gene_id=job.gene_id, version=job.gene_version)
    job.manifest_hash = bundle.get("hashes", {}).get("manifest_sha256")
    job.bundle_hash = bundle.get("hashes", {}).get("bundle_sha256")
    await db.flush()
    return bundle


async def update_job_status(
    db: AsyncSession,
    *,
    user_id: str,
    job_id: str,
    data: DesktopInstallJobStatusUpdate,
) -> DesktopInstallJobInfo:
    job = await _get_user_job(db, user_id=user_id, job_id=job_id)

    if data.status not in CLIENT_REPORTABLE_STATUSES:
        raise BadRequestError(
            "安装任务状态无效",
            message_key="errors.genehub.install_job_invalid_status",
        )

    job.status = data.status
    job.client_report = data.client_report
    now = datetime.now(timezone.utc)

    if data.status == InstallJobStatus.failed:
        job.error_code = data.error_code
        job.error_message = data.error_message or data.message
        job.finished_at = now
    elif data.status == InstallJobStatus.installed:
        job.finished_at = now
        await _upsert_installed_skill(db, job=job, data=data)
        if job.job_type == InstallJobType.uninstall:
            await _mark_skill_uninstalled(db, job=job)
    else:
        if data.message:
            job.error_message = data.message

    await db.flush()

    audit = SkillAuditLogger(db)
    await audit.log(
        action=f"genehub.install_job.status.{data.status}",
        target_id=job.id,
        org_id=job.org_id,
        actor_id=user_id,
        details={
            "gene_slug": job.gene_slug,
            "error_code": data.error_code,
            "client_report": data.client_report,
        },
    )
    return DesktopInstallJobInfo(job_id=job.id, status=job.status)


async def _upsert_installed_skill(
    db: AsyncSession,
    *,
    job: HermesSkillInstallJob,
    data: DesktopInstallJobStatusUpdate,
) -> None:
    if job.job_type == InstallJobType.uninstall:
        return
    if not job.profile_id or not job.desktop_device_id:
        return

    result = await db.execute(
        select(HermesInstalledSkill).where(
            HermesInstalledSkill.profile_id == job.profile_id,
            HermesInstalledSkill.gene_slug == job.gene_slug,
            HermesInstalledSkill.deleted_at.is_(None),
        )
    )
    installed = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    version = data.gene_version or job.gene_version

    if installed:
        installed.gene_id = job.gene_id
        installed.gene_version = version
        installed.skill_name = job.skill_name
        installed.install_path = data.install_path
        installed.status = InstalledSkillStatus.installed
        installed.last_sync_at = now
        installed.installed_at = now
    else:
        installed = HermesInstalledSkill(
            id=str(uuid.uuid4()),
            org_id=job.org_id,
            user_id=job.user_id,
            desktop_device_id=job.desktop_device_id,
            profile_id=job.profile_id,
            gene_id=job.gene_id,
            gene_slug=job.gene_slug,
            gene_version=version,
            skill_name=job.skill_name,
            install_path=data.install_path,
            status=InstalledSkillStatus.installed,
            last_sync_at=now,
            installed_at=now,
        )
        db.add(installed)


async def _mark_skill_uninstalled(
    db: AsyncSession,
    *,
    job: HermesSkillInstallJob,
) -> None:
    if not job.profile_id:
        return
    result = await db.execute(
        select(HermesInstalledSkill).where(
            HermesInstalledSkill.profile_id == job.profile_id,
            HermesInstalledSkill.gene_slug == job.gene_slug,
            HermesInstalledSkill.deleted_at.is_(None),
        )
    )
    installed = result.scalar_one_or_none()
    if installed:
        installed.status = InstalledSkillStatus.uninstalled
        installed.last_sync_at = datetime.now(timezone.utc)


async def sync_installed_skills(
    db: AsyncSession,
    *,
    org_id: str,
    user_id: str,
    data: DesktopInstalledSkillSync,
) -> dict:
    profile_result = await db.execute(
        select(DesktopHermesProfile).where(
            DesktopHermesProfile.id == data.profile_id,
            DesktopHermesProfile.user_id == user_id,
            DesktopHermesProfile.org_id == org_id,
            DesktopHermesProfile.deleted_at.is_(None),
        )
    )
    profile = profile_result.scalar_one_or_none()
    if not profile:
        raise NotFoundError(
            "Profile 不存在",
            message_key="errors.desktop.profile_not_found",
        )

    now = datetime.now(timezone.utc)
    synced = 0
    unmanaged = 0

    for item in data.skills:
        result = await db.execute(
            select(HermesInstalledSkill).where(
                HermesInstalledSkill.profile_id == profile.id,
                HermesInstalledSkill.gene_slug == item.gene_slug,
                HermesInstalledSkill.deleted_at.is_(None),
            )
        )
        installed = result.scalar_one_or_none()
        if installed:
            installed.skill_name = item.skill_name
            installed.gene_version = item.gene_version
            installed.install_path = item.install_path
            installed.status = item.status
            installed.last_sync_at = now
        else:
            db.add(
                HermesInstalledSkill(
                    id=str(uuid.uuid4()),
                    org_id=org_id,
                    user_id=user_id,
                    desktop_device_id=profile.desktop_device_id,
                    profile_id=profile.id,
                    gene_slug=item.gene_slug,
                    gene_version=item.gene_version,
                    skill_name=item.skill_name,
                    install_path=item.install_path,
                    status=item.status,
                    last_sync_at=now,
                    installed_at=now if item.status == InstalledSkillStatus.installed else None,
                )
            )
        synced += 1

    return {"synced": synced, "unmanaged": unmanaged}
