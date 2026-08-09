"""Connector API schemas — secrets never appear in Out models."""

from typing import Any

from pydantic import BaseModel, Field


class ConnectorCreate(BaseModel):
    name: str
    connector_type: str
    config: dict[str, Any] = Field(default_factory=dict)
    sync_mode: str = "manual"
    sync_interval_seconds: int | None = None


class ConnectorUpdate(BaseModel):
    name: str | None = None
    config: dict[str, Any] | None = None
    sync_mode: str | None = None
    sync_interval_seconds: int | None = None
    status: str | None = None


class ConnectorOut(BaseModel):
    id: str
    org_id: str
    knowledge_base_id: str
    name: str
    connector_type: str
    status: str
    config: dict[str, Any] = Field(default_factory=dict)
    owner_member_id: str
    sync_mode: str
    sync_interval_seconds: int | None = None
    sync_cursor: dict[str, Any] | None = None
    last_sync_started_at: Any = None
    last_sync_succeeded_at: Any = None
    next_sync_at: Any = None
    last_error_code: str | None = None
    last_error: str | None = None
    credential_configured: bool = False
    credential_updated_at: Any = None
    created_at: Any = None
    updated_at: Any = None

    model_config = {"from_attributes": True}


class ConnectorCredentialPut(BaseModel):
    payload: dict[str, Any]


class ConnectorSourceObjectOut(BaseModel):
    id: str
    connector_id: str
    external_object_id: str
    source_file_id: str | None = None
    canonical_uri: str | None = None
    display_path: str | None = None
    external_revision: str | None = None
    etag: str | None = None
    source_modified_at: Any = None
    source_metadata: dict[str, Any] = Field(default_factory=dict)
    state: str
    last_seen_sync_run_id: str | None = None
    last_seen_at: Any = None
    last_synced_at: Any = None
    last_content_sha256: str | None = None
    last_error: str | None = None
    created_at: Any = None
    updated_at: Any = None

    model_config = {"from_attributes": True}


class ConnectorSyncRunOut(BaseModel):
    id: str
    connector_id: str
    status: str
    metrics: dict[str, Any] = Field(default_factory=dict)
    attempt_count: int = 0
    max_attempts: int = 5
    next_run_at: Any = None
    trigger: str
    cursor_before: dict[str, Any] | None = None
    cursor_after: dict[str, Any] | None = None
    error_code: str | None = None
    error_message: str | None = None
    started_at: Any = None
    finished_at: Any = None
    created_by_member_id: str | None = None
    created_at: Any = None
    updated_at: Any = None

    model_config = {"from_attributes": True}


class ConnectorSyncItemOut(BaseModel):
    id: str
    sync_run_id: str
    source_object_id: str | None = None
    source_file_id: str | None = None
    action: str
    status: str
    ingestion_job_id: str | None = None
    error: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: Any = None
    updated_at: Any = None

    model_config = {"from_attributes": True}


class ConnectorSyncCreate(BaseModel):
    trigger: str = "manual"
