"""Resolve Desktop Hermes profile references for GeneHub MCP tools."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.base import not_deleted
from app.models.desktop_hermes_profile import DesktopHermesProfile, ProfileStatus
from app.models.user import User


async def resolve_desktop_profile(
    ref: str | None,
    org_id: str,
    user: User,
    db: AsyncSession,
) -> DesktopHermesProfile:
    value = (ref or "").strip()
    if not value:
        result = await db.execute(
            select(DesktopHermesProfile)
            .where(
                DesktopHermesProfile.org_id == org_id,
                DesktopHermesProfile.user_id == user.id,
                DesktopHermesProfile.status == ProfileStatus.active.value,
                not_deleted(DesktopHermesProfile),
            )
            .order_by(DesktopHermesProfile.last_seen_at.desc().nullslast())
        )
        profile = result.scalars().first()
        if not profile:
            raise NotFoundError(
                "未找到可用的 Desktop Hermes profile",
                message_key="errors.desktop.profile_not_found",
            )
        return profile

    by_id = await db.execute(
        select(DesktopHermesProfile).where(
            DesktopHermesProfile.id == value,
            not_deleted(DesktopHermesProfile),
        )
    )
    profile = by_id.scalar_one_or_none()
    if not profile:
        by_name = await db.execute(
            select(DesktopHermesProfile).where(
                DesktopHermesProfile.profile_name == value,
                DesktopHermesProfile.org_id == org_id,
                DesktopHermesProfile.user_id == user.id,
                not_deleted(DesktopHermesProfile),
            )
        )
        profile = by_name.scalar_one_or_none()

    if not profile:
        raise NotFoundError(
            f"Desktop Hermes profile 不存在: {value}",
            message_key="errors.desktop.profile_not_found",
        )

    if profile.org_id != org_id or profile.user_id != user.id:
        raise ForbiddenError(
            "无权限访问该 Desktop Hermes profile",
            message_key="errors.desktop.profile_forbidden",
        )

    return profile
