from typing import Any, Literal

from pydantic import BaseModel, Field


class SkillToolAnnotations(BaseModel):
    category: str | None = None
    riskLevel: str | None = None
    requiresApproval: bool = False
    approvalMode: str | None = None
    streaming: bool = True
    artifacts: bool = True
    version: str | None = None


class SkillToolDescriptor(BaseModel):
    name: str
    title: str | None = None
    description: str = ""
    inputSchema: dict[str, Any] = Field(default_factory=dict)
    version: str | None = None
    category: str | None = None
    annotations: SkillToolAnnotations | None = None


class ToolsListResult(BaseModel):
    tools: list[SkillToolDescriptor] = Field(default_factory=list)


class SkillRunAcceptedStructuredContent(BaseModel):
    committed: bool = True
    run_id: str
    status: str
    tool_name: str | None = None
    event_stream: str
    result_url: str
    artifact_url: str | None = None
    execution_mode: str | None = "async_event"
    message: str | None = None
    request_trace_id: str | None = None


class ToolsCallAcceptedResult(BaseModel):
    content: list[dict[str, Any]] = Field(default_factory=list)
    structuredContent: SkillRunAcceptedStructuredContent
    isError: bool = False


class ArtifactDescriptor(BaseModel):
    artifact_id: str
    name: str
    content_type: str | None = None
    size_bytes: int | None = None
    download_url: str | None = None
    checksum_sha256: str | None = None


class ExecutionSnapshot(BaseModel):
    skill_id: str
    skill_version: str | None = None
    skill_release_id: str | None = None
    skill_release_digest: str
    session_id: str | None = None
    workspace_id: str | None = None
    attachment_refs: list[str] = Field(default_factory=list)
    knowledge_refs: list[str] = Field(default_factory=list)
    connector_binding_refs: list[str] = Field(default_factory=list)
    model_policy: dict[str, Any] = Field(default_factory=dict)
    runtime_policy: dict[str, Any] = Field(default_factory=dict)
    placement: dict[str, Any] = Field(default_factory=dict)
    snapshot_hash: str


RunStatus = Literal[
    "CREATED",
    "QUEUED",
    "PREPARING",
    "RUNNING",
    "WAITING_APPROVAL",
    "RESUMING",
    "CANCELLING",
    "COMPLETED",
    "FAILED",
    "CANCELLED",
    "TIMED_OUT",
]


class RunRecord(BaseModel):
    run_id: str
    org_id: str
    user_id: str
    tool_name: str
    status: RunStatus
    snapshot: ExecutionSnapshot
    attempt_id: str | None = None
    created_at: str
    updated_at: str


class RunEvent(BaseModel):
    event_id: str
    run_id: str
    event_type: str
    event_seq: int
    source: str = "agent"
    source_event_id: str | None = None
    timestamp: str
    payload: dict[str, Any] = Field(default_factory=dict)


class SkillToolAnnotationsV11(BaseModel):
    category: str | None = None
    riskLevel: str = "low"
    requiresApproval: bool = False
    approvalMode: str = "none"
    streaming: bool = True
    artifacts: bool = True
    version: str | None = None


class SkillToolDescriptorV11(BaseModel):
    name: str
    title: str | None = None
    description: str = ""
    inputSchema: dict[str, Any] = Field(default_factory=dict)
    version: str | None = None
    category: str | None = None
    capabilityKind: Literal["skill", "connector"]
    interactionMode: Literal["chat", "form"]
    promptField: str | None = None
    supportsAttachments: bool = False
    skillReleaseId: str | None = None
    skillReleaseDigest: str | None = None
    annotations: SkillToolAnnotationsV11 = Field(default_factory=SkillToolAnnotationsV11)


class ToolsListResultV11(BaseModel):
    tools: list[SkillToolDescriptorV11] = Field(default_factory=list)


class SkillRunAcceptedStructuredContentV11(BaseModel):
    committed: bool = True
    run_id: str
    status: str
    tool_name: str | None = None
    event_stream: str
    result_url: str
    artifact_url: str | None = None
    execution_mode: str | None = "async_event"
    message: str | None = None
    request_trace_id: str | None = None
    contract_version: str | None = None


class ToolsCallAcceptedResultV11(BaseModel):
    content: list[dict[str, Any]] = Field(default_factory=list)
    structuredContent: SkillRunAcceptedStructuredContentV11
    isError: bool = False

