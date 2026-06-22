"""v4.6 Hermes agent-scoped profile extended API routes."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.hermes_skill._agent_profile_context import (
    host_data_dir_context as _host_data_dir_context,
    host_dir_from_agent as _host_dir_from_agent,
    require_agent_record as _require_agent_record,
    resolve_bound_instance as _resolve_bound_instance,
)
from app.core.deps import get_db, require_org_member
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
from app.services.hermes_external import (
    profile_backup_service,
    profile_file_service,
    profile_package_service,
    profile_runtime_service,
    profile_skill_inventory_service,
    profile_skill_service,
)
from app.services.hermes_external._common import resolve_paths
from app.services.hermes_skill.permission_checker import PermissionChecker
from app.services.hermes_skill.skill_audit_logger import SkillAuditLogger

router = APIRouter()


def _ok(data=None, message: str = "success") -> dict:
    return {"code": 0, "message": message, "data": data}


@router.get("/agents/{agent_profile}/profiles/{profile}/skills")
async def list_skills(agent_profile: str, profile: str, user_org=Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_agent:view")
    host_data_dir, _, _ = await _host_dir_from_agent(db, org.id, agent_profile)
    data = profile_skill_service.list_profile_skills(host_data_dir, profile)
    return _ok(data.model_dump())


@router.get("/agents/{agent_profile}/profiles/{profile}/skills/tree")
async def list_skill_tree(
    agent_profile: str,
    profile: str,
    keyword: str | None = Query(None),
    include_builtin: bool = Query(True),
    include_local: bool = Query(True),
    include_profile: bool = Query(True),
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_agent:view")
    host_data_dir, record, _ = await _host_dir_from_agent(db, org.id, agent_profile)
    data = await profile_skill_inventory_service.list_full_skill_inventory(
        agent_profile,
        profile,
        host_data_dir,
        record.container_name,
        keyword=keyword,
        include_builtin=include_builtin,
        include_local=include_local,
        include_profile=include_profile,
    )
    return _ok(data.model_dump())


@router.post("/agents/{agent_profile}/profiles/{profile}/skills/builtin")
async def install_builtin(agent_profile: str, profile: str, body: ProfileSkillBuiltinRequest, user_org=Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_agent:manage")
    host_data_dir, record, _ = await _host_dir_from_agent(db, org.id, agent_profile)
    data = profile_skill_service.install_builtin(host_data_dir, profile, body.bundle)
    audit = SkillAuditLogger(db)
    await audit.log(action="profile.skill.install", target_id=f"{profile}:{body.bundle}", org_id=org.id, actor_id=user.id if user else "", details={"agent_profile": agent_profile, "source": "builtin"})
    await db.commit()
    return _ok(data.model_dump())


@router.post("/agents/{agent_profile}/profiles/{profile}/skills/upload")
async def upload_skill(agent_profile: str, profile: str, file: UploadFile = File(...), user_org=Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_agent:manage")
    host_data_dir, _, _ = await _host_dir_from_agent(db, org.id, agent_profile)
    content = await file.read()
    data = profile_skill_service.upload_skill_zip(host_data_dir, profile, content)
    audit = SkillAuditLogger(db)
    await audit.log(action="profile.skill.install", target_id=f"{profile}:upload", org_id=org.id, actor_id=user.id if user else "", details={"agent_profile": agent_profile, "source": "upload"})
    await db.commit()
    return _ok(data.model_dump())


@router.post("/agents/{agent_profile}/profiles/{profile}/skills/git")
async def git_skill(agent_profile: str, profile: str, body: ProfileSkillGitRequest, user_org=Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_agent:manage")
    host_data_dir, _, _ = await _host_dir_from_agent(db, org.id, agent_profile)
    data = await profile_skill_service.install_from_git(host_data_dir, profile, repo_url=body.repo_url, ref=body.ref, subdir=body.subdir)
    audit = SkillAuditLogger(db)
    await audit.log(action="profile.skill.install", target_id=f"{profile}:git", org_id=org.id, actor_id=user.id if user else "", details={"agent_profile": agent_profile, "source": "git"})
    await db.commit()
    return _ok(data.model_dump())


@router.post("/agents/{agent_profile}/profiles/{profile}/skills/{skill_slug}/enable")
async def enable_skill(agent_profile: str, profile: str, skill_slug: str, user_org=Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_agent:manage")
    host_data_dir, _, _ = await _host_dir_from_agent(db, org.id, agent_profile)
    data = profile_skill_service.enable_skill(host_data_dir, profile, skill_slug)
    return _ok(data.model_dump())


@router.post("/agents/{agent_profile}/profiles/{profile}/skills/{skill_slug}/disable")
async def disable_skill(agent_profile: str, profile: str, skill_slug: str, user_org=Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_agent:manage")
    host_data_dir, _, _ = await _host_dir_from_agent(db, org.id, agent_profile)
    data = profile_skill_service.disable_skill(host_data_dir, profile, skill_slug)
    return _ok(data.model_dump())


@router.delete("/agents/{agent_profile}/profiles/{profile}/skills/{skill_slug}")
async def delete_skill(agent_profile: str, profile: str, skill_slug: str, user_org=Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_agent:manage")
    host_data_dir, _, _ = await _host_dir_from_agent(db, org.id, agent_profile)
    data = profile_skill_service.delete_skill(host_data_dir, profile, skill_slug)
    audit = SkillAuditLogger(db)
    await audit.log(action="profile.skill.delete", target_id=f"{profile}:{skill_slug}", org_id=org.id, actor_id=user.id if user else "", details={"agent_profile": agent_profile})
    await db.commit()
    return _ok(data.model_dump())


@router.post("/agents/{agent_profile}/profiles/{profile}/skills/rescan")
async def rescan_skills(agent_profile: str, profile: str, user_org=Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_agent:manage")
    host_data_dir, _, _ = await _host_dir_from_agent(db, org.id, agent_profile)
    data = profile_skill_service.rescan_skills(host_data_dir, profile)
    return _ok(data.model_dump())


@router.get("/agents/{agent_profile}/profiles/{profile}/files")
async def list_files(agent_profile: str, profile: str, scope: str = Query(default="workspace"), path: str = Query(default=""), user_org=Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_agent:view")
    host_data_dir, _, _ = await _host_dir_from_agent(db, org.id, agent_profile)
    data = profile_file_service.list_profile_files(host_data_dir, profile, scope=scope, path=path)
    return _ok(data.model_dump())


@router.get("/agents/{agent_profile}/profiles/{profile}/files/read")
async def read_file(agent_profile: str, profile: str, scope: str = Query(...), path: str = Query(...), user_org=Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_agent:view")
    host_data_dir, _, _ = await _host_dir_from_agent(db, org.id, agent_profile)
    data = profile_file_service.read_profile_file(host_data_dir, profile, scope=scope, path=path)
    return _ok(data.model_dump())


@router.put("/agents/{agent_profile}/profiles/{profile}/files/write")
async def write_file(agent_profile: str, profile: str, body: ProfileFileWriteRequest, user_org=Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_agent:manage")
    host_data_dir, _, _ = await _host_dir_from_agent(db, org.id, agent_profile)
    data = profile_file_service.write_profile_file(host_data_dir, profile, scope=body.scope, path=body.path, content=body.content)
    audit = SkillAuditLogger(db)
    await audit.log(action="profile.file.write", target_id=f"{profile}:{body.path}", org_id=org.id, actor_id=user.id if user else "", details={"agent_profile": agent_profile, "scope": body.scope})
    await db.commit()
    return _ok(data.model_dump())


@router.post("/agents/{agent_profile}/profiles/{profile}/files/mkdir")
async def mkdir_file(agent_profile: str, profile: str, body: ProfileFileMkdirRequest, user_org=Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_agent:manage")
    host_data_dir, _, _ = await _host_dir_from_agent(db, org.id, agent_profile)
    data = profile_file_service.mkdir_profile_path(host_data_dir, profile, scope=body.scope, path=body.path)
    return _ok(data.model_dump())


@router.delete("/agents/{agent_profile}/profiles/{profile}/files")
async def delete_file(agent_profile: str, profile: str, body: ProfileFileDeleteRequest, user_org=Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_agent:manage")
    host_data_dir, _, _ = await _host_dir_from_agent(db, org.id, agent_profile)
    data = profile_file_service.delete_profile_path(host_data_dir, profile, scope=body.scope, path=body.path)
    audit = SkillAuditLogger(db)
    await audit.log(action="profile.file.delete", target_id=f"{profile}:{body.path}", org_id=org.id, actor_id=user.id if user else "", details={"agent_profile": agent_profile})
    await db.commit()
    return _ok(data.model_dump())


@router.get("/agents/{agent_profile}/profiles/{profile}/backups")
async def list_backups(agent_profile: str, profile: str, user_org=Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_agent:view")
    host_data_dir, _, _ = await _host_dir_from_agent(db, org.id, agent_profile)
    data = profile_backup_service.list_profile_backups(host_data_dir, profile)
    return _ok(data.model_dump())


@router.post("/agents/{agent_profile}/profiles/{profile}/backups")
async def create_backup(agent_profile: str, profile: str, body: ProfileBackupCreateRequest, user_org=Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_agent:manage")
    host_data_dir, _, _ = await _host_dir_from_agent(db, org.id, agent_profile)
    data = profile_backup_service.create_profile_backup(host_data_dir, profile, include_workspace=body.include_workspace, include_skills=body.include_skills, note=body.note)
    audit = SkillAuditLogger(db)
    await audit.log(action="profile.backup.create", target_id=data.backup_id, org_id=org.id, actor_id=user.id if user else "", details={"agent_profile": agent_profile, "profile": profile})
    await db.commit()
    return _ok(data.model_dump())


@router.post("/agents/{agent_profile}/profiles/{profile}/backups/{backup_id}/restore")
async def restore_backup(agent_profile: str, profile: str, backup_id: str, body: ProfileBackupRestoreRequest, user_org=Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_agent:manage")
    host_data_dir, record, instance = await _host_dir_from_agent(db, org.id, agent_profile)
    ctx = _host_data_dir_context(record, agent_profile)
    data = await profile_backup_service.restore_profile_backup_async(
        host_data_dir, profile, backup_id,
        restart_after_restore=body.restart_after_restore,
        instance=instance,
        container_name=ctx["container_name"],
        gateway_url=ctx["gateway_url"],
    )
    audit = SkillAuditLogger(db)
    await audit.log(action="profile.backup.restore", target_id=backup_id, org_id=org.id, actor_id=user.id if user else "", details={"agent_profile": agent_profile, "profile": profile})
    await db.commit()
    return _ok(data.model_dump())


@router.delete("/agents/{agent_profile}/profiles/{profile}/backups/{backup_id}")
async def delete_backup(agent_profile: str, profile: str, backup_id: str, body: ProfileBackupDeleteRequest, user_org=Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_agent:manage")
    host_data_dir, _, _ = await _host_dir_from_agent(db, org.id, agent_profile)
    data = profile_backup_service.delete_profile_backup(host_data_dir, profile, backup_id, confirm_backup_id=body.confirm_backup_id)
    audit = SkillAuditLogger(db)
    await audit.log(action="profile.backup.delete", target_id=backup_id, org_id=org.id, actor_id=user.id if user else "", details={"agent_profile": agent_profile})
    await db.commit()
    return _ok(data.model_dump())


@router.get("/agents/{agent_profile}/profiles/{profile}/backups/{backup_id}/download")
async def download_backup(agent_profile: str, profile: str, backup_id: str, user_org=Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_agent:view")
    host_data_dir, _, _ = await _host_dir_from_agent(db, org.id, agent_profile)
    path = profile_backup_service.resolve_backup_download_path(host_data_dir, profile, backup_id)
    return FileResponse(path, filename=path.name, media_type="application/zip")


@router.post("/agents/{agent_profile}/profiles/{source_profile}/clone")
async def clone_profile(agent_profile: str, source_profile: str, body: ProfileCloneRequest, user_org=Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_agent:manage")
    host_data_dir, _, _ = await _host_dir_from_agent(db, org.id, agent_profile)
    data = profile_package_service.clone_profile(host_data_dir, source_profile, target_profile=body.target_profile, include_skills=body.include_skills, include_workspace=body.include_workspace, overwrite=body.overwrite)
    audit = SkillAuditLogger(db)
    await audit.log(action="profile.clone", target_id=body.target_profile, org_id=org.id, actor_id=user.id if user else "", details={"agent_profile": agent_profile, "source": source_profile})
    await db.commit()
    return _ok(data.model_dump())


@router.post("/agents/{agent_profile}/profiles/{profile}/export")
async def export_profile(agent_profile: str, profile: str, body: ProfileExportRequest, user_org=Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_agent:manage")
    host_data_dir, _, _ = await _host_dir_from_agent(db, org.id, agent_profile)
    data = profile_package_service.export_profile(host_data_dir, profile, include_skills=body.include_skills, include_workspace=body.include_workspace)
    audit = SkillAuditLogger(db)
    await audit.log(action="profile.export", target_id=data.export_id, org_id=org.id, actor_id=user.id if user else "", details={"agent_profile": agent_profile, "profile": profile})
    await db.commit()
    return _ok(data.model_dump())


@router.get("/agents/{agent_profile}/profiles/{profile}/exports/{export_id}/download")
async def download_export(agent_profile: str, profile: str, export_id: str, user_org=Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_agent:view")
    host_data_dir, _, _ = await _host_dir_from_agent(db, org.id, agent_profile)
    path = profile_package_service.resolve_export_download_path(host_data_dir, export_id)
    return FileResponse(path, filename=f"profile-{profile}.zip", media_type="application/zip")


@router.post("/agents/{agent_profile}/profiles/import")
async def import_profile(agent_profile: str, file: UploadFile = File(...), target_profile: str = Query(...), overwrite: bool = Query(default=False), user_org=Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_agent:manage")
    host_data_dir, _, _ = await _host_dir_from_agent(db, org.id, agent_profile)
    content = await file.read()
    data = profile_package_service.import_profile(host_data_dir, content, target_profile=target_profile, overwrite=overwrite)
    audit = SkillAuditLogger(db)
    await audit.log(action="profile.import", target_id=target_profile, org_id=org.id, actor_id=user.id if user else "", details={"agent_profile": agent_profile})
    await db.commit()
    return _ok(data.model_dump())


@router.post("/agents/{agent_profile}/profiles/{profile}/activate")
async def activate_profile(agent_profile: str, profile: str, body: ProfileActivateRequest, user_org=Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_agent:manage")
    host_data_dir, record, instance = await _host_dir_from_agent(db, org.id, agent_profile)
    ctx = _host_data_dir_context(record, agent_profile)
    if instance is not None:
        data = await profile_runtime_service.activate_profile_for_instance(instance, profile, restart_after_activate=body.restart_after_activate)
    else:
        data = await profile_runtime_service.activate_profile(
            host_data_dir, profile,
            restart_after_activate=body.restart_after_activate,
            container_name=ctx["container_name"],
            gateway_url=ctx["gateway_url"],
        )
    audit = SkillAuditLogger(db)
    await audit.log(action="profile.activate", target_id=profile, org_id=org.id, actor_id=user.id if user else "", details={"agent_profile": agent_profile, "runtime_status": data.runtime_status})
    await db.commit()
    return _ok(data.model_dump())
