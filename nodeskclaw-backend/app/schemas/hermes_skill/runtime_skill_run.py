from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class StartRuntimeSkillRunRequest:
    org_id: str
    user_id: str
    tool_name: str
    runtime_skill_id: str
    agent_profile: str
    hermes_agent_instance_id: str
    agent_id: str | None
    arguments: dict[str, Any]
    client_context: dict[str, Any]
    output_policy: dict[str, Any]
    task_source: str
    skill_id: str
    installation_id: str | None = None
    workspace_id: str | None = None
    timeout_seconds: int | None = None
    request_trace_id: str | None = None
    request_snapshot: dict[str, Any] | None = None
    route_diagnostics: dict[str, Any] | None = None
    execution_mode: str = "async_event"
    entrypoint: str = "mcp_skill_gateway"
    catalog_kind: str | None = None
    catalog_slug: str | None = None
    skill_name: str | None = None
    invocation_id: str | None = None
    upstream_tool_name: str | None = None
    extra_route_snapshot: dict[str, Any] = field(default_factory=dict)
    routing_metadata_extras: dict[str, Any] = field(default_factory=dict)
    sse_token_ttl_seconds: int | None = None


@dataclass
class RuntimeSkillRunResult:
    task: Any
    sse_token: str
    structured_content: dict[str, Any]
