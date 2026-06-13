"""External Docker Hermes instance API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ExternalDockerOverviewResponse(BaseModel):
    binding_type: str = "external_docker"
    binding_type_label: str = ""
    profile: str = ""
    container_name: str = ""
    lifecycle_mode: str = ""
    public_url: str | None = None
    docker_env_file: str = ""
    host_data_dir: str = ""
    container_data_dir: str = ""
    compose_path: str | None = None
    compose_project: str | None = None
    service_name: str | None = None


class ExternalDockerStatusResponse(BaseModel):
    container_name: str = ""
    container_id: str | None = None
    image: str | None = None
    docker_status: str = "unknown"
    docker_health: str | None = None
    webui_health: str = "unknown"
    display_status: str = "unknown"
    public_url: str | None = None
    started_at: datetime | None = None
    last_checked_at: datetime = Field(default_factory=datetime.utcnow)
    last_error: str | None = None


class ExternalDockerWebuiAccessResponse(BaseModel):
    public_url: str | None = None
    username: str | None = None
    password_available: bool = False
    password_masked: str = "************"


class ExternalDockerWebuiPasswordResponse(BaseModel):
    password: str = ""


class ExternalDockerModelConfigResponse(BaseModel):
    config_file: str = ""
    exists: bool = False
    providers: list[dict[str, Any]] = Field(default_factory=list)
    masked: bool = True
    message: str | None = None


class ExternalDockerSkillItem(BaseModel):
    name: str
    path: str
    kind: str
    category: str


class ExternalDockerSkillsResponse(BaseModel):
    skills_dir: str = ""
    skill_inbox_dir: str = ""
    tools_dir: str = ""
    plugins_dir: str = ""
    items: list[ExternalDockerSkillItem] = Field(default_factory=list)


class ExternalDockerFileItem(BaseModel):
    name: str
    path: str
    is_dir: bool
    size: int | None = None
    modified_at: datetime | None = None


class ExternalDockerFilesResponse(BaseModel):
    root: str = ""
    scope: str = "workspace"
    path: str = ""
    exists: bool = True
    items: list[ExternalDockerFileItem] = Field(default_factory=list)


class ExternalDockerBackupItem(BaseModel):
    name: str
    path: str
    size: int
    created_at: datetime


class ExternalDockerBackupsResponse(BaseModel):
    backup_dir: str = ""
    items: list[ExternalDockerBackupItem] = Field(default_factory=list)


class ExternalDockerCreateBackupResponse(BaseModel):
    success: bool = True
    backup_file: str = ""
    include_docker_env: bool = False


class ExternalDockerLifecycleResponse(BaseModel):
    success: bool = True
    action: str = ""
    message: str = ""


class ExternalDockerLogsResponse(BaseModel):
    container_name: str = ""
    logs: str = ""


class ExternalDockerDetachResponse(BaseModel):
    success: bool = True
    instance_id: str = ""
