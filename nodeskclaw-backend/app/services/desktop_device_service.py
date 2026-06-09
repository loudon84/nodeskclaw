"""Desktop device and Hermes profile registration."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.desktop_device import DesktopDevice, DeviceStatus
from app.models.desktop_hermes_profile import DesktopHermesProfile, ProfileStatus
from app.models.hermes_skill_install_job import HermesSkillInstallJob, InstallJobStatus
from app.schemas.genehub import (
    DesktopDeviceInfo,
    DesktopDeviceRegister,
    DesktopHeartbeat,
    DesktopHeartbeatResponse,
    DesktopHermesProfileInfo,
    DesktopHermesProfileRegister,
)


async def register_device(
    db: AsyncSession,
    *,
    org_id: str,
    user_id: str,
    data: DesktopDeviceRegister,
) -> DesktopDeviceInfo:
    result = await db.execute(
        select(DesktopDevice).where(
            DesktopDevice.user_id == user_id,
            DesktopDevice.device_fingerprint == data.device_fingerprint,
            DesktopDevice.deleted_at.is_(None),
        )
    )
    device = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)

    if device:
        device.device_name = data.device_name
        device.os_type = data.os_type
        device.os_version = data.os_version
        device.app_version = data.app_version
        device.status = DeviceStatus.active
        device.last_seen_at = now
    else:
        device = DesktopDevice(
            id=str(uuid.uuid4()),
            org_id=org_id,
            user_id=user_id,
            device_name=data.device_name,
            device_fingerprint=data.device_fingerprint,
            os_type=data.os_type,
            os_version=data.os_version,
            app_version=data.app_version,
            status=DeviceStatus.active,
            last_seen_at=now,
        )
        db.add(device)

    await db.flush()
    return DesktopDeviceInfo(
        desktop_device_id=device.id,
        device_id=device.id,
        status=device.status,
    )


async def _bind_pending_jobs_to_profile(
    db: AsyncSession,
    *,
    org_id: str,
    user_id: str,
    profile_id: str,
    profile_name: str,
    desktop_device_id: str,
) -> None:
    result = await db.execute(
        select(HermesSkillInstallJob).where(
            HermesSkillInstallJob.org_id == org_id,
            HermesSkillInstallJob.user_id == user_id,
            HermesSkillInstallJob.profile_id.is_(None),
            HermesSkillInstallJob.status == InstallJobStatus.pending,
            HermesSkillInstallJob.deleted_at.is_(None),
        )
    )
    for job in result.scalars().all():
        job.profile_id = profile_id
        job.desktop_device_id = desktop_device_id
    await db.flush()


async def register_profile(
    db: AsyncSession,
    *,
    org_id: str,
    user_id: str,
    data: DesktopHermesProfileRegister,
) -> DesktopHermesProfileInfo:
    device_result = await db.execute(
        select(DesktopDevice).where(
            DesktopDevice.id == data.desktop_device_id,
            DesktopDevice.user_id == user_id,
            DesktopDevice.org_id == org_id,
            DesktopDevice.deleted_at.is_(None),
        )
    )
    device = device_result.scalar_one_or_none()
    if not device:
        raise ForbiddenError(
            "设备不属于当前用户",
            message_key="errors.desktop.device_not_found",
        )

    result = await db.execute(
        select(DesktopHermesProfile).where(
            DesktopHermesProfile.desktop_device_id == data.desktop_device_id,
            DesktopHermesProfile.profile_name == data.profile_name,
            DesktopHermesProfile.deleted_at.is_(None),
        )
    )
    profile = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)

    if profile:
        if profile.user_id != user_id:
            raise ForbiddenError(
                "Profile 不属于当前用户",
                message_key="errors.desktop.profile_forbidden",
            )
        profile.hermes_home = data.hermes_home
        profile.runtime_version = data.runtime_version
        profile.gateway_url = data.gateway_url
        profile.gateway_port = data.gateway_port
        profile.capabilities = data.capabilities
        profile.status = ProfileStatus.active
        profile.last_seen_at = now
    else:
        profile = DesktopHermesProfile(
            id=str(uuid.uuid4()),
            org_id=org_id,
            user_id=user_id,
            desktop_device_id=data.desktop_device_id,
            profile_name=data.profile_name,
            hermes_home=data.hermes_home,
            runtime_version=data.runtime_version,
            gateway_url=data.gateway_url,
            gateway_port=data.gateway_port,
            capabilities=data.capabilities,
            status=ProfileStatus.active,
            last_seen_at=now,
        )
        db.add(profile)

    await db.flush()
    await _bind_pending_jobs_to_profile(
        db,
        org_id=org_id,
        user_id=user_id,
        profile_id=profile.id,
        profile_name=profile.profile_name,
        desktop_device_id=device.id,
    )
    return DesktopHermesProfileInfo(profile_id=profile.id, status=profile.status)


async def heartbeat(
    db: AsyncSession,
    *,
    user_id: str,
    data: DesktopHeartbeat,
) -> DesktopHeartbeatResponse:
    device_result = await db.execute(
        select(DesktopDevice).where(
            DesktopDevice.id == data.desktop_device_id,
            DesktopDevice.user_id == user_id,
            DesktopDevice.deleted_at.is_(None),
        )
    )
    device = device_result.scalar_one_or_none()
    if not device:
        raise NotFoundError(
            "设备不存在",
            message_key="errors.desktop.device_not_found",
        )

    now = datetime.now(timezone.utc)
    device.last_seen_at = now

    for profile_item in data.profiles:
        profile_result = await db.execute(
            select(DesktopHermesProfile).where(
                DesktopHermesProfile.id == profile_item.profile_id,
                DesktopHermesProfile.desktop_device_id == device.id,
                DesktopHermesProfile.user_id == user_id,
                DesktopHermesProfile.deleted_at.is_(None),
            )
        )
        profile = profile_result.scalar_one_or_none()
        if profile:
            profile.status = profile_item.status
            profile.last_seen_at = now

    await db.flush()
    return DesktopHeartbeatResponse(
        sync_interval_seconds=60,
        pending_jobs_interval_seconds=60,
        genehub_enabled=settings.GENEHUB_DESKTOP_SYNC_ENABLED,
    )
