"""Workflow instance schemas - Workflow execution and management DTOs."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.modules.task_orchestrator.enums import SourceType, WorkflowStatus


class WorkflowCreateRequest(BaseModel):
    """Request to create a workflow instance."""

    template_key: str = Field(description="Template key to instantiate")
    source_type: SourceType = Field(description="Trigger source type")
    source_ref_id: str = Field(description="Source reference ID (e.g., issue ID)")
    org_id: str = Field(description="Organization ID")
    workspace_id: str | None = Field(default=None, description="Workspace ID")
    input_payload: dict[str, Any] = Field(description="Workflow input data")
    options: dict[str, Any] = Field(default_factory=dict, description="Execution options")


class WorkflowCreateResponse(BaseModel):
    """Response after creating a workflow instance."""

    workflow_instance_id: str
    thread_id: str
    status: str


class WorkflowNodeDTO(BaseModel):
    """Workflow node data transfer object."""

    id: str
    node_key: str
    node_type: str
    executor_type: str
    status: str
    role_code: str | None = None
    assigned_agent_id: str | None = None
    external_run_id: str | None = None
    retry_count: int = 0
    timeout_sec: int = 1800
    started_at: datetime | None = None
    completed_at: datetime | None = None
    blocked_reason: str | None = None


class WorkflowDetailResponse(BaseModel):
    """Detailed workflow instance response."""

    id: str
    template_key: str
    template_id: str
    status: str
    thread_id: str
    source_type: str
    source_ref_id: str
    org_id: str
    workspace_id: str | None
    input_payload: dict[str, Any]
    runtime_state: dict[str, Any]
    current_node_keys: list[str]
    nodes: list[WorkflowNodeDTO]
    started_at: datetime | None
    completed_at: datetime | None
    error_summary: str | None
    created_at: datetime
    updated_at: datetime


class WorkflowSummary(BaseModel):
    """Workflow instance summary (list view)."""

    id: str
    template_key: str
    status: str
    thread_id: str
    source_type: str
    source_ref_id: str
    org_id: str
    current_node_keys: list[str]
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class WorkflowActionRequest(BaseModel):
    """Request for workflow actions (pause/resume/cancel)."""

    reason: str | None = Field(default=None, description="Reason for action")


class WorkflowActionResponse(BaseModel):
    """Response after workflow action."""

    workflow_instance_id: str
    status: str
    message: str


class RetryNodeRequest(BaseModel):
    """Request to retry a failed node."""

    node_key: str = Field(description="Node key to retry")
    reason: str | None = Field(default=None, description="Reason for retry")


class WorkflowTimelineEvent(BaseModel):
    """Workflow timeline event."""

    id: str
    workflow_instance_id: str
    workflow_node_id: str | None
    event_type: str
    event_payload: dict[str, Any]
    trace_id: str | None
    created_at: datetime


class WorkflowTimelineResponse(BaseModel):
    """Workflow timeline response."""

    workflow_instance_id: str
    events: list[WorkflowTimelineEvent]
    total: int


class WorkflowQueryParams(BaseModel):
    """Workflow query parameters."""

    template_key: str | None = None
    status: WorkflowStatus | None = None
    source_type: SourceType | None = None
    source_ref_id: str | None = None
    org_id: str | None = None
    workspace_id: str | None = None
    thread_id: str | None = None


class WorkflowRuntimeStateUpdate(BaseModel):
    """Workflow runtime state update."""

    runtime_state: dict[str, Any] = Field(description="Updated runtime state")
    current_node_keys: list[str] | None = Field(default=None, description="Updated current node keys")
