from pydantic import BaseModel, Field


class McpGatewayAuthorizeRequest(BaseModel):
    profile: str = "default"
    workspace_id: str = "default"
    expires_days: int = Field(default=180, ge=1, le=3650)
    allowed_skills: list[str] = Field(default_factory=list)
    write_env: bool = True
    force_rotate: bool = False


class McpGatewayAuthorizeResponse(BaseModel):
    ok: bool = True
    agent_id: str
    instance_name: str
    mcp_url: str
    token_prefix: str
    env_path: str | None = None
    env_updated: bool = False
    mcp_gateway_enabled: bool = True
    expires_at: str | None = None


class McpGatewayStatusResponse(BaseModel):
    status: str
    enabled: bool = False
    token_prefix: str | None = None
    mcp_url: str | None = None
    env_synced: bool = False
    expires_at: str | None = None
    revoked_at: str | None = None
    last_error: str | None = None


class McpGatewayRevokeRequest(BaseModel):
    remove_env_keys: bool = True


class McpGatewayRevokeResponse(BaseModel):
    ok: bool = True
    agent_id: str
    token_prefix: str | None = None
    revoked: bool = True
