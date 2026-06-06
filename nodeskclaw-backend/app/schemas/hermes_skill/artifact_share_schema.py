from datetime import datetime

from pydantic import BaseModel


class ArtifactShareRequest(BaseModel):
    max_uses: int = 1
    expires_hours: int = 24


class ArtifactShareResponse(BaseModel):
    token: str
    share_url: str
    expires_at: datetime
    max_uses: int


class ArtifactDownloadByTokenPath(BaseModel):
    token: str
