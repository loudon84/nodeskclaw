from pydantic import BaseModel, Field


class McpProxyRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: int | str | None = None
    method: str
    params: dict | None = None


class McpProxyResponse(BaseModel):
    jsonrpc: str = "2.0"
    id: int | str | None = None
    result: dict | list | None = None
    error: dict | None = None


class AggregatedTool(BaseModel):
    name: str
    description: str | None = None
    inputSchema: dict | None = None  # noqa: N815
    source_server: str = ""
    source_server_id: str = ""


class AggregatedToolList(BaseModel):
    tools: list[AggregatedTool] = Field(default_factory=list)
    partial_failure: bool = False
    unavailable_servers: list[str] = Field(default_factory=list)


class UpstreamStatusRead(BaseModel):
    mcp_server_id: str
    mcp_server_name: str
    is_available: bool
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    last_checked_at: str | None = None
