"""Extended Hermes profile schemas for v4.6."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ProfileSkillItem(BaseModel):
    slug: str
    name: str
    path: str
    enabled: bool = True
    has_skill_md: bool = False
    source: str = "profile"
    updated_at: datetime | None = None


class ProfileSkillsResponse(BaseModel):
    profile: str
    skills_dir: str
    items: list[ProfileSkillItem] = Field(default_factory=list)


class ProfileSkillBuiltinRequest(BaseModel):
    bundle: str


class ProfileSkillGitRequest(BaseModel):
    repo_url: str
    ref: str = "main"
    subdir: str | None = None


class ProfileSkillActionResponse(BaseModel):
    success: bool
    message: str
    skill_slug: str | None = None
    installed_path: str | None = None


class ProfileFileItem(BaseModel):
    name: str
    type: str
    size: int = 0
    updated_at: datetime | None = None
    path: str = ""


class ProfileFilesResponse(BaseModel):
    profile: str
    scope: str
    base_path: str
    path: str = ""
    items: list[ProfileFileItem] = Field(default_factory=list)


class ProfileFileReadResponse(BaseModel):
    profile: str
    scope: str
    path: str
    file_path: str
    exists: bool
    content: str = ""
    binary: bool = False
    message: str | None = None


class ProfileFileWriteRequest(BaseModel):
    scope: str
    path: str
    content: str


class ProfileFileMkdirRequest(BaseModel):
    scope: str
    path: str


class ProfileFileDeleteRequest(BaseModel):
    scope: str
    path: str


class ProfileFileActionResponse(BaseModel):
    success: bool
    message: str
    backup_file: str | None = None


class ProfileBackupManifest(BaseModel):
    profile: str
    version: str = "1"


class ProfileBackupItem(BaseModel):
    backup_id: str
    file_name: str
    size: int
    created_at: datetime
    note: str | None = None
    manifest: ProfileBackupManifest | None = None


class ProfileBackupListResponse(BaseModel):
    profile: str
    items: list[ProfileBackupItem] = Field(default_factory=list)


class ProfileBackupCreateRequest(BaseModel):
    include_workspace: bool = True
    include_skills: bool = True
    note: str | None = None


class ProfileBackupCreateResponse(BaseModel):
    success: bool
    backup_id: str
    file_path: str
    message: str


class ProfileBackupRestoreRequest(BaseModel):
    restart_after_restore: bool = False


class ProfileBackupRestoreResponse(BaseModel):
    success: bool
    profile: str
    backup_id: str
    restarted: bool = False
    runtime_status: str | None = None
    message: str


class ProfileBackupDeleteRequest(BaseModel):
    confirm_backup_id: str


class ProfileBackupDeleteResponse(BaseModel):
    success: bool
    backup_id: str
    message: str


class ProfileCloneRequest(BaseModel):
    target_profile: str
    include_skills: bool = True
    include_workspace: bool = False
    overwrite: bool = False


class ProfileCloneResponse(BaseModel):
    success: bool
    source_profile: str
    target_profile: str
    profile_dir: str
    message: str


class ProfileExportRequest(BaseModel):
    include_skills: bool = True
    include_workspace: bool = False


class ProfileExportResponse(BaseModel):
    success: bool
    export_id: str
    file_name: str
    file_path: str
    message: str


class ProfileImportResponse(BaseModel):
    success: bool
    target_profile: str
    profile_dir: str
    message: str


class ProfileActivateRequest(BaseModel):
    restart_after_activate: bool = True


class ProfileActivateResponse(BaseModel):
    success: bool
    active_profile: str
    previous_active_profile: str | None = None
    restarted: bool = False
    runtime_status: str | None = None
    api_server_status: str | None = None
    message: str
