from typing import Literal

from pydantic import BaseModel, Field


class RuntimeSkillRegisterGrant(BaseModel):
    subject_type: Literal["org", "user", "role", "agent"] = "org"
    subject_id: str | None = None
    can_list: bool = True
    can_invoke: bool = True
    can_install: bool = False
    can_manage: bool = False


class RuntimeSkillRegisterRequest(BaseModel):
    profile_id: str = "default"
    workspace_id: str = "default"
    tool_name: str | None = None
    is_mcp_exposed: bool = True
    default_execution_mode: Literal["async"] = "async"
    timeout_seconds: int = Field(default=1800, ge=60, le=7200)
    grant: RuntimeSkillRegisterGrant | None = None


class RuntimeSkillRegisterResponse(BaseModel):
    skill_db_id: str
    skill_id: str
    tool_name: str
    runtime_skill_id: str
    hermes_instance_name: str
    hermes_agent_instance_id: str
    agent_profile: str
    profile_id: str
    workspace_id: str
    installation_id: str
    is_mcp_exposed: bool
    grant_created: bool
    status: Literal["created", "updated"]
