"""Per-profile Hermes backup service."""

from __future__ import annotations

import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from app.core.exceptions import BadRequestError, NotFoundError
from app.models.instance import Instance
from app.schemas.profile_extended import (
    ProfileBackupCreateResponse,
    ProfileBackupDeleteResponse,
    ProfileBackupItem,
    ProfileBackupListResponse,
    ProfileBackupManifest,
    ProfileBackupRestoreResponse,
)
from app.services.hermes_external._common import resolve_paths
from app.services.hermes_external._profile_helpers import profile_backup_root, resolve_profile_paths
from app.services.hermes_external.path_resolver import HermesExternalPathResolver

_path_resolver = HermesExternalPathResolver()
_CORE_FILES = (".env", "config.yaml", "SOUL.md")
_EXCLUDE_DIRS = {"backups", "sessions", "logs", "cache"}


def _host_data_dir(instance: Instance) -> Path:
    ep = resolve_paths(instance)
    _path_resolver.validate_host_data_dir(ep)
    return ep.host_data_dir


def _backup_id_from_name(file_name: str) -> str:
    if file_name.endswith(".zip"):
        return file_name[:-4]
    return file_name


def _list_backup_files(backup_dir: Path) -> list[Path]:
    if not backup_dir.is_dir():
        return []
    return sorted(backup_dir.glob("profile-*.zip"), reverse=True)


def _read_manifest_from_zip(zf: zipfile.ZipFile) -> ProfileBackupManifest | None:
    try:
        raw = zf.read("manifest.json")
        data = json.loads(raw.decode("utf-8"))
        return ProfileBackupManifest(profile=data.get("profile", ""), version=str(data.get("version", "1")))
    except (KeyError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def list_profile_backups(host_data_dir: Path, profile_name: str) -> ProfileBackupListResponse:
    pp = resolve_profile_paths(host_data_dir, profile_name)
    backup_dir = profile_backup_root(pp, host_data_dir)
    items: list[ProfileBackupItem] = []
    for entry in _list_backup_files(backup_dir):
        stat = entry.stat()
        backup_id = _backup_id_from_name(entry.name)
        manifest = None
        try:
            with zipfile.ZipFile(entry, "r") as zf:
                manifest = _read_manifest_from_zip(zf)
        except (OSError, zipfile.BadZipFile):
            pass
        items.append(
            ProfileBackupItem(
                backup_id=backup_id,
                file_name=entry.name,
                size=stat.st_size,
                created_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
                manifest=manifest,
            )
        )
    return ProfileBackupListResponse(profile=pp.profile, items=items)


def create_profile_backup(
    host_data_dir: Path,
    profile_name: str,
    *,
    include_workspace: bool = True,
    include_skills: bool = True,
    note: str | None = None,
) -> ProfileBackupCreateResponse:
    pp = resolve_profile_paths(host_data_dir, profile_name)
    backup_dir = profile_backup_root(pp, host_data_dir)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    backup_id = f"profile-{pp.profile}-{stamp}"
    backup_file = backup_dir / f"{backup_id}.zip"
    manifest = {
        "type": "hermes-profile-backup",
        "version": "1",
        "profile": pp.profile,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "note": note,
        "include_workspace": include_workspace,
        "include_skills": include_skills,
    }
    with zipfile.ZipFile(backup_file, "w", zipfile.ZIP_DEFLATED) as zf:
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
    return ProfileBackupCreateResponse(
        success=True,
        backup_id=backup_id,
        file_path=str(backup_file),
        message="备份已创建",
    )


def _resolve_backup_file(backup_dir: Path, backup_id: str) -> Path:
    candidate = backup_dir / f"{backup_id}.zip"
    if not candidate.is_file():
        raise NotFoundError(
            message=f"备份 {backup_id} 不存在",
            message_key="errors.external_docker.profile_backup_not_found",
        )
    return candidate


def _normalize_zip_entry(name: str) -> str:
    n = name.replace("\\", "/")
    if n.startswith("./"):
        return n[2:]
    return n

def _safe_extract_profile_zip(zf: zipfile.ZipFile, dest: Path) -> None:
    dest = dest.resolve()
    for info in zf.infolist():
        name = info.filename.replace("\\", "/")
        if name.startswith("/") or ".." in Path(name).parts:
            raise BadRequestError(
                message="备份包包含非法路径",
                message_key="errors.external_docker.profile_zip_invalid_path",
            )
    zf.extractall(dest)


def restore_profile_backup(
    host_data_dir: Path,
    profile_name: str,
    backup_id: str,
    *,
    restart_after_restore: bool = False,
    instance: Instance | None = None,
    container_name: str | None = None,
    gateway_url: str | None = None,
) -> ProfileBackupRestoreResponse:
    import asyncio
    return asyncio.get_event_loop().run_until_complete(
        restore_profile_backup_async(
            host_data_dir,
            profile_name,
            backup_id,
            restart_after_restore=restart_after_restore,
            instance=instance,
            container_name=container_name,
            gateway_url=gateway_url,
        )
    )


async def restore_profile_backup_async(
    host_data_dir: Path,
    profile_name: str,
    backup_id: str,
    *,
    restart_after_restore: bool = False,
    instance: Instance | None = None,
    container_name: str | None = None,
    gateway_url: str | None = None,
) -> ProfileBackupRestoreResponse:
    pp = resolve_profile_paths(host_data_dir, profile_name)
    backup_dir = profile_backup_root(pp, host_data_dir)
    backup_file = _resolve_backup_file(backup_dir, backup_id)
    create_profile_backup(host_data_dir, profile_name, note="pre-restore auto backup")

    temp_dir = backup_dir / f".restore-{backup_id}"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True)
    try:
        with zipfile.ZipFile(backup_file, "r") as zf:
            manifest = _read_manifest_from_zip(zf)
            if manifest and manifest.profile and manifest.profile != pp.profile:
                raise BadRequestError(
                    message="备份 manifest 与目标 Profile 不匹配",
                    message_key="errors.external_docker.profile_backup_manifest_mismatch",
                )
            name_map = {_normalize_zip_entry(n): n for n in zf.namelist()}
            for name in _CORE_FILES:
                zip_name = name_map.get(name)
                if not zip_name:
                    continue
                target = pp.profile_dir / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(zf.read(zip_name))
            _safe_extract_profile_zip(zf, temp_dir)
        skills_src = temp_dir / "skills"
        if skills_src.is_dir():
            if pp.skills_dir.exists():
                shutil.rmtree(pp.skills_dir)
            shutil.copytree(skills_src, pp.skills_dir)
        workspace_src = temp_dir / "workspace"
        if workspace_src.is_dir():
            if pp.workspace_dir.exists():
                shutil.rmtree(pp.workspace_dir)
            shutil.copytree(workspace_src, pp.workspace_dir)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    restarted = False
    runtime_status = None
    if restart_after_restore:
        from app.services.hermes_external import lifecycle_service
        from app.services.hermes_external.runtime_recovery_service import wait_for_runtime_recovery
        if instance is not None:
            await lifecycle_service.restart(instance)
            ep = resolve_paths(instance)
            container_name = ep.container_name
            if not gateway_url and instance.advanced_config:
                import json
                try:
                    cfg = json.loads(instance.advanced_config) if isinstance(instance.advanced_config, str) else instance.advanced_config
                    webui = cfg.get("webui") or {}
                    from app.services.docker_constants import get_docker_public_url
                    if webui.get("port"):
                        gateway_url = get_docker_public_url(int(webui["port"]))
                except (json.JSONDecodeError, TypeError, ValueError):
                    pass
        elif container_name:
            await lifecycle_service.restart_container(container_name)
        restarted = True
        recovery = await wait_for_runtime_recovery(
            container_name=container_name or "",
            gateway_url=gateway_url,
            env_file=pp.env_file,
        )
        runtime_status = recovery.runtime_status

    return ProfileBackupRestoreResponse(
        success=True,
        profile=pp.profile,
        backup_id=backup_id,
        restarted=restarted,
        runtime_status=runtime_status,
        message="备份已恢复",
    )


def delete_profile_backup(
    host_data_dir: Path,
    profile_name: str,
    backup_id: str,
    *,
    confirm_backup_id: str,
) -> ProfileBackupDeleteResponse:
    if confirm_backup_id != backup_id:
        raise BadRequestError(
            message="确认 ID 不匹配，已取消删除",
            message_key="errors.external_docker.profile_backup_confirm_mismatch",
        )
    pp = resolve_profile_paths(host_data_dir, profile_name)
    backup_dir = profile_backup_root(pp, host_data_dir)
    backup_file = _resolve_backup_file(backup_dir, backup_id)
    backup_file.unlink()
    return ProfileBackupDeleteResponse(success=True, backup_id=backup_id, message="备份已删除")


def resolve_backup_download_path(host_data_dir: Path, profile_name: str, backup_id: str) -> Path:
    pp = resolve_profile_paths(host_data_dir, profile_name)
    backup_dir = profile_backup_root(pp, host_data_dir)
    return _resolve_backup_file(backup_dir, backup_id)


def list_profile_backups_instance(instance: Instance, profile_name: str) -> ProfileBackupListResponse:
    return list_profile_backups(_host_data_dir(instance), profile_name)
