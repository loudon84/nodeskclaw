from datetime import datetime

from pydantic import BaseModel, Field


class ExpertCreateBody(BaseModel):
    hermes_agent_id: str
    expert_slug: str
    display_name: str
    description: str | None = None
    category: str | None = None
    tags: list[str] = Field(default_factory=list)
    avatar: str | None = None
    sort_order: int = 100
    published: bool = False
    enabled: bool = True


class ExpertUpdateBody(BaseModel):
    expert_slug: str | None = None
    display_name: str | None = None
    description: str | None = None
    category: str | None = None
    tags: list[str] | None = None
    avatar: str | None = None
    sort_order: int | None = None
    published: bool | None = None
    enabled: bool | None = None


class ExpertItem(BaseModel):
    id: str
    org_id: str
    hermes_agent_id: str
    expert_slug: str
    display_name: str
    description: str | None = None
    category: str | None = None
    tags: list[str] = Field(default_factory=list)
    avatar: str | None = None
    published: bool
    enabled: bool
    sort_order: int
    agent_profile: str | None = None
    public_skill_count: int = 0
    callable_skill_count: int = 0
    total_skill_count: int = 0
    recent_invocation_count_24h: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ExpertListResponse(BaseModel):
    items: list[ExpertItem]
    total: int


class ExpertTeamCreateBody(BaseModel):
    team_slug: str
    display_name: str
    description: str | None = None
    category: str | None = None
    tags: list[str] = Field(default_factory=list)
    avatar: str | None = None
    hermes_agent_id: str | None = None
    orchestration_mode: str = "upstream_skill"
    sort_order: int = 100
    published: bool = False
    enabled: bool = True


class ExpertTeamUpdateBody(BaseModel):
    team_slug: str | None = None
    display_name: str | None = None
    description: str | None = None
    category: str | None = None
    tags: list[str] | None = None
    avatar: str | None = None
    hermes_agent_id: str | None = None
    orchestration_mode: str | None = None
    sort_order: int | None = None
    published: bool | None = None
    enabled: bool | None = None


class ExpertTeamMemberBody(BaseModel):
    expert_id: str
    role: str | None = None
    responsibility: str | None = None
    order_no: int = 0
    required: bool = True


class ExpertTeamItem(BaseModel):
    id: str
    org_id: str
    team_slug: str
    display_name: str
    description: str | None = None
    category: str | None = None
    tags: list[str] = Field(default_factory=list)
    avatar: str | None = None
    hermes_agent_id: str | None = None
    orchestration_mode: str
    published: bool
    enabled: bool
    sort_order: int
    agent_profile: str | None = None
    public_skill_count: int = 0
    callable_skill_count: int = 0
    member_count: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ExpertTeamListResponse(BaseModel):
    items: list[ExpertTeamItem]
    total: int
