from datetime import datetime

from pydantic import BaseModel, Field


class RouteCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    instance_id: str
    mcp_server_ids: list[str] = Field(min_length=1)
    match_tools: list[str] = Field(default_factory=list)
    priority: int = 0
    is_active: bool = True


class RouteUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    mcp_server_ids: list[str] | None = None
    match_tools: list[str] | None = None
    priority: int | None = None
    is_active: bool | None = None


class RouteRead(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    name: str
    instance_id: str
    mcp_server_ids: list
    match_tools: list
    priority: int
    is_active: bool
    org_id: str
    created_at: datetime
    updated_at: datetime


class RouteList(BaseModel):
    items: list[RouteRead]
    total: int
