"""Filesystem helpers for Hermes expert instances."""

from __future__ import annotations

import json
import os
import re
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from app.core.exceptions import BadRequestError
from app.services.docker_constants import DOCKER_DATA_DIR, DOCKER_HOST_DATA_DIR

RESOURCES_ROOT = Path(__file__).resolve().parents[2] / "resources" / "hermes_webui_expert"
PLACEHOLDER_PATTERN = re.compile(r"__([A-Z0-9_]+)__")
SLUG_PATTERN = re.compile(r"^[a-z][a-z0-9-]{1,62}$")


def expert_resources_root() -> Path:
    return RESOURCES_ROOT


def expert_host_data_dir(instance_slug: str) -> Path:
    root = Path(DOCKER_DATA_DIR) / instance_slug / "data" / "hermes"
    root.mkdir(parents=True, exist_ok=True)
    return root


def expert_host_data_dir_for_bind(instance_slug: str) -> str:
    return str(Path(DOCKER_HOST_DATA_DIR) / instance_slug / "data" / "hermes")


def expert_skills_dir(instance_slug: str) -> Path:
    path = expert_host_data_dir(instance_slug) / "skills"
    path.mkdir(parents=True, exist_ok=True)
    return path


def expert_compose_dir(instance_slug: str) -> Path:
    path = Path(DOCKER_DATA_DIR) / instance_slug
    path.mkdir(parents=True, exist_ok=True)
    return path


def validate_profile_slug(value: str, field_name: str = "profile") -> str:
    slug = (value or "").strip().lower()
    if not SLUG_PATTERN.match(slug):
        raise BadRequestError(
            message=f"{field_name} 格式无效，需为小写字母、数字和连字符",
            message_key="errors.validation.invalid_slug",
        )
    return slug


def render_placeholders(content: str, mapping: dict[str, str]) -> str:
    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        return mapping.get(key, match.group(0))

    return PLACEHOLDER_PATTERN.sub(repl, content)


def copy_tree_with_placeholders(
    source: Path,
    target: Path,
    mapping: dict[str, str],
    *,
    overwrite: bool = True,
) -> None:
    if not source.is_dir():
        raise BadRequestError(
            message=f"模板目录不存在: {source.name}",
            message_key="errors.hermes_expert.template_not_found",
        )
    for root, dirs, files in os.walk(source):
        rel = Path(root).relative_to(source)
        dest_root = target / rel
        dest_root.mkdir(parents=True, exist_ok=True)
        for dirname in dirs:
            (dest_root / dirname).mkdir(parents=True, exist_ok=True)
        for filename in files:
            src_file = Path(root) / filename
            dest_file = dest_root / filename
            if dest_file.exists() and not overwrite:
                continue
            if src_file.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".zip"}:
                shutil.copy2(src_file, dest_file)
                continue
            try:
                text = src_file.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                shutil.copy2(src_file, dest_file)
                continue
            dest_file.write_text(render_placeholders(text, mapping), encoding="utf-8")


def backup_path(target: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = target.parent / f"{target.name}.backup.{stamp}"
    if target.is_dir():
        shutil.copytree(target, backup, dirs_exist_ok=True)
    elif target.is_file():
        shutil.copy2(target, backup)
    return backup


def ensure_default_layout(data_dir: Path, *, init_obsidian: bool = True) -> None:
    for name in ("skills", "sessions", "logs", "webui", "memories", "hindsight", "workspace"):
        (data_dir / name).mkdir(parents=True, exist_ok=True)
    workspace = data_dir / "workspace"
    for sub in ("materials", "references", "drafts", "exports"):
        (workspace / sub).mkdir(parents=True, exist_ok=True)
    if init_obsidian:
        vault = data_dir / "obsidian-vault"
        for sub in (
            "00-Inbox", "10-Articles", "20-Research", "30-Templates",
            "40-Content-Calendar", "50-Policies", "60-Reports", "90-Archive",
        ):
            (vault / sub).mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def safe_extract_zip(zip_bytes: bytes, target_dir: Path, *, max_size_mb: int = 50) -> Path:
    if len(zip_bytes) > max_size_mb * 1024 * 1024:
        raise BadRequestError(
            message=f"技能包超过 {max_size_mb}MB 限制",
            message_key="errors.hermes_expert.skill_zip_too_large",
        )
    temp_zip = target_dir.parent / f".upload-{os.urandom(4).hex()}.zip"
    temp_zip.write_bytes(zip_bytes)
    extract_root = target_dir.parent / f".extract-{os.urandom(4).hex()}"
    extract_root.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(temp_zip, "r") as zf:
            for info in zf.infolist():
                name = info.filename.replace("\\", "/")
                if name.startswith("/") or ".." in Path(name).parts:
                    raise BadRequestError(
                        message="技能包包含非法路径",
                        message_key="errors.hermes_expert.skill_zip_invalid_path",
                    )
            zf.extractall(extract_root)
    finally:
        temp_zip.unlink(missing_ok=True)

    candidates = [p for p in extract_root.iterdir() if p.is_dir()]
    if len(candidates) == 1 and (candidates[0] / "SKILL.md").is_file():
        return candidates[0]
    if (extract_root / "SKILL.md").is_file():
        return extract_root
    raise BadRequestError(
        message="技能包结构无效，需包含 SKILL.md",
        message_key="errors.hermes_expert.skill_zip_invalid_structure",
    )
