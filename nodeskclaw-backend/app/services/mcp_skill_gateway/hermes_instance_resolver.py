"""Resolve Hermes external Docker instance references for MCP Gateway."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.models.base import not_deleted
from app.models.desktop_hermes_profile import DesktopHermesProfile, ProfileStatus
from app.models.instance import Instance
from app.models.instance_member import InstanceRole
from app.models.user import User
from app.services.hermes_external._common import load_advanced_config
from app.services.hermes_external.binding_type import get_instance_binding_type
from app.services import instance_member_service


def _instance_profile(instance: Instance) -> str:
    advanced = load_advanced_config(instance)
    return str(advanced.get("profile") or instance.slug or instance.name)


def _instance_container_name(instance: Instance) -> str:
    advanced = load_advanced_config(instance)
    profile = _instance_profile(instance)
    return str(advanced.get("external_container_name") or f"hermes-{profile}")


def _instance_aliases(instance: Instance) -> set[str]:
    advanced = load_advanced_config(instance)
    aliases = advanced.get("aliases") or []
    result = {instance.slug, instance.name, _instance_profile(instance)}
    if isinstance(aliases, list):
        result.update(str(a) for a in aliases if a)
    return {a for a in result if a}


async def list_external_docker_instances(org_id: str, db: AsyncSession) -> list[Instance]:
    result = await db.execute(
        select(Instance).where(
            Instance.org_id == org_id,
            not_deleted(Instance),
        )
    )
    instances = result.scalars().all()
    return [inst for inst in instances if get_instance_binding_type(inst) == "external_docker"]


async def _filter_accessible_instances(
    instances: list[Instance],
    user: User,
    db: AsyncSession,
) -> list[Instance]:
    accessible: list[Instance] = []
    for instance in instances:
        try:
            await instance_member_service.check_instance_access(
                instance.id,
                user,
                InstanceRole.viewer,
                db,
            )
            accessible.append(instance)
        except (ForbiddenError, NotFoundError):
            continue
    return accessible


def _ensure_unique(matches: list[Instance], ref: str) -> Instance:
    if not matches:
        raise NotFoundError(
            f"Hermes 实例不存在: {ref}",
            "errors.external_docker.instance_not_found",
        )
    if len(matches) > 1:
        raise BadRequestError(
            f"instance_ref 匹配多个 Hermes 实例: {ref}",
            "errors.external_docker.instance_ambiguous",
        )
    return matches[0]


def _match_by_id(instances: list[Instance], ref: str) -> list[Instance]:
    return [inst for inst in instances if inst.id == ref]


def _match_by_container_name(instances: list[Instance], ref: str) -> list[Instance]:
    return [inst for inst in instances if _instance_container_name(inst) == ref]


def _match_by_profile(instances: list[Instance], ref: str) -> list[Instance]:
    return [inst for inst in instances if _instance_profile(inst) == ref]


def _match_by_alias(instances: list[Instance], ref: str) -> list[Instance]:
    return [inst for inst in instances if ref in _instance_aliases(inst)]


async def _resolve_default_instance(
    org_id: str,
    user: User,
    db: AsyncSession,
) -> Instance:
    instances = await list_external_docker_instances(org_id, db)
    accessible = await _filter_accessible_instances(instances, user, db)
    if not accessible:
        raise NotFoundError(
            "未找到可访问的 Hermes 实例",
            "errors.external_docker.instance_not_found",
        )
    if len(accessible) == 1:
        return accessible[0]

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
    if profile:
        profile_matches = _match_by_profile(accessible, profile.profile_name)
        if len(profile_matches) == 1:
            return profile_matches[0]
        if len(profile_matches) > 1:
            raise BadRequestError(
                "默认 Hermes 实例存在歧义",
                "errors.external_docker.instance_ambiguous",
            )

    raise BadRequestError(
        "默认 Hermes 实例存在歧义",
        "errors.external_docker.instance_ambiguous",
    )


async def resolve_instance_ref(
    ref: str | None,
    org_id: str,
    user: User,
    db: AsyncSession,
) -> Instance:
    value = (ref or "").strip()
    if not value:
        return await _resolve_default_instance(org_id, user, db)

    instances = await list_external_docker_instances(org_id, db)

    for matcher in (_match_by_id, _match_by_container_name, _match_by_profile, _match_by_alias):
        matches = matcher(instances, value)
        if matches:
            instance = _ensure_unique(matches, value)
            try:
                await instance_member_service.check_instance_access(
                    instance.id,
                    user,
                    InstanceRole.viewer,
                    db,
                )
            except ForbiddenError as exc:
                raise ForbiddenError(
                    exc.message,
                    "errors.external_docker.instance_forbidden",
                ) from exc
            except NotFoundError as exc:
                raise NotFoundError(
                    exc.message,
                    "errors.external_docker.instance_not_found",
                ) from exc
            return instance

    raise NotFoundError(
        f"Hermes 实例不存在: {value}",
        "errors.external_docker.instance_not_found",
    )


async def require_instance_viewer_access(
    instance: Instance,
    user: User,
    db: AsyncSession,
) -> None:
    try:
        await instance_member_service.check_instance_access(
            instance.id,
            user,
            InstanceRole.viewer,
            db,
        )
    except ForbiddenError as exc:
        raise ForbiddenError(
            exc.message,
            "errors.external_docker.instance_forbidden",
        ) from exc
