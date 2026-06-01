"""LangGraph nodes - Workflow execution node functions."""

from datetime import datetime
from typing import Any

from langgraph.types import interrupt

from app.modules.task_orchestrator.langgraph.state import WorkflowState


async def dispatch_node(state: WorkflowState, config: dict[str, Any]) -> dict[str, Any]:
    """Dispatch node - Execute a workflow node via executor adapter.

    This node is responsible for:
    1. Reading the current node configuration
    2. Calling the routing service to resolve executor
    3. Submitting the task to the executor adapter
    4. Updating node status and recording audit event

    Args:
        state: Current workflow state
        config: Node configuration (contains node_key, executor_type, etc.)

    Returns:
        State updates
    """
    node_key = config.get("node_key", "unknown")
    node_type = config.get("node_type", "unknown")
    executor_type = config.get("executor_type", "unknown")

    # Get input payload from state or config
    input_payload = state.get("input_payload", {})
    node_input = config.get("input_mapping", {}).get(node_key, input_payload)

    # Record dispatch event
    audit_event = {
        "type": "node_dispatched",
        "node_key": node_key,
        "node_type": node_type,
        "executor_type": executor_type,
        "timestamp": datetime.utcnow().isoformat(),
    }

    # Update node status to running
    node_status_update = {node_key: "running"}

    # In a real implementation, this would:
    # 1. Call routing_service.resolve_executor(node_config, org_id, workspace_id)
    # 2. Get the appropriate adapter
    # 3. Call adapter.submit(submit_context)
    # 4. Store external_run_id and callback_mode

    # For now, return state updates
    return {
        "node_statuses": node_status_update,
        "audit_events": [audit_event],
        "current_node_keys": [node_key],
    }


async def wait_human_node(state: WorkflowState, config: dict[str, Any]) -> dict[str, Any]:
    """Wait for human intervention node.

    This node uses LangGraph's interrupt() primitive to pause execution
    until a human provides input. The workflow can be resumed by providing
    the intervention response.

    Args:
        state: Current workflow state
        config: Node configuration

    Returns:
        State updates after human input is received
    """
    node_key = config.get("node_key", "unknown")
    workflow_instance_id = state.get("workflow_instance_id")

    # Prepare human intervention request
    human_payload = {
        "type": "approval_required",
        "workflow_instance_id": workflow_instance_id,
        "node_key": node_key,
        "request": config.get("human_request", {}),
        "timestamp": datetime.utcnow().isoformat(),
    }

    # Record waiting event
    audit_event = {
        "type": "waiting_human",
        "node_key": node_key,
        "timestamp": datetime.utcnow().isoformat(),
    }

    # Use LangGraph interrupt to pause execution
    # This will block until resume is called with human input
    human_input = interrupt(human_payload)

    # After resume, process human input
    return {
        "node_statuses": {node_key: "completed"},
        "node_results": {node_key: human_input},
        "pending_human_actions": [],  # Clear pending actions
        "audit_events": [
            audit_event,
            {
                "type": "human_resumed",
                "node_key": node_key,
                "timestamp": datetime.utcnow().isoformat(),
            },
        ],
    }


async def finalize_node(state: WorkflowState, config: dict[str, Any]) -> dict[str, Any]:
    """Finalize node - Complete workflow execution.

    This node is called when the workflow reaches its terminal state.
    It records the final audit event and prepares the workflow for completion.

    Args:
        state: Current workflow state
        config: Node configuration

    Returns:
        State updates for finalization
    """
    workflow_instance_id = state.get("workflow_instance_id")
    template_key = state.get("template_key")

    # Check if any nodes failed
    node_errors = state.get("node_errors", {})
    has_failures = len(node_errors) > 0

    # Record completion event
    audit_event = {
        "type": "workflow_completed" if not has_failures else "workflow_failed",
        "workflow_instance_id": workflow_instance_id,
        "template_key": template_key,
        "timestamp": datetime.utcnow().isoformat(),
        "has_failures": has_failures,
    }

    return {
        "audit_events": [audit_event],
        "current_node_keys": [],
    }


async def gateway_node(state: WorkflowState, config: dict[str, Any]) -> dict[str, Any]:
    """Gateway node - Conditional routing based on state.

    This node evaluates conditions and determines which path to take.
    It's used for branching logic in workflows.

    Args:
        state: Current workflow state
        config: Node configuration with condition expression

    Returns:
        State updates (gateway doesn't change state, just routes)
    """
    node_key = config.get("node_key", "unknown")
    condition_expr = config.get("condition_expr", {})

    # Evaluate condition (simplified - real implementation would use expression evaluator)
    # For now, just record that gateway was evaluated
    audit_event = {
        "type": "gateway_evaluated",
        "node_key": node_key,
        "timestamp": datetime.utcnow().isoformat(),
    }

    return {
        "audit_events": [audit_event],
    }


async def error_handler_node(state: WorkflowState, config: dict[str, Any]) -> dict[str, Any]:
    """Error handler node - Handle node failures.

    This node is called when a node fails and needs error handling.
    It can retry, escalate, or mark the workflow as failed.

    Args:
        state: Current workflow state
        config: Error configuration

    Returns:
        State updates for error handling
    """
    node_key = config.get("node_key", "unknown")
    error = config.get("error", {})
    retry_count = config.get("retry_count", 0)
    max_retries = config.get("max_retries", 2)

    audit_events = []

    if retry_count < max_retries:
        # Retry
        audit_events.append({
            "type": "node_retry_scheduled",
            "node_key": node_key,
            "retry_count": retry_count + 1,
            "timestamp": datetime.utcnow().isoformat(),
        })
        node_status = "pending"  # Will be picked up for retry
    else:
        # Max retries exhausted, mark as failed
        audit_events.append({
            "type": "node_failed",
            "node_key": node_key,
            "error": error,
            "timestamp": datetime.utcnow().isoformat(),
        })
        node_status = "failed"

    return {
        "node_statuses": {node_key: node_status},
        "node_errors": {node_key: error},
        "audit_events": audit_events,
    }


async def timeout_check_node(state: WorkflowState, config: dict[str, Any]) -> dict[str, Any]:
    """Timeout check node - Check for node timeouts.

    This node checks if any running nodes have exceeded their timeout.
    If so, it triggers error handling.

    Args:
        state: Current workflow state
        config: Node configuration

    Returns:
        State updates if timeout detected
    """
    node_key = config.get("node_key", "unknown")
    timeout_sec = config.get("timeout_sec", 1800)
    started_at = config.get("started_at")

    if not started_at:
        return {}

    # Check if timeout exceeded
    now = datetime.utcnow()
    elapsed = (now - started_at).total_seconds()

    if elapsed > timeout_sec:
        audit_event = {
            "type": "node_timeout",
            "node_key": node_key,
            "elapsed_sec": elapsed,
            "timeout_sec": timeout_sec,
            "timestamp": now.isoformat(),
        }

        return {
            "node_statuses": {node_key: "timeout"},
            "node_errors": {node_key: {"type": "timeout", "elapsed_sec": elapsed}},
            "audit_events": [audit_event],
        }

    return {}
