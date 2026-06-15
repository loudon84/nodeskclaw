from datetime import datetime

from pydantic import BaseModel, Field


class InstallationCreate(BaseModel):
    skill_id: str
    agent_id: str
    profile_id: str | None = None
    workspace_id: str | None = None
    install_mode: str = "copy"
    conflict_strategy: str = "install_as_new_version"


class InstallationRead(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    org_id: str
    skill_id: str
    agent_id: str
    profile_id: str | None = None
    workspace_id: str | None = None
    install_mode: str = "copy"
    installed_path: str | None = None
    installed_version: str | None = None
    status: str = "pending"
    error_message: str | None = None
    installed_by: str | None = None
    profile_root_path: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class InstallationFilterParams(BaseModel):
    skill_id: str | None = None
    agent_id: str | None = None
    status: str | None = None
    page: int = Field(default=1, gt=0)
    page_size: int = Field(default=20, gt=0, le=100)


class InstallationListResult(BaseModel):
    items: list[InstallationRead]
    total: int
    page: int
    page_size: int
