"""Workflow template schemas - Template definition and management DTOs."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.modules.task_orchestrator.enums import SourceType, TemplateStatus


class WorkflowNodeTemplate(BaseModel):
    """Workflow node template definition."""

    node_key: str = Field(description="Unique node identifier within template")
    node_type: Literal["role_task", "system_task", "human_review", "gateway_task"] = Field(
        description="Node type determining execution behavior"
    )
    role_code: str | None = Field(default=None, description="Role code for role-based task assignment")
    executor_type: Literal["openclaw", "dify", "deerflow", "human_review", "system"] = Field(
        description="Executor backend type"
    )
    timeout_sec: int = Field(default=1800, ge=1, description="Node execution timeout in seconds")
    retry_max_attempts: int = Field(default=2, ge=0, description="Maximum retry attempts on failure")
    required_capabilities: list[str] = Field(default_factory=list, description="Required agent capabilities")
    input_schema: dict[str, Any] = Field(default_factory=dict, description="Input JSON schema")
    output_schema: dict[str, Any] = Field(default_factory=dict, description="Output JSON schema")
    config: dict[str, Any] = Field(default_factory=dict, description="Node-specific configuration")


class WorkflowEdgeTemplate(BaseModel):
    """Workflow edge template definition."""

    from_node: str = Field(description="Source node key")
    to_node: str = Field(description="Target node key")
    condition_type: Literal["always", "success", "failure", "manual_gate", "expr"] = Field(
        default="always", description="Edge condition type"
    )
    condition_expr: dict[str, Any] | None = Field(default=None, description="Condition expression for 'expr' type")


class WorkflowTemplateDefinition(BaseModel):
    """Complete workflow template definition."""

    entry_node: str = Field(description="Entry node key")
    terminal_node: str = Field(description="Terminal node key")
    nodes: list[WorkflowNodeTemplate] = Field(description="Node templates")
    edges: list[WorkflowEdgeTemplate] = Field(description="Edge templates")
    variables: dict[str, Any] = Field(default_factory=dict, description="Template variables")


class WorkflowTemplateCreateRequest(BaseModel):
    """Request to create a workflow template."""

    template_key: str = Field(description="Unique template identifier")
    name: str = Field(description="Template display name")
    version: int = Field(default=1, ge=1, description="Template version")
    source_type: SourceType = Field(description="Template source type")
    definition: WorkflowTemplateDefinition = Field(description="Template definition")
    description: str | None = Field(default=None, description="Template description")
    is_active: bool = Field(default=True, description="Whether template is active")


class WorkflowTemplateUpdateRequest(BaseModel):
    """Request to update a workflow template."""

    name: str | None = Field(default=None, description="Template display name")
    definition: WorkflowTemplateDefinition | None = Field(default=None, description="Template definition")
    description: str | None = Field(default=None, description="Template description")
    is_active: bool | None = Field(default=None, description="Whether template is active")
    status: TemplateStatus | None = Field(default=None, description="Template status")


class WorkflowTemplateResponse(BaseModel):
    """Workflow template response."""

    id: str
    template_key: str
    name: str
    version: int
    source_type: str
    status: str
    definition: dict[str, Any]
    is_active: bool
    description: str | None
    created_by: str | None
    created_at: datetime
    updated_at: datetime


class WorkflowTemplateSummary(BaseModel):
    """Workflow template summary (list view)."""

    id: str
    template_key: str
    name: str
    version: int
    source_type: str
    status: str
    is_active: bool
    description: str | None
    created_at: datetime
