from datetime import datetime

from pydantic import BaseModel


class TaskRead(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    org_id: str
    task_no: str
    skill_id: str | None = None
    tool_name: str | None = None
    agent_id: str | None = None
    profile_id: str | None = None
    workspace_id: str | None = None
    installation_id: str | None = None
    user_id: str | None = None
    status: str = "queued"
    arguments: dict | None = None
    arguments_hash: str | None = None
    request_summary: str | None = None
    result_summary: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    hermes_run_id: str | None = None
    event_url: str | None = None
    artifact_url: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TaskListResult(BaseModel):
    items: list[TaskRead]
    total: int
    page: int
    page_size: int
