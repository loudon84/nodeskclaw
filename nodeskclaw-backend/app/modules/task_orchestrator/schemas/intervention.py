"""Human intervention schemas - Human-in-the-loop interaction DTOs."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.modules.task_orchestrator.enums import InterventionType, InterventionStatus


class InterventionCreateRequest(BaseModel):
    """Request to create a human intervention."""

    workflow_node_id: str | None = Field(default=None, description="Node ID requiring intervention")
    intervention_type: InterventionType = Field(description="Type of intervention")
    request_payload: dict[str, Any] = Field(
        default_factory=dict, description="Intervention request data"
    )


class InterventionResolveRequest(BaseModel):
    """Request to resolve a human intervention."""

    response_payload: dict[str, Any] = Field(description="Intervention response data")


class InterventionResponse(BaseModel):
    """Human intervention response."""

    id: str
    workflow_instance_id: str
    workflow_node_id: str | None
    intervention_type: str
    status: str
    requested_by: str | None
    request_payload: dict[str, Any]
    response_payload: dict[str, Any]
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class InterventionSummary(BaseModel):
    """Human intervention summary (list view)."""

    id: str
    workflow_instance_id: str
    workflow_node_id: str | None
    intervention_type: str
    status: str
    requested_by: str | None
    created_at: datetime


class InterventionQueryParams(BaseModel):
    """Intervention query parameters."""

    workflow_instance_id: str | None = None
    workflow_node_id: str | None = None
    intervention_type: InterventionType | None = None
    status: InterventionStatus | None = None
    requested_by: str | None = None


class PendingInterventionNotification(BaseModel):
    """Notification for pending human intervention."""

    intervention_id: str
    workflow_instance_id: str
    workflow_node_id: str | None
    intervention_type: str
    request_payload: dict[str, Any]
    workflow_template_key: str
    workflow_status: str
    created_at: datetime


class InterventionApprovalPayload(BaseModel):
    """Payload for approval-type intervention."""

    decision: str = Field(description="Approval decision: 'approved' or 'rejected'")
    comment: str | None = Field(default=None, description="Optional comment")
    approved_by: str | None = Field(default=None, description="Approver user ID")
    approved_at: datetime | None = Field(default=None, description="Approval timestamp")


class InterventionModificationPayload(BaseModel):
    """Payload for modification-type intervention."""

    modifications: dict[str, Any] = Field(description="Modified data")
    reason: str | None = Field(default=None, description="Reason for modification")
    modified_by: str | None = Field(default=None, description="Modifier user ID")


class InterventionEscalationPayload(BaseModel):
    """Payload for escalation-type intervention."""

    escalation_reason: str = Field(description="Reason for escalation")
    escalate_to: str | None = Field(default=None, description="User or role to escalate to")
    priority: str | None = Field(default=None, description="Escalation priority")
    escalated_by: str | None = Field(default=None, description="Escalator user ID")
