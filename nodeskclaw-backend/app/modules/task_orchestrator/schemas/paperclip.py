"""PaperClip sync schemas - PaperClip integration and synchronization DTOs."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class TaskOrchestrationRef(BaseModel):
    """Reference to a task orchestration from PaperClip."""

    workflow_instance_id: str = Field(description="Workflow instance ID")
    thread_id: str = Field(description="LangGraph thread ID")
    source_type: Literal["paperclip_issue"] = Field(description="Source type")
    source_ref_id: str = Field(description="PaperClip issue ID")


class TaskOrchestrationEvent(BaseModel):
    """Event sent from Task Orchestrator to PaperClip."""

    type: Literal[
        "workflow_created",
        "workflow_running",
        "node_dispatched",
        "node_blocked",
        "waiting_human",
        "workflow_completed",
        "workflow_failed",
    ] = Field(description="Event type")
    workflow_instance_id: str = Field(description="Workflow instance ID")
    issue_id: str = Field(description="PaperClip issue ID")
    node_key: str | None = Field(default=None, description="Node key if applicable")
    payload: dict[str, Any] = Field(default_factory=dict, description="Event payload")
    trace_id: str | None = Field(default=None, description="Distributed trace ID")
    timestamp: datetime = Field(description="Event timestamp")


class PaperClipIssueUpdate(BaseModel):
    """PaperClip issue update request."""

    issue_id: str = Field(description="Issue ID")
    status: str | None = Field(default=None, description="New issue status")
    assignee_agent_id: str | None = Field(default=None, description="Assigned agent ID")
    metadata: dict[str, Any] | None = Field(default=None, description="Issue metadata updates")


class PaperClipComment(BaseModel):
    """PaperClip comment creation request."""

    issue_id: str = Field(description="Issue ID")
    body: str = Field(description="Comment body")
    author_agent_id: str | None = Field(default=None, description="Author agent ID")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Comment metadata")


class PaperClipSubtask(BaseModel):
    """PaperClip subtask creation request."""

    parent_issue_id: str = Field(description="Parent issue ID")
    title: str = Field(description="Subtask title")
    description: str | None = Field(default=None, description="Subtask description")
    status: str = Field(default="todo", description="Initial status")
    assignee_agent_id: str | None = Field(default=None, description="Assigned agent ID")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Subtask metadata")


class PaperClipSyncRequest(BaseModel):
    """Request to sync with PaperClip."""

    workflow_instance_id: str = Field(description="Workflow instance ID")
    sync_type: Literal["status", "comment", "subtask", "full"] = Field(description="Sync type")
    payload: dict[str, Any] = Field(description="Sync payload")


class PaperClipSyncResult(BaseModel):
    """Result of PaperClip sync operation."""

    success: bool = Field(description="Whether sync succeeded")
    sync_type: str = Field(description="Sync type performed")
    issue_id: str = Field(description="PaperClip issue ID")
    error: str | None = Field(default=None, description="Error message if failed")
    timestamp: datetime = Field(description="Sync timestamp")


class PaperClipWebhookPayload(BaseModel):
    """Payload received from PaperClip webhook."""

    event_type: str = Field(description="Webhook event type")
    issue_id: str = Field(description="Issue ID")
    issue_status: str = Field(description="Issue status")
    issue_metadata: dict[str, Any] = Field(default_factory=dict, description="Issue metadata")
    timestamp: datetime = Field(description="Webhook timestamp")
    signature: str | None = Field(default=None, description="Webhook signature")


class PaperClipIssueContext(BaseModel):
    """PaperClip issue context for workflow creation."""

    issue_id: str = Field(description="Issue ID")
    company_id: str = Field(description="Company ID")
    org_id: str = Field(description="Organization ID")
    workspace_id: str | None = Field(default=None, description="Workspace ID")
    issue_type: str = Field(description="Issue type")
    issue_metadata: dict[str, Any] = Field(default_factory=dict, description="Issue metadata")
    run_id: str | None = Field(default=None, description="PaperClip run ID")
    trace_id: str | None = Field(default=None, description="Distributed trace ID")


class PaperClipWorkflowMapping(BaseModel):
    """Mapping between PaperClip issue and workflow."""

    issue_id: str = Field(description="PaperClip issue ID")
    workflow_instance_id: str = Field(description="Workflow instance ID")
    thread_id: str = Field(description="LangGraph thread ID")
    template_key: str = Field(description="Workflow template key")
    created_at: datetime = Field(description="Mapping creation time")
    updated_at: datetime = Field(description="Mapping update time")
