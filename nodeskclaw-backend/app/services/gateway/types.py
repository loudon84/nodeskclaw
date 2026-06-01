from dataclasses import dataclass, field
from enum import StrEnum
from datetime import datetime


class PolicyDenyReason(StrEnum):
    ACCESS_DENIED = "access_denied"
    RATE_LIMITED = "rate_limited"
    CONNECTION_LIMITED = "connection_limited"
    SENSITIVE_TOOL_DENIED = "sensitive_tool_denied"
    APPROVAL_TIMEOUT = "approval_timeout"


@dataclass(frozen=True)
class UpstreamTarget:
    mcp_server_id: str
    mcp_server_name: str
    transport: str
    url: str | None
    command: str | None
    instance_id: str


@dataclass
class PolicyResult:
    is_allowed: bool
    deny_reason: PolicyDenyReason | None = None
    timeout_seconds: int = 30
    retry_count: int = 0
    rate_limit_rpm: int | None = None
    max_connections: int | None = None
    sensitive_tools: list[str] = field(default_factory=list)
    policy_id: str | None = None
    is_default_policy: bool = False


@dataclass
class UpstreamHealthState:
    mcp_server_id: str
    is_available: bool = True
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    last_checked_at: datetime | None = None


@dataclass
class SSEProxyConnection:
    connection_id: str
    client_id: str
    upstream_server_id: str
    instance_id: str
    created_at: datetime = field(default_factory=datetime.now)
    last_activity_at: datetime = field(default_factory=datetime.now)
