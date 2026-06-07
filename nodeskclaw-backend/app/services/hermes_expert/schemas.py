"""Pydantic schemas for Hermes expert API."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.llm import LlmConfigItem


class ExpertTemplateInfo(BaseModel):
    slug: str
    name: str
    description: str
    version: str = "0.1.0"
    files: list[str] = Field(default_factory=list)


class CreateExpertInstanceRequest(BaseModel):
    name: str
    profile: str
    expert_template: str
    cluster_id: str
    org_id: str | None = None
    image_version: str | None = "latest"
    webui_port: int | None = None
    hindsight_api_url: str | None = None
    hindsight_bank_id: str | None = None
    env_vars: dict[str, str] = Field(default_factory=dict)
    llm_configs: list[LlmConfigItem] | None = None
    init_obsidian_vault: bool = True
    install_default_skills: bool = True
    default_skill_bundle: str | None = None


class CreateExpertInstanceResponse(BaseModel):
    instance_id: str
    deploy_id: str
    profile: str
    webui_url: str
    webui_password: str | None = None
    status: str = "deploying"


class ExpertInstanceInfo(BaseModel):
    instance_id: str
    name: str
    profile: str
    expert: str
    expert_template: str
    runtime: str
    status: str
    display_status: str | None = None
    webui_url: str | None = None
    webui_port: int | None = None
    hindsight_bank_id: str | None = None
    cluster_id: str
    created_at: datetime


class ExpertSkillInfo(BaseModel):
    slug: str
    name: str
    version: str
    description: str = ""
    enabled: bool = True
    status: str = "installed"
    source: str = "builtin"
    requires_restart: bool = False
    installed_at: str | None = None
    files: list[str] = Field(default_factory=list)


class InstallBuiltinSkillRequest(BaseModel):
    bundle: str


class InstallGitSkillRequest(BaseModel):
    repo: str
    ref: str = "main"
    skill_slug: str | None = None


class ExpertHealthInfo(BaseModel):
    healthy: bool | None = None
    detail: str = ""
    webui_url: str | None = None
