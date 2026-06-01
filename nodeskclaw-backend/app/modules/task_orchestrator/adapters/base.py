"""Base executor adapter - Abstract base class for all executors."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


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
    callback_mode: Literal["poll", "webhook", "interrupt"] = Field(
        default="poll", description="Callback mode"
    )
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


class BaseExecutorAdapter(ABC):
    """Abstract base class for executor adapters.

    All executor adapters must implement this interface to integrate
    with the Task Orchestrator.
    """

    @abstractmethod
    async def submit(self, ctx: ExecutorSubmitContext) -> ExecutorSubmitResult:
        """Submit a task for execution.

        Args:
            ctx: Submission context

        Returns:
            Submission result
        """
        pass

    @abstractmethod
    async def poll(self, external_run_id: str) -> ExecutorPollResult:
        """Poll execution status.

        Args:
            external_run_id: External run ID

        Returns:
            Poll result
        """
        pass

    @abstractmethod
    async def cancel(self, external_run_id: str) -> ExecutorCancelResult:
        """Cancel execution.

        Args:
            external_run_id: External run ID

        Returns:
            Cancellation result
        """
        pass

    @abstractmethod
    def normalize_output(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Normalize executor output to standard format.

        Args:
            raw: Raw executor output

        Returns:
            Normalized output
        """
        pass

    async def health_check(self) -> bool:
        """Check if executor is healthy.

        Returns:
            True if healthy, False otherwise
        """
        return True

    def get_executor_type(self) -> str:
        """Get executor type name.

        Returns:
            Executor type name
        """
        return self.__class__.__name__.replace("Adapter", "").lower()
