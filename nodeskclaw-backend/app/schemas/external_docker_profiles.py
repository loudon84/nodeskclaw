"""External Docker Hermes profile and core file API schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ProfileListItem(BaseModel):
    profile: str
    profile_type: str
    profile_dir: str
    env_exists: bool
    config_exists: bool
    soul_exists: bool
    status: str


class ProfileListResponse(BaseModel):
    items: list[ProfileListItem] = Field(default_factory=list)


class ProfileCreateRequest(BaseModel):
    profile: str
    from_profile: str | None = None


class ProfileCreateResponse(BaseModel):
    success: bool
    profile: str
    profile_dir: str
    message: str


class ProfileDeleteResponse(BaseModel):
    success: bool
    profile: str
    message: str


class CoreFileReadResponse(BaseModel):
    profile: str
    kind: str
    file_name: str
    file_path: str
    exists: bool
    content: str = ""
    requires_restart: bool = True
    readonly: bool = False
    message: str | None = None


class CoreFileValidateRequest(BaseModel):
    content: str


class CoreFileValidateResponse(BaseModel):
    valid: bool
    message: str


class CoreFileSaveRequest(BaseModel):
    content: str
    restart_after_save: bool = False


class CoreFileSaveResponse(BaseModel):
    success: bool
    profile: str
    kind: str
    file_path: str
    backup_file: str | None = None
    restarted: bool = False
    message: str
