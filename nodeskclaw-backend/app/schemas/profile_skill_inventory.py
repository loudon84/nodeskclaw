"""Profile skill inventory tree schemas for Hermes Agent Detail."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

SkillSource = Literal["builtin", "github", "clawhub", "local", "profile", "api_server", "unknown"]
SkillTrust = Literal["builtin", "trusted", "community", "local", "unknown"]
SkillStatus = Literal["enabled", "disabled", "unknown"]
SourceMode = Literal["runtime_inventory", "profile_only_fallback", "api_server_inventory"]


class ProfileSkillInventoryItem(BaseModel):
    id: str
    slug: str
    name: str
    description: str | None = None
    category: str = "uncategorized"
    source: SkillSource = "unknown"
    trust: SkillTrust = "unknown"
    status: SkillStatus = "unknown"
    enabled: bool = True
    installed: bool = True
    manageable: bool = False
    path: str | None = None
    profile_path: str | None = None
    has_skill_md: bool = False
    can_install: bool = False
    can_enable: bool = False
    can_disable: bool = False
    can_delete: bool = False
    can_authorize: bool = True


class ProfileSkillGroup(BaseModel):
    category: str
    label: str
    count: int
    items: list[ProfileSkillInventoryItem] = Field(default_factory=list)


class ProfileSkillTreeResponse(BaseModel):
    agent_profile: str
    profile: str
    source_mode: SourceMode = "profile_only_fallback"
    total: int = 0
    enabled_count: int = 0
    manageable_count: int = 0
    warnings: list[str] = Field(default_factory=list)
    groups: list[ProfileSkillGroup] = Field(default_factory=list)
