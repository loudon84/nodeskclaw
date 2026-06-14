from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class McpToolApprovalRequestItem(BaseModel):
    id: str
    org_id: str
    requester_user_id: str
    desktop_device_id: str | None = None
    profile_id: str | None = None
    profile_name: str | None = None
    instance_id: str | None = None
    instance_ref: str | None = None
    tool_name: str
    permission: str
    risk_level: str
    request_source: str
    request_reason: str | None = None
    arguments_summary: dict | None = None
    status: str
    requested_at: datetime
    decided_by: str | None = None
    decided_at: datetime | None = None
    decision_comment: str | None = None
    grant_id: str | None = None
    expires_at: datetime | None = None


class McpToolApprovalRequestListResponse(BaseModel):
    items: list[McpToolApprovalRequestItem]
    total: int = Field(ge=0)


class McpToolGrantItem(BaseModel):
    id: str
    org_id: str
    user_id: str
    desktop_device_id: str | None = None
    profile_id: str | None = None
    profile_name: str | None = None
    instance_id: str | None = None
    tool_name: str
    permission: str
    risk_level: str
    grant_status: str
    approved_by: str
    approved_at: datetime
    revoked_by: str | None = None
    revoked_at: datetime | None = None
    revoke_reason: str | None = None
    expires_at: datetime | None = None
    constraints_json: dict | None = None
    source_request_id: str | None = None


class McpToolGrantListResponse(BaseModel):
    items: list[McpToolGrantItem]
    total: int = Field(ge=0)


class ApproveMcpToolRequestBody(BaseModel):
    expires_at: datetime | None = None
    decision_comment: str | None = None
    constraints: dict[str, Any] | None = None


class RejectMcpToolRequestBody(BaseModel):
    decision_comment: str | None = None


class RevokeMcpToolGrantBody(BaseModel):
    reason: str | None = None
