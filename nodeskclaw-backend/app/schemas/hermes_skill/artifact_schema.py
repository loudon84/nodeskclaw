from datetime import datetime

from pydantic import BaseModel


class ArtifactSummary(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    task_id: str | None = None
    skill_id: str | None = None
    agent_id: str | None = None
    workspace_id: str | None = None
    file_name: str
    relative_path: str | None = None
    content_type: str | None = None
    size_bytes: int | None = None
    download_count: int = 0
    permission_scope: str = "workspace"
    preview_supported: bool = False
    created_by: str | None = None
    created_at: datetime | None = None
    download_url: str | None = None
    preview_url: str | None = None


class ArtifactDetail(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    org_id: str
    task_id: str | None = None
    skill_id: str | None = None
    agent_id: str | None = None
    workspace_id: str | None = None
    file_name: str
    relative_path: str | None = None
    content_type: str | None = None
    size_bytes: int | None = None
    sha256: str | None = None
    storage_type: str = "local"
    download_count: int = 0
    permission_scope: str = "workspace"
    preview_supported: bool = False
    source_run_id: str | None = None
    created_by: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ArtifactDetailAdmin(ArtifactDetail):
    file_path: str | None = None


class ArtifactListQuery(BaseModel):
    task_id: str | None = None
    workspace_id: str | None = None
    skill_id: str | None = None
    content_type: str | None = None
    page: int = 1
    page_size: int = 20


class ArtifactPreviewResponse(BaseModel):
    artifact_id: str
    file_name: str | None = None
    content_type: str
    preview_type: str = "text"
    content: str
    truncated: bool = False
    size_bytes: int | None = None


class ArtifactRead(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    org_id: str
    task_id: str | None = None
    skill_id: str | None = None
    agent_id: str | None = None
    workspace_id: str | None = None
    file_name: str
    relative_path: str | None = None
    content_type: str | None = None
    size_bytes: int | None = None
    sha256: str | None = None
    storage_type: str = "local"
    download_count: int = 0
    permission_scope: str = "workspace"
    preview_supported: bool = False
    created_by: str | None = None
    created_at: datetime | None = None
