from datetime import datetime

from pydantic import BaseModel


class ArtifactSummary(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    org_id: str
    task_id: str | None = None
    skill_id: str | None = None
    agent_id: str | None = None
    workspace_id: str | None = None
    file_name: str
    content_type: str | None = None
    size_bytes: int | None = None
    download_count: int = 0
    permission_scope: str = "workspace"
    created_by: str | None = None
    created_at: datetime | None = None


class ArtifactDetail(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    org_id: str
    task_id: str | None = None
    skill_id: str | None = None
    agent_id: str | None = None
    workspace_id: str | None = None
    file_name: str
    file_path: str
    relative_path: str | None = None
    content_type: str | None = None
    size_bytes: int | None = None
    sha256: str | None = None
    storage_type: str = "local"
    download_count: int = 0
    permission_scope: str = "workspace"
    created_by: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ArtifactListQuery(BaseModel):
    task_id: str | None = None
    workspace_id: str | None = None
    skill_id: str | None = None
    content_type: str | None = None
    page: int = 1
    page_size: int = 20


class ArtifactPreviewResponse(BaseModel):
    artifact_id: str
    content_type: str
    content: str


class ArtifactRead(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    org_id: str
    task_id: str | None = None
    skill_id: str | None = None
    agent_id: str | None = None
    workspace_id: str | None = None
    file_name: str
    file_path: str
    relative_path: str | None = None
    content_type: str | None = None
    size_bytes: int | None = None
    sha256: str | None = None
    storage_type: str = "local"
    download_count: int = 0
    permission_scope: str = "workspace"
    created_by: str | None = None
    created_at: datetime | None = None
