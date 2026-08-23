from typing import Any

from pydantic import BaseModel, Field


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


class ToolsListResult(BaseModel):
    tools: list[dict[str, Any]] = Field(default_factory=list)
