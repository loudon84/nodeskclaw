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


class AttachExistingInstanceRequest(BaseModel):
    cluster_id: str
    runtime: str = "hermes-webui-expert"
    name: str = Field(..., min_length=1, max_length=128)
    slug: str
    profile: str
    container_name: str
    host_port: int = Field(..., ge=1, le=65535)
    image: str | None = None
    data_dir: str
    compose_path: str | None = None


class AttachExistingInstanceResponse(BaseModel):
    instance_id: str
