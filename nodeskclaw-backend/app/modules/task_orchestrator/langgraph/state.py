"""LangGraph state definition - Workflow execution state."""

import operator
from typing import Annotated, Any

from typing_extensions import TypedDict


def merge_dict(left: dict[str, Any] | None, right: dict[str, Any] | None) -> dict[str, Any]:
    """Merge two dictionaries (right overwrites left).

    This reducer is used for state fields that can be updated by multiple nodes
    concurrently. The right value takes precedence.

    Args:
        left: Existing dictionary
        right: New dictionary to merge

    Returns:
        Merged dictionary
    """
    if left is None:
        left = {}
    if right is None:
        right = {}
    result = dict(left)
    result.update(right)
    return result


def merge_node_statuses(
    left: dict[str, str] | None, right: dict[str, str] | None
) -> dict[str, str]:
    """Merge node status dictionaries.

    Args:
        left: Existing node statuses
        right: New node statuses

    Returns:
        Merged node statuses
    """
    return merge_dict(left, right)


def merge_node_results(
    left: dict[str, dict[str, Any]] | None, right: dict[str, dict[str, Any]] | None
) -> dict[str, dict[str, Any]]:
    """Merge node result dictionaries.

    Args:
        left: Existing node results
        right: New node results

    Returns:
        Merged node results
    """
    return merge_dict(left, right)


def merge_node_errors(
    left: dict[str, dict[str, Any]] | None, right: dict[str, dict[str, Any]] | None
) -> dict[str, dict[str, Any]]:
    """Merge node error dictionaries.

    Args:
        left: Existing node errors
        right: New node errors

    Returns:
        Merged node errors
    """
    return merge_dict(left, right)


class WorkflowState(TypedDict):
    """Workflow execution state for LangGraph.

    This state is passed between nodes in the workflow graph and accumulates
    results, errors, and audit events as the workflow executes.

    Fields:
        workflow_instance_id: Unique workflow instance identifier
        thread_id: LangGraph thread ID for checkpoint recovery
        template_key: Workflow template key
        source_ref: Source reference information (e.g., PaperClip issue)
        input_payload: Initial workflow input data
        runtime_context: Runtime context (org_id, workspace_id, user_id, etc.)
        node_statuses: Current status of each node (node_key -> status)
        node_results: Results from completed nodes (node_key -> result)
        node_errors: Errors from failed nodes (node_key -> error)
        pending_human_actions: List of pending human intervention requests
        audit_events: List of audit events for timeline
        current_node_keys: List of currently executing node keys
        metadata: Additional metadata
    """

    # Identity fields
    workflow_instance_id: str
    thread_id: str
    template_key: str

    # Input fields
    source_ref: dict[str, Any]
    input_payload: dict[str, Any]
    runtime_context: dict[str, Any]

    # Node state fields (use reducers for concurrent updates)
    node_statuses: Annotated[dict[str, str], merge_node_statuses]
    node_results: Annotated[dict[str, dict[str, Any]], merge_node_results]
    node_errors: Annotated[dict[str, dict[str, Any]], merge_node_errors]

    # Human-in-the-loop fields
    pending_human_actions: Annotated[list[dict[str, Any]], operator.add]

    # Audit trail
    audit_events: Annotated[list[dict[str, Any]], operator.add]

    # Execution state
    current_node_keys: list[str]

    # Metadata
    metadata: dict[str, Any]


def create_initial_state(
    workflow_instance_id: str,
    thread_id: str,
    template_key: str,
    source_ref: dict[str, Any],
    input_payload: dict[str, Any],
    runtime_context: dict[str, Any],
) -> WorkflowState:
    """Create initial workflow state.

    Args:
        workflow_instance_id: Workflow instance ID
        thread_id: Thread ID
        template_key: Template key
        source_ref: Source reference
        input_payload: Input payload
        runtime_context: Runtime context

    Returns:
        Initial workflow state
    """
    return WorkflowState(
        workflow_instance_id=workflow_instance_id,
        thread_id=thread_id,
        template_key=template_key,
        source_ref=source_ref,
        input_payload=input_payload,
        runtime_context=runtime_context,
        node_statuses={},
        node_results={},
        node_errors={},
        pending_human_actions=[],
        audit_events=[],
        current_node_keys=[],
        metadata={},
    )


def get_node_status(state: WorkflowState, node_key: str) -> str | None:
    """Get status of a specific node.

    Args:
        state: Workflow state
        node_key: Node key

    Returns:
        Node status if set, None otherwise
    """
    return state.get("node_statuses", {}).get(node_key)


def get_node_result(state: WorkflowState, node_key: str) -> dict[str, Any] | None:
    """Get result of a specific node.

    Args:
        state: Workflow state
        node_key: Node key

    Returns:
        Node result if available, None otherwise
    """
    return state.get("node_results", {}).get(node_key)


def get_node_error(state: WorkflowState, node_key: str) -> dict[str, Any] | None:
    """Get error of a specific node.

    Args:
        state: Workflow state
        node_key: Node key

    Returns:
        Node error if available, None otherwise
    """
    return state.get("node_errors", {}).get(node_key)


def is_node_completed(state: WorkflowState, node_key: str) -> bool:
    """Check if a node is completed.

    Args:
        state: Workflow state
        node_key: Node key

    Returns:
        True if node is completed, False otherwise
    """
    status = get_node_status(state, node_key)
    return status == "completed"


def is_node_failed(state: WorkflowState, node_key: str) -> bool:
    """Check if a node has failed.

    Args:
        state: Workflow state
        node_key: Node key

    Returns:
        True if node has failed, False otherwise
    """
    status = get_node_status(state, node_key)
    return status == "failed"
