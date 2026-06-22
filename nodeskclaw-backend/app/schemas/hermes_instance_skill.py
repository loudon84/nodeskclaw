"""Hermes instance skills and MCP Gateway schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class HermesInstanceSkillItem(BaseModel):
    name: str
    description: str | None = None
    category: str | None = None
    source: str | None = "api_server"
    status: str | None = "enabled"
    runtime_available: bool = True
    callable: bool = True


class HermesInstanceSkillListResponse(BaseModel):
    agent_profile: str
    gateway_url: str | None = None
    source_mode: str = "api_server_default"
    exposed_profile: str = "default"
    total: int = 0
    skills: list[HermesInstanceSkillItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    last_refreshed_at: datetime | None = None


class HermesMcpGatewayStatusResponse(BaseModel):
    agent_profile: str
    enabled: bool = False
    status: str = "unknown"
    endpoint: str
    expose_scope: str = "instance_default_skills"
    skills_source: str = "api_server"
    skills_count: int = 0
    tools_count: int = 0
    last_refreshed_at: datetime | None = None
    warnings: list[str] = Field(default_factory=list)


class HermesMcpToolItem(BaseModel):
    tool_name: str
    skill_id: str
    category: str | None = None
    description: str | None = None
    can_list: bool = False
    can_invoke: bool = False
