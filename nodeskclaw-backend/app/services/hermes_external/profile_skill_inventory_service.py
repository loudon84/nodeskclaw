"""API_SERVER skill inventory aggregation for Hermes Agent Detail skills tab."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.base import not_deleted
from app.models.hermes_skill.skill import HermesSkill
from app.models.hermes_skill.skill_installation import HermesSkillInstallation
from app.schemas.profile_skill_inventory import (
    ProfileSkillGroup,
    ProfileSkillInventoryItem,
    ProfileSkillTreeResponse,
)
from app.schemas.hermes_instance_skill import HermesInstanceSkillItem
from app.services.hermes_external import hermes_instance_skill_service as instance_skill_service
from app.services.hermes_external._profile_helpers import resolve_profile_paths
from app.services.hermes_external.path_resolver import DEFAULT_PROFILE_NAME


def _normalize_category(value: str | None) -> str:
    raw = (value or "").strip().lower()
    return raw or "uncategorized"


def _category_label(category: str) -> str:
    if category == "uncategorized":
        return "UNCATEGORIZED"
    return category.replace("-", " ").replace("_", " ").upper()


def _inventory_item_from_instance_skill(
    skill: HermesInstanceSkillItem,
    *,
    org_mcp_registered: bool = False,
    org_mcp_tool_name: str | None = None,
    execution_instance_name: str | None = None,
) -> ProfileSkillInventoryItem:
    slug = skill.name.strip()
    return ProfileSkillInventoryItem(
        id=slug,
        slug=slug,
        name=slug,
        description=skill.description,
        category=_normalize_category(skill.category),
        source="api_server",
        trust="unknown",
        status="enabled",
        enabled=True,
        installed=True,
        manageable=False,
        path=None,
        profile_path=None,
        has_skill_md=False,
        can_install=False,
        can_enable=False,
        can_disable=False,
        can_delete=False,
        can_authorize=True,
        org_mcp_registered=org_mcp_registered,
        org_mcp_tool_name=org_mcp_tool_name,
        execution_instance_name=execution_instance_name,
    )


def _apply_filters(
    items: list[ProfileSkillInventoryItem],
    *,
    keyword: str | None,
    include_builtin: bool,
    include_local: bool,
    include_profile: bool,
) -> list[ProfileSkillInventoryItem]:
    filtered = items
    if not include_builtin:
        filtered = [item for item in filtered if item.source != "builtin"]
    if not include_local:
        filtered = [item for item in filtered if item.source != "local"]
    if not include_profile:
        filtered = [item for item in filtered if item.source != "profile"]

    keyword_value = (keyword or "").strip().lower()
    if not keyword_value:
        return filtered

    result: list[ProfileSkillInventoryItem] = []
    for item in filtered:
        haystack = " ".join(
            filter(
                None,
                [
                    item.slug,
                    item.name,
                    item.description or "",
                    item.category,
                    item.source,
                ],
            )
        ).lower()
        if keyword_value in haystack:
            result.append(item)
    return result


def _group_items(items: list[ProfileSkillInventoryItem]) -> list[ProfileSkillGroup]:
    grouped: dict[str, list[ProfileSkillInventoryItem]] = {}
    for item in sorted(items, key=lambda row: (row.category, row.slug.lower())):
        grouped.setdefault(item.category, []).append(item)
    return [
        ProfileSkillGroup(
            category=category,
            label=_category_label(category),
            count=len(group_items),
            items=group_items,
        )
        for category, group_items in sorted(grouped.items(), key=lambda pair: pair[0])
    ]


def _ensure_profile_exists(host_data_dir: Path, profile: str) -> None:
    pp = resolve_profile_paths(host_data_dir, profile)
    if profile != DEFAULT_PROFILE_NAME and not pp.profile_dir.is_dir():
        raise NotFoundError(
            message=f"Profile {profile} 不存在",
            message_key="errors.external_docker.profile_not_found",
        )


async def _load_org_mcp_registration_map(
    db: AsyncSession,
    org_id: str,
    agent_profile: str,
    skill_names: list[str],
) -> dict[str, dict[str, str | bool]]:
    if not skill_names:
        return {}

    tool_names = {
        instance_skill_service.build_tool_name(agent_profile, name): name
        for name in skill_names
    }
    installed_subq = (
        select(HermesSkillInstallation.skill_id)
        .where(
            not_deleted(HermesSkillInstallation),
            HermesSkillInstallation.org_id == org_id,
            HermesSkillInstallation.status == "installed",
            HermesSkillInstallation.skill_id == HermesSkill.skill_id,
        )
        .correlate(HermesSkill)
    )
    result = await db.execute(
        select(HermesSkill).where(
            not_deleted(HermesSkill),
            HermesSkill.org_id == org_id,
            HermesSkill.source_type == "hermes_api_server",
            HermesSkill.tool_name.in_(list(tool_names.keys())),
            HermesSkill.is_active.is_(True),
            exists(installed_subq),
        )
    )
    mapping: dict[str, dict[str, str | bool]] = {}
    for row in result.scalars().all():
        runtime_name = tool_names.get(row.tool_name or "")
        if not runtime_name:
            continue
        meta = row.extra_metadata or {}
        mapping[runtime_name] = {
            "org_mcp_registered": True,
            "org_mcp_tool_name": row.tool_name,
            "execution_instance_name": str(
                meta.get("hermes_instance_name") or agent_profile,
            ),
        }
    return mapping


async def list_full_skill_inventory(
    db: AsyncSession,
    org_id: str,
    agent_profile: str,
    profile: str,
    host_data_dir: Path,
    *,
    keyword: str | None = None,
    include_builtin: bool = True,
    include_local: bool = True,
    include_profile: bool = True,
    force_refresh: bool = False,
) -> ProfileSkillTreeResponse:
    _ensure_profile_exists(host_data_dir, profile)
    instance_list = await instance_skill_service.list_instance_skills(
        db,
        org_id,
        agent_profile,
        force_refresh=force_refresh,
    )
    registration_map = await _load_org_mcp_registration_map(
        db,
        org_id,
        agent_profile,
        [skill.name for skill in instance_list.skills],
    )
    items = []
    for skill in instance_list.skills:
        reg = registration_map.get(skill.name, {})
        items.append(
            _inventory_item_from_instance_skill(
                skill,
                org_mcp_registered=bool(reg.get("org_mcp_registered")),
                org_mcp_tool_name=reg.get("org_mcp_tool_name"),  # type: ignore[arg-type]
                execution_instance_name=reg.get("execution_instance_name"),  # type: ignore[arg-type]
            )
        )
    filtered = _apply_filters(
        items,
        keyword=keyword,
        include_builtin=include_builtin,
        include_local=include_local,
        include_profile=include_profile,
    )
    groups = _group_items(filtered)
    enabled_count = sum(1 for item in filtered if item.enabled)
    manageable_count = sum(1 for item in filtered if item.manageable)

    return ProfileSkillTreeResponse(
        agent_profile=agent_profile,
        profile=profile,
        source_mode="api_server_inventory",
        total=len(filtered),
        enabled_count=enabled_count,
        manageable_count=manageable_count,
        warnings=instance_list.warnings,
        groups=groups,
    )
