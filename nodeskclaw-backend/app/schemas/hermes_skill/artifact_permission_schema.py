from datetime import datetime

from pydantic import BaseModel


class ArtifactPermissionDetail(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    artifact_id: str
    user_id: str
    granted_by: str | None = None
    permission_level: str = "viewer"
    granted_at: datetime | None = None
    revoked_at: datetime | None = None


class ArtifactPermissionGrantRequest(BaseModel):
    user_id: str
    permission_level: str = "viewer"


class ArtifactPermissionRevokeRequest(BaseModel):
    user_id: str


class ArtifactScopeChangeRequest(BaseModel):
    permission_scope: str
