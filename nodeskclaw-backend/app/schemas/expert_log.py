from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ExpertInvocationLogItem(BaseModel):
    id: str
    org_id: str
    user_id: str | None = None
    expert_id: str | None = None
    expert_skill_id: str | None = None
    expert_team_id: str | None = None
    expert_slug: str | None = None
    skill_name: str | None = None
    upstream_tool_name: str | None = None
    agent_alias: str | None = None
    request_id: str | None = None
    jsonrpc_id: str | None = None
    status: str
    request_prompt_preview: str | None = None
    response_preview: str | None = None
    response_content_type: str | None = None
    response_size_bytes: int | None = None
    error_code: str | None = None
    error_message: str | None = None
    started_at: datetime
    finished_at: datetime | None = None
    duration_ms: int | None = None
    client_source: str | None = None
    client_version: str | None = None
    client_device_id: str | None = None
    parent_invocation_id: str | None = None
    invocation_type: str
    created_at: datetime | None = None


class ExpertInvocationLogDetail(ExpertInvocationLogItem):
    request_payload: dict[str, Any] | None = None
    error_detail: dict[str, Any] | None = None


class ExpertInvocationLogListResponse(BaseModel):
    items: list[ExpertInvocationLogItem]
    total: int
