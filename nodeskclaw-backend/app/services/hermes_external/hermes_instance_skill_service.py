"""Fetch and cache Hermes Agent instance skills from API_SERVER."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException, ConflictError, ForbiddenError, NotFoundError
from app.schemas.hermes_instance_skill import HermesInstanceSkillItem, HermesInstanceSkillListResponse
from app.services.hermes_external.hermes_api_server_client import HermesApiServerClient
from app.services.hermes_external.hermes_docker_binding_service import HermesDockerBindingService
from app.services.hermes_external.hermes_env_parser import parse_env_file

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 30
_AGENT_SLUG_RE = re.compile(r"[^a-z0-9]+")


@dataclass
class _CacheEntry:
    expires_at: float
    payload: HermesInstanceSkillListResponse


_cache: dict[str, _CacheEntry] = {}


def agent_profile_to_slug(agent_profile: str) -> str:
    raw = (agent_profile or "").strip().lower()
    return _AGENT_SLUG_RE.sub("_", raw).strip("_")


def skill_name_to_slug(skill_name: str) -> str:
    raw = (skill_name or "").strip().lower()
    return _AGENT_SLUG_RE.sub("-", raw).strip("-")


def build_tool_name(agent_profile: str, skill_name: str) -> str:
    return f"hermes_{agent_profile_to_slug(agent_profile)}__{skill_name_to_slug(skill_name)}"


def parse_tool_name(tool_name: str) -> tuple[str, str] | None:
    raw = (tool_name or "").strip()
    if not raw.startswith("hermes_") or "__" not in raw:
        return None
    prefix, skill_slug = raw.split("__", 1)
    agent_slug = prefix.removeprefix("hermes_").strip("_")
    if not agent_slug or not skill_slug:
        return None
    return agent_slug, skill_slug


def _normalize_category(value: str | None) -> str | None:
    raw = (value or "").strip().lower()
    return raw or None


def _parse_api_server_skills(data: dict | list | None) -> list[HermesInstanceSkillItem]:
    rows: list[dict] = []
    if isinstance(data, list):
        rows = [row for row in data if isinstance(row, dict)]
    elif isinstance(data, dict):
        for key in ("skills", "items", "data"):
            value = data.get(key)
            if isinstance(value, list):
                rows = [row for row in value if isinstance(row, dict)]
                break

    items: list[HermesInstanceSkillItem] = []
    for row in rows:
        name = str(row.get("name") or row.get("slug") or row.get("id") or "").strip()
        if not name:
            continue
        items.append(
            HermesInstanceSkillItem(
                name=name,
                description=(row.get("description") or "").strip() or None,
                category=_normalize_category(row.get("category")),
                source="api_server",
                status="enabled",
                runtime_available=True,
                callable=True,
            )
        )
    return items


def raise_not_configured(detail: str = "") -> None:
    raise ConflictError(
        message="该实例未启用 API_SERVER，请在实例 .env 配置 API_SERVER_ENABLED 与 API_SERVER_KEY",
        message_key="errors.hermes.api_server_not_configured",
        message_params={"detail": detail} if detail else None,
    )


def raise_unauthorized() -> None:
    raise ForbiddenError(
        message="Hermes API_SERVER 鉴权失败，请检查 API_SERVER_KEY 配置",
        message_key="errors.hermes.api_server_unauthorized",
    )


def raise_offline(detail: str = "") -> None:
    raise AppException(
        code=50301,
        error_code=50301,
        message="无法连接 Hermes API_SERVER，请确认实例容器运行中",
        message_key="errors.hermes.api_server_offline",
        status_code=503,
        message_params={"detail": detail} if detail else None,
    )


def resolve_api_server_client(gateway_url: str | None, env_file: str | None) -> HermesApiServerClient:
    if not gateway_url:
        raise_not_configured("gateway_url missing")
    if not env_file:
        raise_not_configured("env_file missing")

    env_path = Path(env_file)
    env = parse_env_file(env_path, require_gateway_port=False)
    if env.api_server_enabled is False:
        raise_not_configured("API_SERVER_ENABLED is false")
    if not env.has_api_server_key:
        raise_not_configured("API_SERVER_KEY missing")

    api_key = (env.raw.get("API_SERVER_KEY") or "").strip()
    if not api_key:
        raise_not_configured("API_SERVER_KEY missing")

    return HermesApiServerClient(base_url=gateway_url, api_key=api_key)


def is_gateway_configured(gateway_url: str | None, env_file: str | None) -> bool:
    if not gateway_url or not env_file:
        return False
    try:
        env_path = Path(env_file)
        if not env_path.is_file():
            return False
        env = parse_env_file(env_path, require_gateway_port=False)
        if env.api_server_enabled is False:
            return False
        return bool(env.has_api_server_key and (env.raw.get("API_SERVER_KEY") or "").strip())
    except Exception:
        return False


def invalidate_cache(agent_profile: str) -> None:
    _cache.pop(agent_profile, None)


async def fetch_instance_skills_from_api_server(
    agent_profile: str,
    gateway_url: str | None,
    env_file: str | None,
) -> HermesInstanceSkillListResponse:
    client = resolve_api_server_client(gateway_url, env_file)
    response = await client.list_skills()
    if response.error == "unauthorized":
        raise_unauthorized()
    if response.error in {"offline", "timeout"}:
        raise_offline(response.error or "")
    if not response.ok:
        raise_offline(response.error or "invalid_response")

    skills = _parse_api_server_skills(response.data)  # type: ignore[arg-type]
    warnings: list[str] = []
    if not skills and response.data not in (None, [], {}):
        logger.warning("API_SERVER /v1/skills returned unexpected payload: %r", response.data)
        warnings.append("Hermes API_SERVER returned unexpected skills payload.")
    if not skills:
        warnings.append("Hermes API_SERVER returned empty skills.")

    now = datetime.now(timezone.utc)
    return HermesInstanceSkillListResponse(
        agent_profile=agent_profile,
        gateway_url=gateway_url,
        source_mode="api_server_default",
        exposed_profile="default",
        total=len(skills),
        skills=skills,
        warnings=warnings,
        last_refreshed_at=now,
    )


async def list_instance_skills(
    db: AsyncSession,
    org_id: str,
    agent_profile: str,
    *,
    force_refresh: bool = False,
) -> HermesInstanceSkillListResponse:
    binding = HermesDockerBindingService(db)
    record = await binding.get_by_profile(org_id, agent_profile)
    if not record:
        raise NotFoundError(
            message="Hermes Agent 实例不存在",
            message_key="errors.hermes.agent_instance_not_found",
        )

    if not force_refresh:
        cached = _cache.get(agent_profile)
        if cached and cached.expires_at > datetime.now(timezone.utc).timestamp():
            return cached.payload

    payload = await fetch_instance_skills_from_api_server(
        agent_profile,
        record.gateway_url,
        record.env_file,
    )
    _cache[agent_profile] = _CacheEntry(
        expires_at=datetime.now(timezone.utc).timestamp() + CACHE_TTL_SECONDS,
        payload=payload,
    )
    return payload
