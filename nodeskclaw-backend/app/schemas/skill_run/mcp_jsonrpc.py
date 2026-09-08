from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


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


class PublicContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PublicSkillToolAnnotations(PublicContractModel):
    category: str | None = None
    riskLevel: Literal["low", "medium", "high", "critical"] = "low"
    requiresApproval: bool = False
    streaming: bool = True
    artifacts: bool = True
    version: str | None = None


class PublicSkillToolDescriptor(PublicContractModel):
    name: str
    title: str
    description: str
    inputSchema: dict[str, Any]
    version: str
    category: str | None = None
    capabilityKind: Literal["skill"]
    interactionMode: Literal["chat", "form"]
    promptField: str | None = None
    supportsAttachments: bool = False
    annotations: PublicSkillToolAnnotations


class PublicToolsListResult(PublicContractModel):
    tools: list[PublicSkillToolDescriptor] = Field(default_factory=list)


class PublicMcpTextContent(PublicContractModel):
    type: Literal["text"]
    text: str


class PublicSkillRunAccepted(PublicContractModel):
    committed: Literal[True]
    run_id: str
    status: RunStatus
    tool_name: str
    event_stream: str
    result_url: str
    artifact_url: str
    execution_mode: Literal["async_event"]


class PublicToolsCallAccepted(PublicContractModel):
    content: list[PublicMcpTextContent] = Field(default_factory=list)
    structuredContent: PublicSkillRunAccepted
    isError: Literal[False]


class PublicRunView(PublicContractModel):
    run_id: str
    tool_name: str
    status: RunStatus
    created_at: str | None = None
    updated_at: str | None = None


class PublicRunResult(PublicContractModel):
    run_id: str
    status: RunStatus
    text: str | None = None
    error_code: str | None = None
    error_message: str | None = None


class PublicArtifactDescriptor(PublicContractModel):
    artifact_id: str
    name: str
    content_type: str | None = None
    size_bytes: int
    checksum_sha256: str


class PublicArtifactList(PublicContractModel):
    run_id: str
    items: list[PublicArtifactDescriptor] = Field(default_factory=list)


class PublicArtifactDownloadResponse(PublicContractModel):
    content_type: str
    content_disposition: str
    content_length: int
    checksum_sha256: str


class UnsupportedCapabilities(PublicContractModel):
    approval: Literal["unsupported"]
    attachments: Literal["unsupported"]


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


class AssistantMessagePayload(BaseModel):
    text: str


class ReasoningSummaryPayload(BaseModel):
    summary: str


class ToolCallPayload(BaseModel):
    tool_name: str
    call_id: str
    status: Literal["started", "completed", "failed"]


class ClarifyRequestedPayload(BaseModel):
    question: str
    options: list[Any] | None = None


class ApprovalRequestedPayload(BaseModel):
    approval_id: str
    summary: str


class ArtifactPersistedPayload(BaseModel):
    artifact_id: str
    name: str
    content_type: str | None = None
    size: int
    checksum_sha256: str


class RunEventAssistantMessageV12(BaseModel):
    event_id: str
    run_id: str
    event_type: Literal["assistant.message"]
    event_seq: int
    source: str = "agent"
    source_event_id: str | None = None
    timestamp: str
    payload: AssistantMessagePayload


class RunEventReasoningSummaryV12(BaseModel):
    event_id: str
    run_id: str
    event_type: Literal["reasoning.summary"]
    event_seq: int
    source: str = "agent"
    source_event_id: str | None = None
    timestamp: str
    payload: ReasoningSummaryPayload


class RunEventToolCallV12(BaseModel):
    event_id: str
    run_id: str
    event_type: Literal["tool.call"]
    event_seq: int
    source: str = "agent"
    source_event_id: str | None = None
    timestamp: str
    payload: ToolCallPayload


class RunEventClarifyRequestedV12(BaseModel):
    event_id: str
    run_id: str
    event_type: Literal["clarify.requested"]
    event_seq: int
    source: str = "agent"
    source_event_id: str | None = None
    timestamp: str
    payload: ClarifyRequestedPayload


class RunEventApprovalRequestedV12(BaseModel):
    event_id: str
    run_id: str
    event_type: Literal["approval.requested"]
    event_seq: int
    source: str = "agent"
    source_event_id: str | None = None
    timestamp: str
    payload: ApprovalRequestedPayload


class RunEventArtifactPersistedV12(BaseModel):
    event_id: str
    run_id: str
    event_type: Literal["artifact.persisted"]
    event_seq: int
    source: str = "agent"
    source_event_id: str | None = None
    timestamp: str
    payload: ArtifactPersistedPayload


class RunEventControlV12(BaseModel):
    event_id: str
    run_id: str
    event_type: str = Field(pattern=r"^(run|step|edge\.job)\.")
    event_seq: int
    source: str = "agent"
    source_event_id: str | None = None
    timestamp: str
    payload: dict[str, Any] = Field(default_factory=dict)


RUN_EVENT_V12_MODELS = (
    RunEventAssistantMessageV12,
    RunEventReasoningSummaryV12,
    RunEventToolCallV12,
    RunEventClarifyRequestedV12,
    RunEventApprovalRequestedV12,
    RunEventArtifactPersistedV12,
    RunEventControlV12,
)

