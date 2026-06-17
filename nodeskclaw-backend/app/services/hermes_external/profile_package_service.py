"""Per-profile Hermes package service: clone, export, import."""

from __future__ import annotations

import json
import os
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from app.core.exceptions import BadRequestError, NotFoundError
from app.schemas.profile_extended import (
    ProfileCloneResponse,
    ProfileExportResponse,
    ProfileImportResponse,
)
from app.services.hermes_external._profile_helpers import (
    profile_export_root,
    resolve_profile_paths,
    validate_profile_name_or_raise,
)
from app.services.hermes_external.path_resolver import DEFAULT_PROFILE_NAME

_CORE_FILES = (".env", "config.yaml", "SOUL.md")
_EXCLUDE_DIRS = {"backups", "sessions", "logs", "cache"}


def _copy_profile_contents(
    source_pp,
    target_pp,
    *,
    include_skills: bool,
    include_workspace: bool,
) -> None:
    target_pp.profile_dir.mkdir(parents=True, exist_ok=True)
    for name in _CORE_FILES:
        src = source_pp.profile_dir / name
        if src.is_file():
            shutil.copy2(src, target_pp.profile_dir / name)
    if include_skills and source_pp.skills_dir.is_dir():
        if target_pp.skills_dir.exists():
            shutil.rmtree(target_pp.skills_dir)
        shutil.copytree(source_pp.skills_dir, target_pp.skills_dir)
    if include_workspace and source_pp.workspace_dir.is_dir():
        if target_pp.workspace_dir.exists():
            shutil.rmtree(target_pp.workspace_dir)
        shutil.copytree(source_pp.workspace_dir, target_pp.workspace_dir)


def clone_profile(
    host_data_dir: Path,
    source_profile: str,
    *,
    target_profile: str,
    include_skills: bool = True,
    include_workspace: bool = False,
    overwrite: bool = False,
) -> ProfileCloneResponse:
    target = validate_profile_name_or_raise(target_profile)
    if target == DEFAULT_PROFILE_NAME:
        raise BadRequestError(
            message="不能克隆为 default profile",
            message_key="errors.external_docker.profile_clone_forbidden",
        )
    source_pp = resolve_profile_paths(host_data_dir, source_profile)
    target_pp = resolve_profile_paths(host_data_dir, target)
    if target_pp.profile_dir.exists() and not overwrite:
        raise BadRequestError(
            message=f"Profile {target} 已存在",
            message_key="errors.external_docker.profile_already_exists",
        )
    if target_pp.profile_dir.exists() and overwrite:
        shutil.rmtree(target_pp.profile_dir)
    _copy_profile_contents(
        source_pp,
        target_pp,
        include_skills=include_skills,
        include_workspace=include_workspace,
    )
    manifest = {
        "type": "hermes-profile",
        "version": "1",
        "profile": target,
        "cloned_from": source_pp.profile,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    (target_pp.profile_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )
    return ProfileCloneResponse(
        success=True,
        source_profile=source_pp.profile,
        target_profile=target,
        profile_dir=str(target_pp.profile_dir),
        message="Profile 克隆成功",
    )


def export_profile(
    host_data_dir: Path,
    profile_name: str,
    *,
    include_skills: bool = True,
    include_workspace: bool = False,
) -> ProfileExportResponse:
    pp = resolve_profile_paths(host_data_dir, profile_name)
    export_dir = profile_export_root(host_data_dir)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    export_id = f"export-{pp.profile}-{stamp}"
    file_name = f"profile-{pp.profile}.zip"
    export_file = export_dir / f"{export_id}.zip"
    manifest = {
        "type": "hermes-profile",
        "version": "1",
        "profile": pp.profile,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    with zipfile.ZipFile(export_file, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))
        for name in _CORE_FILES:
            src = pp.profile_dir / name
            if src.is_file():
                zf.writestr(name, src.read_bytes())
        if include_skills and pp.skills_dir.is_dir():
            for child in pp.skills_dir.rglob("*"):
                if child.is_file() and not any(p in _EXCLUDE_DIRS for p in child.parts):
                    arc = str(Path("skills") / child.relative_to(pp.skills_dir)).replace("\\", "/")
                    zf.write(child, arc)
        if include_workspace and pp.workspace_dir.is_dir():
            for child in pp.workspace_dir.rglob("*"):
                if child.is_file():
                    arc = str(Path("workspace") / child.relative_to(pp.workspace_dir)).replace("\\", "/")
                    zf.write(child, arc)
    return ProfileExportResponse(
        success=True,
        export_id=export_id,
        file_name=file_name,
        file_path=str(export_file),
        message="导出成功",
    )


def _safe_extract_import_zip(zf: zipfile.ZipFile, dest: Path) -> None:
    for info in zf.infolist():
        name = info.filename.replace("\\", "/")
        if name.startswith("/") or ".." in Path(name).parts:
            raise BadRequestError(
                message="导入包包含非法路径",
                message_key="errors.external_docker.profile_zip_invalid_path",
            )
    zf.extractall(dest)


def import_profile(
    host_data_dir: Path,
    zip_bytes: bytes,
    *,
    target_profile: str,
    overwrite: bool = False,
) -> ProfileImportResponse:
    target = validate_profile_name_or_raise(target_profile)
    if target == DEFAULT_PROFILE_NAME and not overwrite:
        pass
    target_pp = resolve_profile_paths(host_data_dir, target)
    if target_pp.profile_dir.exists() and not overwrite:
        raise BadRequestError(
            message=f"Profile {target} 已存在，请设置 overwrite=true",
            message_key="errors.external_docker.profile_already_exists",
        )
    temp_dir = profile_export_root(host_data_dir) / f".import-{os.urandom(4).hex()}"
    temp_dir.mkdir(parents=True)
    temp_zip = temp_dir / "upload.zip"
    try:
        temp_zip.write_bytes(zip_bytes)
        with zipfile.ZipFile(temp_zip, "r") as zf:
            try:
                manifest_raw = zf.read("manifest.json")
                manifest = json.loads(manifest_raw.decode("utf-8"))
            except (KeyError, json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise BadRequestError(
                    message="导入包缺少有效 manifest.json",
                    message_key="errors.external_docker.profile_import_invalid_manifest",
                ) from exc
            if manifest.get("type") not in ("hermes-profile", "hermes-profile-backup"):
                raise BadRequestError(
                    message="导入包类型无效",
                    message_key="errors.external_docker.profile_import_invalid_manifest",
                )
            extract_to = temp_dir / "extracted"
            extract_to.mkdir()
            _safe_extract_import_zip(zf, extract_to)
        if target_pp.profile_dir.exists() and overwrite:
            shutil.rmtree(target_pp.profile_dir)
        target_pp.profile_dir.mkdir(parents=True, exist_ok=True)
        for name in _CORE_FILES:
            src = extract_to / name
            if src.is_file():
                shutil.copy2(src, target_pp.profile_dir / name)
        skills_src = extract_to / "skills"
        if skills_src.is_dir():
            shutil.copytree(skills_src, target_pp.profile_dir / "skills", dirs_exist_ok=True)
        workspace_src = extract_to / "workspace"
        if workspace_src.is_dir():
            shutil.copytree(workspace_src, target_pp.profile_dir / "workspace", dirs_exist_ok=True)
        manifest_out = {
            "type": "hermes-profile",
            "version": "1",
            "profile": target,
            "imported_at": datetime.now(timezone.utc).isoformat(),
        }
        (target_pp.profile_dir / "manifest.json").write_text(
            json.dumps(manifest_out, indent=2),
            encoding="utf-8",
        )
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
    return ProfileImportResponse(
        success=True,
        target_profile=target,
        profile_dir=str(target_pp.profile_dir),
        message="导入成功",
    )


def resolve_export_download_path(host_data_dir: Path, export_id: str) -> Path:
    export_dir = profile_export_root(host_data_dir)
    candidate = export_dir / f"{export_id}.zip"
    if not candidate.is_file():
        raise NotFoundError(
            message=f"导出文件 {export_id} 不存在",
            message_key="errors.external_docker.profile_export_not_found",
        )
    return candidate
