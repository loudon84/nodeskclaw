"""API_SERVER skill inventory aggregation for Hermes Agent Detail skills tab."""

from __future__ import annotations

import logging
from pathlib import Path

from app.core.exceptions import AppException, ConflictError, ForbiddenError, NotFoundError
from app.schemas.profile_skill_inventory import (
    ProfileSkillGroup,
    ProfileSkillInventoryItem,
    ProfileSkillTreeResponse,
)
from app.services.hermes_external._profile_helpers import resolve_profile_paths
from app.services.hermes_external.hermes_api_server_client import HermesApiServerClient
from app.services.hermes_external.hermes_env_parser import parse_env_file
from app.services.hermes_external.path_resolver import DEFAULT_PROFILE_NAME

logger = logging.getLogger(__name__)


def _normalize_category(value: str | None) -> str:
    raw = (value or "").strip().lower()
    return raw or "uncategorized"


def _category_label(category: str) -> str:
    if category == "uncategorized":
        return "UNCATEGORIZED"
    return category.replace("-", " ").replace("_", " ").upper()


def _api_server_item_from_fields(
    name: str,
    category: str | None,
    description: str | None = None,
) -> ProfileSkillInventoryItem:
    slug = (name or "").strip()
    return ProfileSkillInventoryItem(
        id=slug,
        slug=slug,
        name=slug,
        description=(description or "").strip() or None,
        category=_normalize_category(category),
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
    )


def _parse_api_server_skills(data: dict | list | None) -> list[ProfileSkillInventoryItem]:
    rows: list[dict] = []
    if isinstance(data, list):
        rows = [row for row in data if isinstance(row, dict)]
    elif isinstance(data, dict):
        for key in ("skills", "items", "data"):
            value = data.get(key)
            if isinstance(value, list):
                rows = [row for row in value if isinstance(row, dict)]
                break

    items: list[ProfileSkillInventoryItem] = []
    for row in rows:
        name = str(row.get("name") or row.get("slug") or row.get("id") or "").strip()
        if not name:
            continue
        items.append(
            _api_server_item_from_fields(
                name=name,
                category=row.get("category"),
                description=row.get("description"),
            )
        )
    return items


def _raise_not_configured(detail: str = "") -> None:
    raise ConflictError(
        message="该实例未启用 API_SERVER，请在实例 .env 配置 API_SERVER_ENABLED 与 API_SERVER_KEY",
        message_key="errors.hermes.api_server_not_configured",
        message_params={"detail": detail} if detail else None,
    )


def _raise_unauthorized() -> None:
    raise ForbiddenError(
        message="Hermes API_SERVER 鉴权失败，请检查 API_SERVER_KEY 配置",
        message_key="errors.hermes.api_server_unauthorized",
    )


def _raise_offline(detail: str = "") -> None:
    raise AppException(
        code=50301,
        error_code=50301,
        message="无法连接 Hermes API_SERVER，请确认实例容器运行中",
        message_key="errors.hermes.api_server_offline",
        status_code=503,
        message_params={"detail": detail} if detail else None,
    )


def _resolve_api_server_client(gateway_url: str | None, env_file: str | None) -> HermesApiServerClient:
    if not gateway_url:
        _raise_not_configured("gateway_url missing")
    if not env_file:
        _raise_not_configured("env_file missing")

    env_path = Path(env_file)
    env = parse_env_file(env_path, require_gateway_port=False)
    if env.api_server_enabled is False:
        _raise_not_configured("API_SERVER_ENABLED is false")
    if not env.has_api_server_key:
        _raise_not_configured("API_SERVER_KEY missing")

    api_key = (env.raw.get("API_SERVER_KEY") or "").strip()
    if not api_key:
        _raise_not_configured("API_SERVER_KEY missing")

    return HermesApiServerClient(base_url=gateway_url, api_key=api_key)


async def _fetch_api_server_inventory(
    gateway_url: str | None,
    env_file: str | None,
) -> list[ProfileSkillInventoryItem]:
    client = _resolve_api_server_client(gateway_url, env_file)
    response = await client.list_skills()
    if response.error == "unauthorized":
        _raise_unauthorized()
    if response.error in {"offline", "timeout"}:
        _raise_offline(response.error or "")
    if not response.ok:
        _raise_offline(response.error or "invalid_response")

    items = _parse_api_server_skills(response.data)  # type: ignore[arg-type]
    if not items and response.data not in (None, [], {}):
        logger.warning("API_SERVER /v1/skills returned unexpected payload: %r", response.data)
    return items


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


async def list_full_skill_inventory(
    agent_profile: str,
    profile: str,
    host_data_dir: Path,
    gateway_url: str | None = None,
    env_file: str | None = None,
    *,
    keyword: str | None = None,
    include_builtin: bool = True,
    include_local: bool = True,
    include_profile: bool = True,
) -> ProfileSkillTreeResponse:
    _ensure_profile_exists(host_data_dir, profile)
    items = await _fetch_api_server_inventory(gateway_url, env_file)
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
        warnings=[],
        groups=groups,
    )
