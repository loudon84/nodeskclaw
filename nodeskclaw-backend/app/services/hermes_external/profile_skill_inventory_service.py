"""Runtime + local profile skill inventory aggregation for Hermes Agent Detail."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from pathlib import Path

from app.core.exceptions import ConflictError, NotFoundError
from app.schemas.profile_extended import ProfileSkillItem
from app.schemas.profile_skill_inventory import (
    ProfileSkillGroup,
    ProfileSkillInventoryItem,
    ProfileSkillTreeResponse,
    SkillSource,
    SkillStatus,
    SkillTrust,
)
from app.services.hermes_external import profile_skill_service
from app.services.hermes_external._profile_helpers import resolve_profile_paths
from app.services.hermes_external.path_resolver import DEFAULT_PROFILE_NAME
from app.services.hermes_external.status_service import _docker_inspect

logger = logging.getLogger(__name__)

_RUNTIME_TIMEOUT_SECONDS = 15
_TABLE_HEADER = re.compile(r"^name\s*\|\s*category\s*\|\s*source\s*\|\s*trust\s*\|\s*status", re.I)
_TABLE_ROW = re.compile(r"^\s*([^|]+)\|\s*([^|]*)\|\s*([^|]*)\|\s*([^|]*)\|\s*([^|]*)\s*$")
_SOURCE_PRIORITY = {"profile": 5, "local": 4, "github": 3, "clawhub": 2, "builtin": 1, "unknown": 0}


def _normalize_category(value: str | None) -> str:
    raw = (value or "").strip().lower()
    return raw or "uncategorized"


def _category_label(category: str) -> str:
    if category == "uncategorized":
        return "UNCATEGORIZED"
    return category.replace("-", " ").replace("_", " ").upper()


def _normalize_source(value: str | None) -> SkillSource:
    raw = (value or "").strip().lower()
    if raw in {"builtin", "github", "clawhub", "local", "profile"}:
        return raw  # type: ignore[return-value]
    return "unknown"


def _normalize_trust(value: str | None) -> SkillTrust:
    raw = (value or "").strip().lower()
    if raw in {"builtin", "trusted", "community", "local"}:
        return raw  # type: ignore[return-value]
    return "unknown"


def _normalize_status(value: str | None) -> tuple[SkillStatus, bool]:
    raw = (value or "").strip().lower()
    if raw == "enabled":
        return "enabled", True
    if raw == "disabled":
        return "disabled", False
    return "unknown", True


def _is_manageable_source(source: SkillSource) -> bool:
    return source in {"local", "profile"}


def _runtime_item_from_fields(
    name: str,
    category: str | None,
    source_raw: str | None,
    trust_raw: str | None,
    status_raw: str | None,
    description: str | None = None,
) -> ProfileSkillInventoryItem:
    slug = (name or "").strip()
    source = _normalize_source(source_raw)
    trust = _normalize_trust(trust_raw)
    status, enabled = _normalize_status(status_raw)
    manageable = _is_manageable_source(source)
    return ProfileSkillInventoryItem(
        id=slug,
        slug=slug,
        name=slug,
        description=(description or "").strip() or None,
        category=_normalize_category(category),
        source=source,
        trust=trust,
        status=status,
        enabled=enabled,
        installed=True,
        manageable=manageable,
        path=None,
        profile_path=None,
        has_skill_md=False,
        can_install=False,
        can_enable=manageable and not enabled,
        can_disable=manageable and enabled,
        can_delete=manageable,
        can_authorize=True,
    )


def _parse_runtime_json(stdout: str) -> list[ProfileSkillInventoryItem]:
    payload = json.loads(stdout)
    rows: list[dict] = []
    if isinstance(payload, list):
        rows = [row for row in payload if isinstance(row, dict)]
    elif isinstance(payload, dict):
        for key in ("skills", "items", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                rows = [row for row in value if isinstance(row, dict)]
                break
    items: list[ProfileSkillInventoryItem] = []
    for row in rows:
        name = str(row.get("name") or row.get("slug") or row.get("id") or "").strip()
        if not name:
            continue
        items.append(
            _runtime_item_from_fields(
                name=name,
                category=row.get("category"),
                source_raw=row.get("source"),
                trust_raw=row.get("trust"),
                status_raw=row.get("status"),
                description=row.get("description"),
            )
        )
    return items


def _parse_runtime_table(stdout: str) -> list[ProfileSkillInventoryItem]:
    items: list[ProfileSkillInventoryItem] = []
    for line in stdout.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("-") or _TABLE_HEADER.match(stripped):
            continue
        match = _TABLE_ROW.match(stripped)
        if not match:
            continue
        name, category, source, trust, status = match.groups()
        if not name.strip():
            continue
        items.append(
            _runtime_item_from_fields(
                name=name.strip(),
                category=category,
                source_raw=source,
                trust_raw=trust,
                status_raw=status,
            )
        )
    return items


async def _exec_runtime_command(container_name: str, profile: str, *, use_json: bool) -> tuple[int, str, str]:
    base_cmd = ["docker", "exec", container_name]
    if use_json:
        commands = [
            base_cmd + ["hermes", "-p", profile, "skills", "list", "--json"],
            base_cmd + ["python", "-m", "hermes_cli.main", "-p", profile, "skills", "list", "--json"],
        ]
    else:
        commands = [
            base_cmd + ["hermes", "-p", profile, "skills", "list"],
            base_cmd + ["python", "-m", "hermes_cli.main", "-p", profile, "skills", "list"],
        ]
    last_stderr = ""
    for cmd in commands:
        try:
            proc = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                ),
                timeout=_RUNTIME_TIMEOUT_SECONDS,
            )
            stdout_bytes, stderr_bytes = await proc.communicate()
            stdout = stdout_bytes.decode(errors="replace")
            stderr = stderr_bytes.decode(errors="replace").strip()
            if proc.returncode == 0 and stdout.strip():
                return proc.returncode, stdout, stderr
            last_stderr = stderr or f"exit code {proc.returncode}"
        except TimeoutError:
            last_stderr = "hermes skills list failed: timeout"
        except OSError as exc:
            last_stderr = str(exc)
    return 1, "", last_stderr


async def _fetch_runtime_inventory(
    container_name: str,
    profile: str,
) -> tuple[list[ProfileSkillInventoryItem], list[str]]:
    warnings: list[str] = []
    returncode, stdout, stderr = await _exec_runtime_command(container_name, profile, use_json=True)
    if returncode == 0 and stdout.strip():
        try:
            items = _parse_runtime_json(stdout)
            if items:
                return items, warnings
            warnings.append("Runtime JSON output parsed but contained no skills.")
        except json.JSONDecodeError:
            warnings.append("Failed to parse runtime JSON output, fallback to table parser.")
    elif stderr:
        warnings.append(stderr[:300])

    returncode, stdout, stderr = await _exec_runtime_command(container_name, profile, use_json=False)
    if returncode == 0 and stdout.strip():
        items = _parse_runtime_table(stdout)
        if items:
            return items, warnings
        warnings.append("Runtime table output parsed but contained no skills.")
    elif stderr:
        warnings.append(stderr[:300])

    if not warnings:
        warnings.append("Failed to execute hermes skills list in container.")
    return [], warnings


def _local_item_from_profile_skill(local: ProfileSkillItem) -> ProfileSkillInventoryItem:
    source: SkillSource = "profile" if local.source == "profile" else "local"
    enabled = local.enabled
    return ProfileSkillInventoryItem(
        id=local.slug,
        slug=local.slug,
        name=local.name,
        description=None,
        category="uncategorized",
        source=source,
        trust="local",
        status="enabled" if enabled else "disabled",
        enabled=enabled,
        installed=True,
        manageable=True,
        path=local.path,
        profile_path=local.path,
        has_skill_md=local.has_skill_md,
        can_install=False,
        can_enable=not enabled,
        can_disable=enabled,
        can_delete=True,
        can_authorize=True,
    )


def _merge_runtime_and_local(
    runtime_items: list[ProfileSkillInventoryItem],
    local_items: list[ProfileSkillItem],
) -> list[ProfileSkillInventoryItem]:
    merged: dict[str, ProfileSkillInventoryItem] = {}
    for item in runtime_items:
        merged[item.slug] = item

    for local in local_items:
        local_inv = _local_item_from_profile_skill(local)
        existing = merged.get(local.slug)
        if existing is None:
            merged[local.slug] = local_inv
            continue
        existing.path = local.path
        existing.profile_path = local.path
        existing.has_skill_md = local.has_skill_md
        existing.manageable = True
        existing.can_enable = not existing.enabled
        existing.can_disable = existing.enabled
        existing.can_delete = True
        if existing.source in {"unknown"}:
            existing.source = local_inv.source
            existing.trust = local_inv.trust

    return list(merged.values())


def _dedupe_by_priority(items: list[ProfileSkillInventoryItem]) -> list[ProfileSkillInventoryItem]:
    best: dict[str, ProfileSkillInventoryItem] = {}
    for item in items:
        current = best.get(item.slug)
        if current is None:
            best[item.slug] = item
            continue
        current_priority = _SOURCE_PRIORITY.get(current.source, 0)
        item_priority = _SOURCE_PRIORITY.get(item.source, 0)
        if item_priority > current_priority:
            best[item.slug] = item
        elif item_priority == current_priority and item.manageable and not current.manageable:
            best[item.slug] = item
    return list(best.values())


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
                    item.trust,
                    item.status,
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


async def _ensure_container_running(container_name: str) -> None:
    status, _, err = await _docker_inspect(container_name)
    if status == "missing":
        raise ConflictError(
            message="Hermes container 当前未运行，无法读取 runtime skills",
            message_key="errors.hermes.container_not_running",
        )
    if status != "running":
        raise ConflictError(
            message="Hermes container 当前未运行，无法读取 runtime skills",
            message_key="errors.hermes.container_not_running",
            message_params={"detail": err or status},
        )


async def list_full_skill_inventory(
    agent_profile: str,
    profile: str,
    host_data_dir: Path,
    container_name: str | None = None,
    *,
    keyword: str | None = None,
    include_builtin: bool = True,
    include_local: bool = True,
    include_profile: bool = True,
) -> ProfileSkillTreeResponse:
    _ensure_profile_exists(host_data_dir, profile)
    local_response = profile_skill_service.list_profile_skills(host_data_dir, profile)
    warnings: list[str] = []
    source_mode: str = "profile_only_fallback"
    runtime_items: list[ProfileSkillInventoryItem] = []

    if container_name:
        await _ensure_container_running(container_name)
        runtime_items, runtime_warnings = await _fetch_runtime_inventory(container_name, profile)
        warnings.extend(runtime_warnings)
        if runtime_items:
            source_mode = "runtime_inventory"
        elif not warnings:
            warnings.append(
                "Failed to execute hermes skills list in container, fallback to profile skills dir."
            )
    else:
        warnings.append("No bound container found, fallback to profile skills dir.")

    merged = _merge_runtime_and_local(runtime_items, local_response.items)
    merged = _dedupe_by_priority(merged)
    merged = _apply_filters(
        merged,
        keyword=keyword,
        include_builtin=include_builtin,
        include_local=include_local,
        include_profile=include_profile,
    )
    groups = _group_items(merged)
    enabled_count = sum(1 for item in merged if item.enabled)
    manageable_count = sum(1 for item in merged if item.manageable)

    return ProfileSkillTreeResponse(
        agent_profile=agent_profile,
        profile=profile,
        source_mode=source_mode,  # type: ignore[arg-type]
        total=len(merged),
        enabled_count=enabled_count,
        manageable_count=manageable_count,
        warnings=warnings,
        groups=groups,
    )
