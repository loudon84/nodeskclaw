"""LangGraph commands - Command wrappers for workflow control."""

from typing import Any

from langgraph.types import Command as LangGraphCommand


def create_resume_command(resume_value: dict[str, Any]) -> LangGraphCommand:
    """Create a command to resume a workflow from interrupt.

    This is used to provide human input and resume a workflow that was
    paused at a wait_human_node.

    Args:
        resume_value: Value to provide to the interrupted node

    Returns:
        LangGraph Command object
    """
    return LangGraphCommand(resume=resume_value)


def create_update_command(updates: dict[str, Any]) -> LangGraphCommand:
    """Create a command to update state and continue.

    This is used to update the workflow state without changing the
    execution path.

    Args:
        updates: State updates to apply

    Returns:
        LangGraph Command object
    """
    return LangGraphCommand(update=updates)


def create_goto_command(node_name: str) -> LangGraphCommand:
    """Create a command to jump to a specific node.

    This is used for dynamic routing, such as in gateway nodes
    that need to conditionally route to different paths.

    Args:
        node_name: Name of the node to jump to

    Returns:
        LangGraph Command object
    """
    return LangGraphCommand(goto=node_name)


def create_interrupt_command(interrupt_value: dict[str, Any]) -> LangGraphCommand:
    """Create a command to interrupt the workflow.

    This is used to pause workflow execution and wait for external input.

    Args:
        interrupt_value: Value to pass to the interrupt handler

    Returns:
        LangGraph Command object
    """
    return LangGraphCommand(interrupt=interrupt_value)


class WorkflowCommand:
    """High-level workflow command wrapper.

    This class provides a more intuitive interface for creating
    LangGraph commands in the context of workflow orchestration.
    """

    @staticmethod
    def resume(workflow_instance_id: str, intervention_id: str, response: dict[str, Any]) -> LangGraphCommand:
        """Resume workflow with human intervention response.

        Args:
            workflow_instance_id: Workflow instance ID
            intervention_id: Intervention ID being resolved
            response: Human response data

        Returns:
            Resume command
        """
        resume_value = {
            "workflow_instance_id": workflow_instance_id,
            "intervention_id": intervention_id,
            "response": response,
            "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
        }
        return create_resume_command(resume_value)

    @staticmethod
    def retry_node(node_key: str, reason: str) -> LangGraphCommand:
        """Retry a failed node.

        Args:
            node_key: Node key to retry
            reason: Reason for retry

        Returns:
            Update command with retry information
        """
        updates = {
            "node_statuses": {node_key: "pending"},
            "metadata": {
                "retry_reason": reason,
                "retry_timestamp": __import__("datetime").datetime.utcnow().isoformat(),
            },
        }
        return create_update_command(updates)

    @staticmethod
    def skip_node(node_key: str, reason: str) -> LangGraphCommand:
        """Skip a node.

        Args:
            node_key: Node key to skip
            reason: Reason for skipping

        Returns:
            Update command with skip information
        """
        updates = {
            "node_statuses": {node_key: "skipped"},
            "node_results": {node_key: {"skipped": True, "reason": reason}},
            "metadata": {
                "skip_reason": reason,
                "skip_timestamp": __import__("datetime").datetime.utcnow().isoformat(),
            },
        }
        return create_update_command(updates)

    @staticmethod
    def escalate(node_key: str, reason: str, escalate_to: str | None = None) -> LangGraphCommand:
        """Escalate a node issue.

        Args:
            node_key: Node key with issue
            reason: Reason for escalation
            escalate_to: User or role to escalate to (optional)

        Returns:
            Update command with escalation information
        """
        updates = {
            "node_statuses": {node_key: "escalated"},
            "pending_human_actions": [
                {
                    "type": "escalation",
                    "node_key": node_key,
                    "reason": reason,
                    "escalate_to": escalate_to,
                    "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
                }
            ],
        }
        return create_update_command(updates)

    @staticmethod
    def cancel_workflow(reason: str) -> LangGraphCommand:
        """Cancel the entire workflow.

        Args:
            reason: Reason for cancellation

        Returns:
            Update command with cancellation information
        """
        updates = {
            "metadata": {
                "cancelled": True,
                "cancellation_reason": reason,
                "cancellation_timestamp": __import__("datetime").datetime.utcnow().isoformat(),
            },
        }
        return create_update_command(updates)

    @staticmethod
    def route_to_branch(branch_name: str) -> LangGraphCommand:
        """Route to a specific workflow branch.

        Args:
            branch_name: Name of the branch to route to

        Returns:
            Goto command for the branch
        """
        return create_goto_command(branch_name)


# Convenience aliases
resume_workflow = WorkflowCommand.resume
retry_node = WorkflowCommand.retry_node
skip_node = WorkflowCommand.skip_node
escalate_node = WorkflowCommand.escalate
cancel_workflow = WorkflowCommand.cancel_workflow
route_to_branch = WorkflowCommand.route_to_branch
