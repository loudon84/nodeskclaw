from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class JsonRpcRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: str | int | None = None
    method: str
    params: dict[str, Any] | None = None


class JsonRpcErrorData(BaseModel):
    errorCode: str
    message_key: str | None = None
    forbiddenKeys: list[str] | None = None


class JsonRpcErrorBody(BaseModel):
    code: int
    message: str
    data: JsonRpcErrorData | dict[str, Any] | None = None


class JsonRpcErrorResponse(BaseModel):
    jsonrpc: str = "2.0"
    id: str | int | None = None
    error: JsonRpcErrorBody


class WaitStrategy(BaseModel):
    type: str = "sse"
    fallback: str = "poll"
    poll_url: str
    poll_tool: str = "nodeskclaw_task_wait"
    result_url: str


class ToolsCallAcceptedStructuredContent(BaseModel):
    committed: bool = True
    task_id: str
    task_no: str | None = None
    status: str
    execution_mode: str | None = None
    tool_name: str | None = None
    event_stream: str
    event_url: str | None = None
    event_token_url: str
    result_url: str
    artifact_url: str | None = None
    wait_strategy: WaitStrategy
    catalog_slug: str | None = None
    skill_name: str | None = None
    invocation_id: str | None = None
    artifact_mode: str | None = None
    server_artifacts: list[dict[str, Any]] = Field(default_factory=list)
    message: str | None = None
    entrypoint: str | None = None
    task_source: str | None = None
    agent_profile: str | None = None
    runtime_skill_id: str | None = None
    catalog_kind: str | None = None


class ToolsCallAcceptedResult(BaseModel):
    content: list[dict[str, Any]] = Field(default_factory=list)
    structuredContent: ToolsCallAcceptedStructuredContent
    isError: bool = False


class JsonRpcSuccessResponse(BaseModel):
    jsonrpc: str = "2.0"
    id: str | int | None = None
    result: dict[str, Any] | ToolsCallAcceptedResult | None = None


class McpInputSchema(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str = "object"
    properties: dict[str, Any] = Field(default_factory=dict)
    required: list[str] | None = None
    additionalProperties: bool | dict[str, Any] | None = None
    items: dict[str, Any] | None = None
    description: str | None = None
    title: str | None = None


class CatalogToolAnnotations(BaseModel):
    """POST /api/v1/expert/mcp tools/list Expert / Expert Team annotations."""

    model_config = ConfigDict(extra="allow")

    kind: Literal["expert", "expert_team"]
    slug: str = Field(min_length=1)
    displayName: str | None = None
    status: str = Field(min_length=1)
    publicSkillCount: int = Field(ge=0)
    callableSkillCount: int = Field(ge=0)


class SkillToolAnnotations(BaseModel):
    """POST /api/v1/expert/mcp/{slug} tools/list Skill annotations."""

    model_config = ConfigDict(extra="allow")

    displayName: str | None = None
    status: str = Field(min_length=1)
    callEnabled: bool
    riskLevel: str = Field(min_length=1)
    approvalMode: str = Field(min_length=1)


class McpTool(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str = Field(min_length=1)
    description: str | None = None
    inputSchema: McpInputSchema
    annotations: CatalogToolAnnotations | SkillToolAnnotations


class ToolsListResult(BaseModel):
    tools: list[McpTool] = Field(default_factory=list)
