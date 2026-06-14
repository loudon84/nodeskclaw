from datetime import datetime

from pydantic import BaseModel, Field


class McpCallLogItem(BaseModel):
    id: str
    tool_name: str
    permission: str | None = None
    risk_level: str | None = None
    instance_id: str | None = None
    status: str
    duration_ms: int | None = None
    created_at: datetime


class McpCallLogListResponse(BaseModel):
    items: list[McpCallLogItem]
    total: int = Field(ge=0)
