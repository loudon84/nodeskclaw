"""External Docker Hermes skills directory service."""

from __future__ import annotations

from pathlib import Path

from app.models.instance import Instance
from app.schemas.external_docker import ExternalDockerSkillItem, ExternalDockerSkillsResponse
from app.services.hermes_external._common import resolve_paths
from app.services.hermes_external.path_resolver import HermesExternalPathResolver

_path_resolver = HermesExternalPathResolver()

_SCAN_DIRS: list[tuple[str, Path, str]] = []


def _scan_dir(base: Path, category: str, kind: str) -> list[ExternalDockerSkillItem]:
    if not base.is_dir():
        return []
    items: list[ExternalDockerSkillItem] = []
    for entry in sorted(base.iterdir(), key=lambda p: p.name.lower()):
        items.append(
            ExternalDockerSkillItem(
                name=entry.name,
                path=str(entry),
                kind="directory" if entry.is_dir() else "file",
                category=category,
            )
        )
    return items


def list_skills(instance: Instance) -> ExternalDockerSkillsResponse:
    ep = resolve_paths(instance)
    _path_resolver.ensure_auto_create_dirs(ep)

    skill_inbox = ep.skill_inbox_dir
    legacy_inbox = ep.host_data_dir / "skills-inbox"
    inbox_dir = skill_inbox if skill_inbox.is_dir() else legacy_inbox

    items: list[ExternalDockerSkillItem] = []
    items.extend(_scan_dir(ep.skills_dir, "skills", "skill"))
    items.extend(_scan_dir(inbox_dir, "skill-inbox", "skill-inbox"))
    items.extend(_scan_dir(ep.tools_dir, "tools", "tool"))
    items.extend(_scan_dir(ep.plugins_dir, "plugins", "plugin"))

    return ExternalDockerSkillsResponse(
        skills_dir=str(ep.skills_dir),
        skill_inbox_dir=str(inbox_dir),
        tools_dir=str(ep.tools_dir),
        plugins_dir=str(ep.plugins_dir),
        items=items,
    )
