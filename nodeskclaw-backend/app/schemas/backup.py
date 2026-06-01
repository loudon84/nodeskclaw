"""Backup-related request/response schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class BackupInfo(BaseModel):
    id: str
    instance_id: str
    type: str
    status: str
    config_snapshot: str | None = None
    storage_key: str | None = None
    data_size: int | None = None
    message: str | None = None
    triggered_by: str
    org_id: str | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RestoreRequest(BaseModel):
    backup_id: str


class CloneRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    cluster_id: str | None = None


class CloneResponse(BaseModel):
    instance_id: str
    deploy_id: str
