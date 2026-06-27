from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ExpertTeamSkillUpdateBody(BaseModel):
    skill_name: str | None = None
    display_name: str | None = None
    description: str | None = None
    public: bool | None = None
    call_enabled: bool | None = None
    risk_level: str | None = None
    approval_mode: str | None = None
    output_formats: list[str] | None = None
    sort_order: int | None = None


class ExpertTeamSkillItem(BaseModel):
    id: str
    org_id: str
    expert_team_id: str
    skill_name: str
    upstream_tool_name: str
    display_name: str | None = None
    description: str | None = None
    input_schema: dict[str, Any] = Field(default_factory=dict)
    public: bool
    call_enabled: bool
    risk_level: str
    approval_mode: str
    output_formats: list[str] = Field(default_factory=list)
    sort_order: int
    stale: bool
    last_synced_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ExpertTeamSkillListResponse(BaseModel):
    items: list[ExpertTeamSkillItem]
    total: int
