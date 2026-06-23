from pydantic import BaseModel


class ArtifactRescanRequest(BaseModel):
    force: bool = False


class ArtifactRescanItem(BaseModel):
    id: str
    filename: str
    artifact_type: str | None = None
    mime_type: str | None = None
    relative_path: str | None = None
    size_bytes: int | None = None


class ArtifactRescanResponse(BaseModel):
    task_id: str
    artifact_count: int
    artifacts: list[ArtifactRescanItem]
    warning: str | None = None
