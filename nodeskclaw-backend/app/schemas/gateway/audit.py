from datetime import datetime

from pydantic import BaseModel, Field


class AuditLogRead(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    request_id: str
    caller_user_id: str | None
    caller_org_id: str | None
    instance_id: str | None
    mcp_server_id: str | None
    method: str
    tool_name: str | None
    request_params_hash: str | None
    response_status: str
    duration_ms: int | None
    error_code: int | None
    policy_id: str | None
    is_default_policy: bool
    created_at: datetime


class AuditLogList(BaseModel):
    items: list[AuditLogRead]
    total: int


class AuditLogFilter(BaseModel):
    instance_id: str | None = None
    caller_user_id: str | None = None
    method: str | None = None
    tool_name: str | None = None
    response_status: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    page: int = Field(default=1, gt=0)
    page_size: int = Field(default=20, gt=0, le=100)
