"""Build Profile service — system presets and KB profile resolution."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import not_deleted
from app.models.build_profile import BuildProfile
from app.services.index_registry import SYSTEM_BUILD_PROFILES


async def ensure_system_profiles(db: AsyncSession) -> list[BuildProfile]:
    result: list[BuildProfile] = []
    for key, spec in SYSTEM_BUILD_PROFILES.items():
        existing = await db.scalar(
            select(BuildProfile).where(
                BuildProfile.system_key == key,
                not_deleted(BuildProfile),
            )
        )
        if existing is not None:
            result.append(existing)
            continue
        profile = BuildProfile(
            org_id=None,
            name=spec["name"],
            description=spec.get("description"),
            system_key=key,
            is_system=True,
            index_types=list(spec["index_types"]),
            trigger_policy=dict(spec.get("trigger_policy") or {}),
            runtime_hints={},
            version=1,
        )
        db.add(profile)
        await db.flush()
        result.append(profile)
    return result


async def get_profile(db: AsyncSession, profile_id: str) -> BuildProfile | None:
    profile = await db.get(BuildProfile, profile_id)
    if profile is None or profile.deleted_at is not None:
        return None
    return profile


async def get_system_profile(db: AsyncSession, system_key: str) -> BuildProfile | None:
    await ensure_system_profiles(db)
    return await db.scalar(
        select(BuildProfile).where(
            BuildProfile.system_key == system_key,
            not_deleted(BuildProfile),
        )
    )


async def resolve_profile_for_kb(db: AsyncSession, kb) -> BuildProfile:
    await ensure_system_profiles(db)
    if getattr(kb, "active_build_profile_id", None):
        profile = await get_profile(db, kb.active_build_profile_id)
        if profile is not None:
            return profile
    standard = await get_system_profile(db, "standard")
    assert standard is not None
    return standard


async def list_profiles(db: AsyncSession, *, org_id: str | None = None) -> list[BuildProfile]:
    await ensure_system_profiles(db)
    stmt = select(BuildProfile).where(not_deleted(BuildProfile))
    if org_id is not None:
        stmt = stmt.where((BuildProfile.org_id.is_(None)) | (BuildProfile.org_id == org_id))
    stmt = stmt.order_by(BuildProfile.is_system.desc(), BuildProfile.name.asc())
    rows = await db.scalars(stmt)
    return list(rows.all())
