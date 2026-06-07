"""Manifest parsing for Hermes expert skill packages."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.core.exceptions import BadRequestError


@dataclass
class ExpertSkillManifest:
    slug: str
    name: str
    version: str
    description: str
    runtime: str = "hermes"
    expert: list[str] | None = None
    entry: str = "SKILL.md"
    enabled: bool = True
    requires_restart: bool = False


def parse_manifest(skill_dir: Path) -> ExpertSkillManifest:
    manifest_path = skill_dir / "manifest.json"
    if not manifest_path.is_file():
        raise BadRequestError(
            message=f"技能包缺少 manifest.json: {skill_dir.name}",
            message_key="errors.hermes_expert.skill_manifest_missing",
        )
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BadRequestError(
            message=f"manifest.json 解析失败: {exc}",
            message_key="errors.hermes_expert.skill_manifest_invalid",
        ) from exc
    if not isinstance(raw, dict):
        raise BadRequestError(
            message="manifest.json 必须是 JSON 对象",
            message_key="errors.hermes_expert.skill_manifest_invalid",
        )
    slug = str(raw.get("slug") or skill_dir.name).strip()
    name = str(raw.get("name") or slug).strip()
    if not slug or not name:
        raise BadRequestError(
            message="manifest.json 缺少 slug 或 name",
            message_key="errors.hermes_expert.skill_manifest_invalid",
        )
    expert = raw.get("expert")
    expert_list = None
    if isinstance(expert, list):
        expert_list = [str(item) for item in expert]
    return ExpertSkillManifest(
        slug=slug,
        name=name,
        version=str(raw.get("version") or "0.1.0"),
        description=str(raw.get("description") or ""),
        runtime=str(raw.get("runtime") or "hermes"),
        expert=expert_list,
        entry=str(raw.get("entry") or "SKILL.md"),
        enabled=bool(raw.get("enabled", True)),
        requires_restart=bool(raw.get("requires_restart", False)),
    )


def write_manifest(skill_dir: Path, manifest: ExpertSkillManifest) -> None:
    payload = {
        "slug": manifest.slug,
        "name": manifest.name,
        "version": manifest.version,
        "description": manifest.description,
        "runtime": manifest.runtime,
        "expert": manifest.expert or [],
        "entry": manifest.entry,
        "enabled": manifest.enabled,
        "requires_restart": manifest.requires_restart,
    }
    (skill_dir / "manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def list_skill_files(skill_dir: Path) -> list[str]:
    files: list[str] = []
    if not skill_dir.is_dir():
        return files
    for path in sorted(skill_dir.rglob("*")):
        if path.is_file():
            files.append(str(path.relative_to(skill_dir)).replace("\\", "/"))
    return files
