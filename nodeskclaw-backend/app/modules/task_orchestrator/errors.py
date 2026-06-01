"""Task Orchestrator Errors - Module-specific exception classes."""


class TaskOrchestratorError(Exception):
    """Base exception for Task Orchestrator module."""

    pass


class WorkflowNotFoundError(TaskOrchestratorError):
    """Raised when a workflow instance is not found."""

    def __init__(self, workflow_id: str):
        self.workflow_id = workflow_id
        super().__init__(f"Workflow instance not found: {workflow_id}")


class WorkflowTemplateNotFoundError(TaskOrchestratorError):
    """Raised when a workflow template is not found."""

    def __init__(self, template_key: str, version: int | None = None):
        self.template_key = template_key
        self.version = version
        msg = f"Workflow template not found: {template_key}"
        if version:
            msg += f" (version {version})"
        super().__init__(msg)


class WorkflowNodeNotFoundError(TaskOrchestratorError):
    """Raised when a workflow node is not found."""

    def __init__(self, workflow_id: str, node_key: str):
        self.workflow_id = workflow_id
        self.node_key = node_key
        super().__init__(f"Workflow node not found: {workflow_id}/{node_key}")


class InvalidWorkflowStateError(TaskOrchestratorError):
    """Raised when an operation is invalid for the current workflow state."""

    def __init__(self, workflow_id: str, current_status: str, operation: str):
        self.workflow_id = workflow_id
        self.current_status = current_status
        self.operation = operation
        super().__init__(f"Invalid operation '{operation}' for workflow {workflow_id} in state '{current_status}'")


class InvalidNodeStateError(TaskOrchestratorError):
    """Raised when an operation is invalid for the current node state."""

    def __init__(self, node_id: str, current_status: str, operation: str):
        self.node_id = node_id
        self.current_status = current_status
        self.operation = operation
        super().__init__(f"Invalid operation '{operation}' for node {node_id} in state '{current_status}'")


class ExecutorAdapterError(TaskOrchestratorError):
    """Raised when an executor adapter encounters an error."""

    def __init__(self, executor_type: str, message: str):
        self.executor_type = executor_type
        super().__init__(f"Executor adapter error ({executor_type}): {message}")


class ExecutorSubmissionError(ExecutorAdapterError):
    """Raised when executor submission fails."""

    def __init__(self, executor_type: str, workflow_node_id: str, reason: str):
        self.workflow_node_id = workflow_node_id
        self.reason = reason
        super().__init__(executor_type, f"Submission failed for node {workflow_node_id}: {reason}")


class ExecutorPollError(ExecutorAdapterError):
    """Raised when executor poll fails."""

    def __init__(self, executor_type: str, external_run_id: str, reason: str):
        self.external_run_id = external_run_id
        self.reason = reason
        super().__init__(executor_type, f"Poll failed for run {external_run_id}: {reason}")


class RoutingError(TaskOrchestratorError):
    """Raised when executor routing fails."""

    def __init__(self, node_key: str, reason: str):
        self.node_key = node_key
        self.reason = reason
        super().__init__(f"Routing failed for node {node_key}: {reason}")


class CheckpointError(TaskOrchestratorError):
    """Raised when checkpoint operation fails."""

    def __init__(self, thread_id: str, operation: str, reason: str):
        self.thread_id = thread_id
        self.operation = operation
        self.reason = reason
        super().__init__(f"Checkpoint {operation} failed for thread {thread_id}: {reason}")


class InterventionNotFoundError(TaskOrchestratorError):
    """Raised when a human intervention is not found."""

    def __init__(self, intervention_id: str):
        self.intervention_id = intervention_id
        super().__init__(f"Human intervention not found: {intervention_id}")


class InterventionAlreadyResolvedError(TaskOrchestratorError):
    """Raised when attempting to resolve an already resolved intervention."""

    def __init__(self, intervention_id: str):
        self.intervention_id = intervention_id
        super().__init__(f"Human intervention already resolved: {intervention_id}")


class GraphBuildError(TaskOrchestratorError):
    """Raised when graph building fails."""

    def __init__(self, template_key: str, reason: str):
        self.template_key = template_key
        self.reason = reason
        super().__init__(f"Graph build failed for template {template_key}: {reason}")


class GraphExecutionError(TaskOrchestratorError):
    """Raised when graph execution fails."""

    def __init__(self, workflow_id: str, node_key: str, reason: str):
        self.workflow_id = workflow_id
        self.node_key = node_key
        self.reason = reason
        super().__init__(f"Graph execution failed at {workflow_id}/{node_key}: {reason}")


class TimeoutError(TaskOrchestratorError):
    """Raised when a workflow or node times out."""

    def __init__(self, workflow_id: str, node_key: str | None = None):
        self.workflow_id = workflow_id
        self.node_key = node_key
        if node_key:
            super().__init__(f"Node timeout: {workflow_id}/{node_key}")
        else:
            super().__init__(f"Workflow timeout: {workflow_id}")


class RetryExhaustedError(TaskOrchestratorError):
    """Raised when retry attempts are exhausted."""

    def __init__(self, workflow_id: str, node_key: str, max_attempts: int):
        self.workflow_id = workflow_id
        self.node_key = node_key
        self.max_attempts = max_attempts
        super().__init__(f"Retry exhausted for {workflow_id}/{node_key} after {max_attempts} attempts")


class PaperClipSyncError(TaskOrchestratorError):
    """Raised when PaperClip synchronization fails."""

    def __init__(self, operation: str, reason: str):
        self.operation = operation
        self.reason = reason
        super().__init__(f"PaperClip sync failed ({operation}): {reason}")
