"""v4.6 instance-scoped profile extended API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.security import get_current_user
from app.models.instance_member import InstanceRole
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.profile_extended import (
    ProfileActivateRequest,
    ProfileBackupCreateRequest,
    ProfileBackupDeleteRequest,
    ProfileBackupRestoreRequest,
    ProfileCloneRequest,
    ProfileExportRequest,
    ProfileFileDeleteRequest,
    ProfileFileMkdirRequest,
    ProfileFileWriteRequest,
    ProfileSkillBuiltinRequest,
    ProfileSkillGitRequest,
)
from app.services import instance_member_service
from app.services.hermes_external import (
    profile_backup_service,
    profile_file_service,
    profile_package_service,
    profile_runtime_service,
    profile_skill_service,
)
from app.services.hermes_external._common import require_external_docker_instance, resolve_paths
from app.services.hermes_skill.skill_audit_logger import SkillAuditLogger

router = APIRouter()


async def _instance(db, instance_id, user, role):
    await instance_member_service.check_instance_access(instance_id, user, role, db)
    return await require_external_docker_instance(instance_id, db, user.current_org_id)


@router.get("/{instance_id}/external-docker/profiles/{profile}/skills", response_model=ApiResponse)
async def list_skills(instance_id: str, profile: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    instance = await _instance(db, instance_id, current_user, InstanceRole.viewer)
    data = profile_skill_service.list_profile_skills(resolve_paths(instance).host_data_dir, profile)
    return ApiResponse(data=data)


@router.post("/{instance_id}/external-docker/profiles/{profile}/skills/builtin", response_model=ApiResponse)
async def install_builtin(instance_id: str, profile: str, body: ProfileSkillBuiltinRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    instance = await _instance(db, instance_id, current_user, InstanceRole.admin)
    host = resolve_paths(instance).host_data_dir
    data = profile_skill_service.install_builtin(host, profile, body.bundle)
    await SkillAuditLogger(db).log(action="profile.skill.install", target_id=f"{profile}:{body.bundle}", org_id=current_user.current_org_id or "", actor_id=current_user.id, details={"instance_id": instance_id})
    await db.commit()
    return ApiResponse(data=data)


@router.post("/{instance_id}/external-docker/profiles/{profile}/skills/upload", response_model=ApiResponse)
async def upload_skill(instance_id: str, profile: str, file: UploadFile = File(...), db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    instance = await _instance(db, instance_id, current_user, InstanceRole.admin)
    host = resolve_paths(instance).host_data_dir
    data = profile_skill_service.upload_skill_zip(host, profile, await file.read())
    await SkillAuditLogger(db).log(action="profile.skill.install", target_id=f"{profile}:upload", org_id=current_user.current_org_id or "", actor_id=current_user.id, details={"instance_id": instance_id})
    await db.commit()
    return ApiResponse(data=data)


@router.post("/{instance_id}/external-docker/profiles/{profile}/skills/git", response_model=ApiResponse)
async def git_skill(instance_id: str, profile: str, body: ProfileSkillGitRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    instance = await _instance(db, instance_id, current_user, InstanceRole.admin)
    host = resolve_paths(instance).host_data_dir
    data = await profile_skill_service.install_from_git(host, profile, repo_url=body.repo_url, ref=body.ref, subdir=body.subdir)
    await SkillAuditLogger(db).log(action="profile.skill.install", target_id=f"{profile}:git", org_id=current_user.current_org_id or "", actor_id=current_user.id, details={"instance_id": instance_id})
    await db.commit()
    return ApiResponse(data=data)


@router.post("/{instance_id}/external-docker/profiles/{profile}/skills/{skill_slug}/enable", response_model=ApiResponse)
async def enable_skill(instance_id: str, profile: str, skill_slug: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    instance = await _instance(db, instance_id, current_user, InstanceRole.admin)
    data = profile_skill_service.enable_skill(resolve_paths(instance).host_data_dir, profile, skill_slug)
    return ApiResponse(data=data)


@router.post("/{instance_id}/external-docker/profiles/{profile}/skills/{skill_slug}/disable", response_model=ApiResponse)
async def disable_skill(instance_id: str, profile: str, skill_slug: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    instance = await _instance(db, instance_id, current_user, InstanceRole.admin)
    data = profile_skill_service.disable_skill(resolve_paths(instance).host_data_dir, profile, skill_slug)
    return ApiResponse(data=data)


@router.delete("/{instance_id}/external-docker/profiles/{profile}/skills/{skill_slug}", response_model=ApiResponse)
async def delete_skill(instance_id: str, profile: str, skill_slug: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    instance = await _instance(db, instance_id, current_user, InstanceRole.admin)
    data = profile_skill_service.delete_skill(resolve_paths(instance).host_data_dir, profile, skill_slug)
    await SkillAuditLogger(db).log(action="profile.skill.delete", target_id=f"{profile}:{skill_slug}", org_id=current_user.current_org_id or "", actor_id=current_user.id, details={"instance_id": instance_id})
    await db.commit()
    return ApiResponse(data=data)


@router.get("/{instance_id}/external-docker/profiles/{profile}/files", response_model=ApiResponse)
async def list_files(instance_id: str, profile: str, scope: str = Query(default="workspace"), path: str = Query(default=""), db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    instance = await _instance(db, instance_id, current_user, InstanceRole.viewer)
    data = profile_file_service.list_profile_files(resolve_paths(instance).host_data_dir, profile, scope=scope, path=path)
    return ApiResponse(data=data)


@router.get("/{instance_id}/external-docker/profiles/{profile}/files/read", response_model=ApiResponse)
async def read_file(instance_id: str, profile: str, scope: str = Query(...), path: str = Query(...), db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    instance = await _instance(db, instance_id, current_user, InstanceRole.viewer)
    data = profile_file_service.read_profile_file(resolve_paths(instance).host_data_dir, profile, scope=scope, path=path)
    return ApiResponse(data=data)


@router.put("/{instance_id}/external-docker/profiles/{profile}/files/write", response_model=ApiResponse)
async def write_file(instance_id: str, profile: str, body: ProfileFileWriteRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    instance = await _instance(db, instance_id, current_user, InstanceRole.admin)
    data = profile_file_service.write_profile_file(resolve_paths(instance).host_data_dir, profile, scope=body.scope, path=body.path, content=body.content)
    await SkillAuditLogger(db).log(action="profile.file.write", target_id=f"{profile}:{body.path}", org_id=current_user.current_org_id or "", actor_id=current_user.id, details={"instance_id": instance_id})
    await db.commit()
    return ApiResponse(data=data)


@router.post("/{instance_id}/external-docker/profiles/{profile}/files/mkdir", response_model=ApiResponse)
async def mkdir_file(instance_id: str, profile: str, body: ProfileFileMkdirRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    instance = await _instance(db, instance_id, current_user, InstanceRole.admin)
    data = profile_file_service.mkdir_profile_path(resolve_paths(instance).host_data_dir, profile, scope=body.scope, path=body.path)
    return ApiResponse(data=data)


@router.delete("/{instance_id}/external-docker/profiles/{profile}/files", response_model=ApiResponse)
async def delete_file(instance_id: str, profile: str, body: ProfileFileDeleteRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    instance = await _instance(db, instance_id, current_user, InstanceRole.admin)
    data = profile_file_service.delete_profile_path(resolve_paths(instance).host_data_dir, profile, scope=body.scope, path=body.path)
    await SkillAuditLogger(db).log(action="profile.file.delete", target_id=f"{profile}:{body.path}", org_id=current_user.current_org_id or "", actor_id=current_user.id, details={"instance_id": instance_id})
    await db.commit()
    return ApiResponse(data=data)


@router.get("/{instance_id}/external-docker/profiles/{profile}/backups", response_model=ApiResponse)
async def list_backups(instance_id: str, profile: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    instance = await _instance(db, instance_id, current_user, InstanceRole.viewer)
    data = profile_backup_service.list_profile_backups(resolve_paths(instance).host_data_dir, profile)
    return ApiResponse(data=data)


@router.post("/{instance_id}/external-docker/profiles/{profile}/backups", response_model=ApiResponse)
async def create_backup(instance_id: str, profile: str, body: ProfileBackupCreateRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    instance = await _instance(db, instance_id, current_user, InstanceRole.admin)
    data = profile_backup_service.create_profile_backup(resolve_paths(instance).host_data_dir, profile, include_workspace=body.include_workspace, include_skills=body.include_skills, note=body.note)
    await SkillAuditLogger(db).log(action="profile.backup.create", target_id=data.backup_id, org_id=current_user.current_org_id or "", actor_id=current_user.id, details={"instance_id": instance_id})
    await db.commit()
    return ApiResponse(data=data)


@router.post("/{instance_id}/external-docker/profiles/{profile}/backups/{backup_id}/restore", response_model=ApiResponse)
async def restore_backup(instance_id: str, profile: str, backup_id: str, body: ProfileBackupRestoreRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    instance = await _instance(db, instance_id, current_user, InstanceRole.admin)
    data = await profile_backup_service.restore_profile_backup_async(resolve_paths(instance).host_data_dir, profile, backup_id, restart_after_restore=body.restart_after_restore, instance=instance)
    await SkillAuditLogger(db).log(action="profile.backup.restore", target_id=backup_id, org_id=current_user.current_org_id or "", actor_id=current_user.id, details={"instance_id": instance_id})
    await db.commit()
    return ApiResponse(data=data)


@router.delete("/{instance_id}/external-docker/profiles/{profile}/backups/{backup_id}", response_model=ApiResponse)
async def delete_backup(instance_id: str, profile: str, backup_id: str, body: ProfileBackupDeleteRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    instance = await _instance(db, instance_id, current_user, InstanceRole.admin)
    data = profile_backup_service.delete_profile_backup(resolve_paths(instance).host_data_dir, profile, backup_id, confirm_backup_id=body.confirm_backup_id)
    await SkillAuditLogger(db).log(action="profile.backup.delete", target_id=backup_id, org_id=current_user.current_org_id or "", actor_id=current_user.id, details={"instance_id": instance_id})
    await db.commit()
    return ApiResponse(data=data)


@router.get("/{instance_id}/external-docker/profiles/{profile}/backups/{backup_id}/download")
async def download_backup(instance_id: str, profile: str, backup_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    instance = await _instance(db, instance_id, current_user, InstanceRole.viewer)
    path = profile_backup_service.resolve_backup_download_path(resolve_paths(instance).host_data_dir, profile, backup_id)
    return FileResponse(path, filename=path.name, media_type="application/zip")


@router.post("/{instance_id}/external-docker/profiles/{source_profile}/clone", response_model=ApiResponse)
async def clone_profile(instance_id: str, source_profile: str, body: ProfileCloneRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    instance = await _instance(db, instance_id, current_user, InstanceRole.admin)
    data = profile_package_service.clone_profile(resolve_paths(instance).host_data_dir, source_profile, target_profile=body.target_profile, include_skills=body.include_skills, include_workspace=body.include_workspace, overwrite=body.overwrite)
    await SkillAuditLogger(db).log(action="profile.clone", target_id=body.target_profile, org_id=current_user.current_org_id or "", actor_id=current_user.id, details={"instance_id": instance_id})
    await db.commit()
    return ApiResponse(data=data)


@router.post("/{instance_id}/external-docker/profiles/{profile}/export", response_model=ApiResponse)
async def export_profile(instance_id: str, profile: str, body: ProfileExportRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    instance = await _instance(db, instance_id, current_user, InstanceRole.admin)
    data = profile_package_service.export_profile(resolve_paths(instance).host_data_dir, profile, include_skills=body.include_skills, include_workspace=body.include_workspace)
    await SkillAuditLogger(db).log(action="profile.export", target_id=data.export_id, org_id=current_user.current_org_id or "", actor_id=current_user.id, details={"instance_id": instance_id})
    await db.commit()
    return ApiResponse(data=data)


@router.get("/{instance_id}/external-docker/profiles/{profile}/exports/{export_id}/download")
async def download_export(instance_id: str, profile: str, export_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    instance = await _instance(db, instance_id, current_user, InstanceRole.viewer)
    path = profile_package_service.resolve_export_download_path(resolve_paths(instance).host_data_dir, export_id)
    return FileResponse(path, filename=f"profile-{profile}.zip", media_type="application/zip")


@router.post("/{instance_id}/external-docker/profiles/import", response_model=ApiResponse)
async def import_profile(instance_id: str, file: UploadFile = File(...), target_profile: str = Query(...), overwrite: bool = Query(default=False), db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    instance = await _instance(db, instance_id, current_user, InstanceRole.admin)
    data = profile_package_service.import_profile(resolve_paths(instance).host_data_dir, await file.read(), target_profile=target_profile, overwrite=overwrite)
    await SkillAuditLogger(db).log(action="profile.import", target_id=target_profile, org_id=current_user.current_org_id or "", actor_id=current_user.id, details={"instance_id": instance_id})
    await db.commit()
    return ApiResponse(data=data)


@router.post("/{instance_id}/external-docker/profiles/{profile}/activate", response_model=ApiResponse)
async def activate_profile(instance_id: str, profile: str, body: ProfileActivateRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    instance = await _instance(db, instance_id, current_user, InstanceRole.admin)
    data = await profile_runtime_service.activate_profile_for_instance(instance, profile, restart_after_activate=body.restart_after_activate)
    await SkillAuditLogger(db).log(action="profile.activate", target_id=profile, org_id=current_user.current_org_id or "", actor_id=current_user.id, details={"instance_id": instance_id})
    await db.commit()
    return ApiResponse(data=data)
