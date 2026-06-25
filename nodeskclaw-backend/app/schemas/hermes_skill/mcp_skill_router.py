from pydantic import BaseModel, Field


class McpSkillRouterSyncRequest(BaseModel):
    profile: str = "default"
    force: bool = True
    tool_filter: str = "skill_only"
    include_registry_tools: bool = False


class McpSkillRouterSyncResponse(BaseModel):
    ok: bool = True
    agent_id: str
    instance_name: str
    profile: str
    mcp_name: str
    router_skill_name: str
    router_skill_path: str
    tool_count: int
    tool_names: list[str] = Field(default_factory=list)
    synced_at: str


class McpSkillRouterStatusResponse(BaseModel):
    status: str
    enabled: bool
    router_skill_name: str
    router_skill_path: str
    exists: bool
    tool_count: int
    last_synced_at: str | None = None
    last_error: str | None = None


class McpSkillRouterDeleteRequest(BaseModel):
    profile: str = "default"


class McpSkillRouterDeleteResponse(BaseModel):
    ok: bool = True
    agent_id: str
    deleted: bool
    router_skill_path: str
