from datetime import datetime

from pydantic import BaseModel, Field


class ScanExistingAgentsRequest(BaseModel):
    instances_root: str | None = None
    probe_after_scan: bool = True


class HermesAgentInstanceSummary(BaseModel):
    id: str
    profile_name: str
    container_name: str
    container_id: str | None = None
    image: str | None = None
    docker_status: str
    docker_health: str
    host_ip: str | None = None
    webui_port: int | None = None
    webui_url: str | None = None
    gateway_port: int | None = None
    gateway_url: str | None = None
    gateway_status: str
    runtime_status: str
    mcp_status: str
    instance_dir: str | None = None
    data_dir: str | None = None
    env_file: str | None = None
    compose_file: str | None = None
    compose_project: str | None = None
    managed_mode: str | None = None
    instance_id: str | None = None
    last_probe_at: datetime | str | None = None
    last_seen_at: datetime | str | None = None
    last_error: str | None = None


class ScanExistingAgentsResponse(BaseModel):
    scanned: int
    bound: int
    failed: int
    items: list[HermesAgentInstanceSummary]


class HermesAgentInstanceListResponse(BaseModel):
    items: list[HermesAgentInstanceSummary]


class ProbeAllAgentsResponse(BaseModel):
    success: bool = True
    total: int
    ready: int
    degraded: int
    unavailable: int
    unconfigured: int
    items: list[dict] = Field(default_factory=list)


class DiagnosticCheckItem(BaseModel):
    name: str
    status: str
    message: str


class HermesAgentDiagnosticsResponse(BaseModel):
    profile_name: str
    checks: list[DiagnosticCheckItem]
