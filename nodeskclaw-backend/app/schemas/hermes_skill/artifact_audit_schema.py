from datetime import datetime

from pydantic import BaseModel


class ArtifactAuditLogItem(BaseModel):
    id: str
    action: str
    target_id: str
    actor_id: str
    actor_name: str | None = None
    details: dict | None = None
    created_at: datetime | None = None


class ArtifactAuditLogQuery(BaseModel):
    action: str | None = None
    actor_id: str | None = None
    target_id: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    page: int = 1
    page_size: int = 20
