"""Executor adapter schemas - Adapter interface and communication DTOs."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.modules.task_orchestrator.enums import CallbackMode, ExecutorType


class ExecutorSubmitContext(BaseModel):
    """Context for executor submission."""

    workflow_instance_id: str = Field(description="Workflow instance ID")
    workflow_node_id: str = Field(description="Workflow node ID")
    thread_id: str = Field(description="LangGraph thread ID")
    node_key: str = Field(description="Node key")
    node_type: str = Field(description="Node type")
    role_code: str | None = Field(default=None, description="Role code for assignment")
    assigned_agent_id: str | None = Field(default=None, description="Pre-assigned agent ID")
    input_payload: dict[str, Any] = Field(description="Node input data")
    callback_url: str | None = Field(default=None, description="Callback URL for webhook mode")
    timeout_sec: int = Field(default=1800, description="Execution timeout in seconds")
    trace_id: str | None = Field(default=None, description="Distributed trace ID")
    org_id: str = Field(description="Organization ID")
    workspace_id: str | None = Field(default=None, description="Workspace ID")


class ExecutorSubmitResult(BaseModel):
    """Result of executor submission."""

    accepted: bool = Field(description="Whether submission was accepted")
    external_run_id: str | None = Field(default=None, description="External run ID for tracking")
    callback_mode: CallbackMode = Field(default=CallbackMode.POLL, description="Callback mode")
    estimated_duration_sec: int | None = Field(default=None, description="Estimated execution duration")
    raw: dict[str, Any] = Field(default_factory=dict, description="Raw executor response")


class ExecutorPollResult(BaseModel):
    """Result of executor poll."""

    status: Literal["pending", "running", "completed", "failed", "cancelled"] = Field(
        description="Execution status"
    )
    progress: float | None = Field(default=None, ge=0.0, le=1.0, description="Progress percentage")
    result: dict[str, Any] = Field(default_factory=dict, description="Execution result")
    error: dict[str, Any] = Field(default_factory=dict, description="Error details if failed")
    started_at: datetime | None = Field(default=None, description="Execution start time")
    completed_at: datetime | None = Field(default=None, description="Execution completion time")


class ExecutorCancelResult(BaseModel):
    """Result of executor cancellation."""

    cancelled: bool = Field(description="Whether cancellation succeeded")
    reason: str | None = Field(default=None, description="Cancellation reason or error")


class ExecutorCallbackPayload(BaseModel):
    """Payload received from executor callback."""

    executor_type: ExecutorType = Field(description="Executor type")
    external_run_id: str = Field(description="External run ID")
    status: str = Field(description="Execution status")
    result: dict[str, Any] = Field(default_factory=dict, description="Execution result")
    error: dict[str, Any] = Field(default_factory=dict, description="Error details if failed")
    timestamp: datetime = Field(description="Callback timestamp")
    signature: str | None = Field(default=None, description="Callback signature for verification")


class ExecutorHealthStatus(BaseModel):
    """Executor health status."""

    executor_type: str
    is_healthy: bool
    last_check_at: datetime
    error_message: str | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)


class AdapterConfig(BaseModel):
    """Adapter configuration."""

    executor_type: ExecutorType
    enabled: bool = True
    max_concurrent_runs: int = Field(default=10, ge=1, description="Maximum concurrent runs")
    default_timeout_sec: int = Field(default=1800, ge=1, description="Default timeout")
    retry_on_failure: bool = Field(default=True, description="Whether to retry on failure")
    config: dict[str, Any] = Field(default_factory=dict, description="Executor-specific config")


class OpenClawAdapterConfig(AdapterConfig):
    """OpenClaw adapter configuration."""

    executor_type: ExecutorType = ExecutorType.OPENCLAW
    openclaw_base_url: str = Field(description="OpenClaw API base URL")
    openclaw_api_key: str | None = Field(default=None, description="OpenClaw API key")


class DifyAdapterConfig(AdapterConfig):
    """Dify adapter configuration."""

    executor_type: ExecutorType = ExecutorType.DIFY
    dify_base_url: str = Field(description="Dify API base URL")
    dify_api_key: str = Field(description="Dify API key")


class DeerFlowAdapterConfig(AdapterConfig):
    """DeerFlow adapter configuration."""

    executor_type: ExecutorType = ExecutorType.DEERFLOW
    deerflow_gateway_url: str = Field(description="DeerFlow Gateway URL")
    deerflow_api_key: str | None = Field(default=None, description="DeerFlow API key")


class HumanReviewAdapterConfig(AdapterConfig):
    """Human review adapter configuration."""

    executor_type: ExecutorType = ExecutorType.HUMAN_REVIEW
    notification_enabled: bool = Field(default=True, description="Enable notifications")
    default_timeout_hours: int = Field(default=24, ge=1, description="Default timeout in hours")
