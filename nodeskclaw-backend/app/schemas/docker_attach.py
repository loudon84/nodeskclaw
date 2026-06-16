"""Schemas for Docker container attach (bind existing container)."""

from pydantic import BaseModel, Field


class AttachableContainerInfo(BaseModel):
    profile: str
    container_name: str
    image: str | None = None
    status: str
    health_status: str | None = None
    host_port: int | None = None
    container_port: int | None = None
    data_dir: str
    compose_path: str | None = None
    already_attached: bool = False
    matched_instance_id: str | None = None
    created_at: str | None = None
    public_url: str | None = None
    health_url: str | None = None
    gateway_port: int | None = None
    gateway_url: str | None = None
    gateway_status: str | None = None
    runtime_status: str | None = None
    mcp_status: str | None = None
    last_probe_at: str | None = None
    last_error: str | None = None
    instance_root: str | None = None
    host_data_dir: str | None = None
    container_data_dir: str | None = None
    env_file: str | None = None
    compose_project: str | None = None
    lifecycle_mode: str | None = None
    attachable: bool = True
    warnings: list[str] = Field(default_factory=list)


class AttachExistingInstanceRequest(BaseModel):
    cluster_id: str
    runtime: str = "hermes-webui-expert"
    name: str = Field(..., min_length=1, max_length=128)
    slug: str | None = None
    profile: str | None = None
    container_name: str
    host_port: int | None = Field(default=None, ge=1, le=65535)
    image: str | None = None
    data_dir: str | None = None
    compose_path: str | None = None
    lifecycle_mode: str = "managed_compose"
    display_name: str | None = None


class AttachExistingInstanceResponse(BaseModel):
    instance_id: str
