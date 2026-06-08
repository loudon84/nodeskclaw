"""GeneHub manifest and bundle generation."""

import hashlib
import hmac
import json
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.gene import Gene
from app.schemas.genehub import AdminGeneHubSkillCreate

GENEHUB_MANIFEST_SCHEMA = "genehub.gene.v1"
GENEHUB_BUNDLE_SCHEMA = "genehub.bundle.v1"
SKILL_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
FORBIDDEN_SKILL_NAMES = frozenset({".", "..", ".hidden"})


def validate_skill_name(name: str) -> str:
    if name in FORBIDDEN_SKILL_NAMES:
        raise BadRequestError(
            "skill name 无效",
            message_key="errors.genehub.invalid_skill_name",
        )
    if "/" in name or "\\" in name or any(ord(ch) < 32 for ch in name):
        raise BadRequestError(
            "skill name 无效",
            message_key="errors.genehub.invalid_skill_name",
        )
    if not SKILL_NAME_PATTERN.match(name):
        raise BadRequestError(
            "skill name 无效",
            message_key="errors.genehub.invalid_skill_name",
        )
    return name


def _extract_skill_name(skill_content: str, slug: str) -> str:
    for line in skill_content.splitlines():
        stripped = line.strip()
        if stripped.startswith("name:"):
            return validate_skill_name(stripped.split(":", 1)[1].strip())
    return validate_skill_name(slug)


def validate_manifest(manifest: dict[str, Any]) -> None:
    required = [
        "schema_version",
        "slug",
        "version",
        "name",
        "compatibility",
        "skill",
        "install",
    ]
    for field in required:
        if field not in manifest:
            raise BadRequestError(
                f"manifest 缺少必填字段: {field}",
                message_key="errors.genehub.invalid_manifest",
            )

    skill = manifest.get("skill") or {}
    if not skill.get("name") or not skill.get("content"):
        raise BadRequestError(
            "manifest skill.name 或 skill.content 缺失",
            message_key="errors.genehub.invalid_manifest",
        )

    install = manifest.get("install") or {}
    if "hermes_desktop" not in install:
        raise BadRequestError(
            "manifest install.hermes_desktop 缺失",
            message_key="errors.genehub.invalid_manifest",
        )

    validate_skill_name(skill["name"])


def is_hermes_desktop_compatible(manifest: dict[str, Any] | None) -> bool:
    if not manifest:
        return False
    compatibility = manifest.get("compatibility") or []
    return any(
        item.get("runtime") == "hermes" and item.get("target") == "desktop"
        for item in compatibility
        if isinstance(item, dict)
    )


def build_manifest_from_skill(data: AdminGeneHubSkillCreate) -> dict[str, Any]:
    skill_name = _extract_skill_name(data.skill_content, data.slug)
    manifest: dict[str, Any] = {
        "schema_version": GENEHUB_MANIFEST_SCHEMA,
        "slug": data.slug,
        "version": data.version,
        "name": data.name,
        "description": data.description,
        "category": data.category,
        "tags": data.tags,
        "compatibility": [item.model_dump() for item in data.compatibility],
        "skill": {
            "name": skill_name,
            "content": data.skill_content,
        },
        "scripts": data.scripts,
        "mcp": {
            "requires_gateway": False,
            "allowed_tools": [],
        },
        "permissions": {
            "filesystem": ["read:user_selected_files"],
            "network": [],
            "mcp": [],
        },
        "install": {
            "hermes_desktop": {
                "skill_dir": "~/.hermes/skills",
                "scripts_dir": "~/.hermes/scripts",
                "restart_required": True,
            }
        },
    }
    validate_manifest(manifest)
    return manifest


def sanitize_bundle_paths(files: dict[str, str]) -> dict[str, str]:
    sanitized: dict[str, str] = {}
    for path, content in files.items():
        normalized = path.replace("\\", "/")
        if normalized.startswith("/") or ".." in normalized.split("/"):
            raise BadRequestError(
                "Bundle 路径非法",
                message_key="errors.genehub.invalid_bundle_path",
            )
        sanitized[normalized] = content
    return sanitized


def _calculate_sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _sign_bundle(bundle_json: str, secret: str) -> dict[str, str]:
    signature = hmac.new(secret.encode("utf-8"), bundle_json.encode("utf-8"), hashlib.sha256).hexdigest()
    return {"algorithm": "hmac-sha256", "value": signature}


def _build_files_from_manifest(manifest: dict[str, Any]) -> dict[str, str]:
    skill_name = manifest["skill"]["name"]
    files: dict[str, str] = {
        f"skills/{skill_name}/SKILL.md": manifest["skill"]["content"],
    }
    scripts = manifest.get("scripts") or {}
    for script_name, script_content in scripts.items():
        files[f"scripts/{script_name}"] = script_content
    return sanitize_bundle_paths(files)


def build_bundle_from_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    validate_manifest(manifest)
    files = _build_files_from_manifest(manifest)
    manifest_json = json.dumps(manifest, sort_keys=True, ensure_ascii=False)
    manifest_hash = _calculate_sha256(manifest_json)

    bundle_body = {
        "schema_version": GENEHUB_BUNDLE_SCHEMA,
        "manifest": manifest,
        "files": files,
        "hashes": {
            "manifest_sha256": manifest_hash,
        },
    }
    bundle_json = json.dumps(bundle_body, sort_keys=True, ensure_ascii=False)
    bundle_hash = _calculate_sha256(bundle_json)
    bundle_body["hashes"]["bundle_sha256"] = bundle_hash

    if settings.GENEHUB_BUNDLE_SIGNATURE_ENABLED:
        secret = settings.GENEHUB_BUNDLE_SIGNING_SECRET
        if not secret:
            raise BadRequestError(
                "Bundle 签名失败：未配置签名密钥",
                message_key="errors.genehub.bundle_sign_failed",
            )
        bundle_body["signature"] = _sign_bundle(bundle_json, secret)

    return bundle_body


async def build_hermes_desktop_bundle(
    db: AsyncSession,
    *,
    gene_id: str,
    version: str | None = None,
) -> dict[str, Any]:
    result = await db.execute(
        select(Gene).where(Gene.id == gene_id, Gene.deleted_at.is_(None))
    )
    gene = result.scalar_one_or_none()
    if not gene:
        raise NotFoundError(
            "Skill 不存在",
            message_key="errors.genehub.skill_not_found",
        )
    if version and version != "latest" and gene.version != version:
        raise NotFoundError(
            "Skill 版本不存在",
            message_key="errors.genehub.skill_not_found",
        )
    if not gene.manifest:
        raise BadRequestError(
            "manifest 无效",
            message_key="errors.genehub.invalid_manifest",
        )

    manifest = json.loads(gene.manifest)
    if not is_hermes_desktop_compatible(manifest):
        raise BadRequestError(
            "Skill 不支持 Hermes Desktop",
            message_key="errors.genehub.unsupported_runtime",
        )
    return build_bundle_from_manifest(manifest)
