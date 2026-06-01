"""Workflow service - Workflow instance lifecycle management."""

from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.task_orchestrator.enums import WorkflowStatus, NodeStatus
from app.modules.task_orchestrator.errors import WorkflowNotFoundError
from app.modules.task_orchestrator.models import WorkflowInstance, WorkflowNode, WorkflowEvent
from app.modules.task_orchestrator.repositories import WorkflowRepository, EventRepository


class WorkflowService:
    """Service for workflow instance lifecycle management."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.workflow_repo = WorkflowRepository(db)
        self.event_repo = EventRepository(db)

    async def mark_running(self, workflow_id: str) -> WorkflowInstance:
        """Mark workflow as running.

        Args:
            workflow_id: Workflow instance ID

        Returns:
            Updated workflow instance
        """
        return await self.workflow_repo.update_instance_status(
            workflow_id,
            WorkflowStatus.RUNNING.value,
            started_at=datetime.utcnow(),
        )

    async def mark_waiting_human(self, workflow_id: str, node_key: str) -> WorkflowInstance:
        """Mark workflow as waiting for human input.

        Args:
            workflow_id: Workflow instance ID
            node_key: Node key waiting for human

        Returns:
            Updated workflow instance
        """
        instance = await self.workflow_repo.update_instance_status(
            workflow_id, WorkflowStatus.WAITING_HUMAN.value
        )

        # Create event
        event = WorkflowEvent(
            workflow_instance_id=workflow_id,
            event_type="waiting_human",
            event_payload={"node_key": node_key},
        )
        await self.event_repo.create_event(event)

        return instance

    async def mark_blocked(self, workflow_id: str, reason: str, node_key: str | None = None) -> WorkflowInstance:
        """Mark workflow as blocked.

        Args:
            workflow_id: Workflow instance ID
            reason: Block reason
            node_key: Node key that caused block (optional)

        Returns:
            Updated workflow instance
        """
        instance = await self.workflow_repo.update_instance_status(
            workflow_id, WorkflowStatus.BLOCKED.value, error_summary=reason
        )

        # Create event
        event = WorkflowEvent(
            workflow_instance_id=workflow_id,
            event_type="workflow_blocked",
            event_payload={"reason": reason, "node_key": node_key},
        )
        await self.event_repo.create_event(event)

        return instance

    async def mark_completed(self, workflow_id: str) -> WorkflowInstance:
        """Mark workflow as completed.

        Args:
            workflow_id: Workflow instance ID

        Returns:
            Updated workflow instance
        """
        instance = await self.workflow_repo.update_instance_status(
            workflow_id,
            WorkflowStatus.COMPLETED.value,
            completed_at=datetime.utcnow(),
        )

        # Create event
        event = WorkflowEvent(
            workflow_instance_id=workflow_id,
            event_type="workflow_completed",
        )
        await self.event_repo.create_event(event)

        return instance

    async def mark_failed(self, workflow_id: str, error_summary: str) -> WorkflowInstance:
        """Mark workflow as failed.

        Args:
            workflow_id: Workflow instance ID
            error_summary: Error summary

        Returns:
            Updated workflow instance
        """
        instance = await self.workflow_repo.update_instance_status(
            workflow_id,
            WorkflowStatus.FAILED.value,
            completed_at=datetime.utcnow(),
            error_summary=error_summary,
        )

        # Create event
        event = WorkflowEvent(
            workflow_instance_id=workflow_id,
            event_type="workflow_failed",
            event_payload={"error_summary": error_summary},
        )
        await self.event_repo.create_event(event)

        return instance

    async def update_runtime_state(
        self, workflow_id: str, runtime_state: dict[str, Any], current_node_keys: list[str] | None = None
    ) -> WorkflowInstance:
        """Update workflow runtime state.

        Args:
            workflow_id: Workflow instance ID
            runtime_state: Updated runtime state
            current_node_keys: Updated current node keys (optional)

        Returns:
            Updated workflow instance
        """
        return await self.workflow_repo.update_instance_state(
            workflow_id, runtime_state, current_node_keys
        )

    async def create_node(
        self,
        workflow_id: str,
        node_key: str,
        node_type: str,
        executor_type: str,
        role_code: str | None = None,
        timeout_sec: int = 1800,
        input_payload: dict[str, Any] | None = None,
    ) -> WorkflowNode:
        """Create a workflow node.

        Args:
            workflow_id: Workflow instance ID
            node_key: Node key
            node_type: Node type
            executor_type: Executor type
            role_code: Role code (optional)
            timeout_sec: Timeout in seconds
            input_payload: Input payload (optional)

        Returns:
            Created workflow node
        """
        import uuid
        node = WorkflowNode(
            id=str(uuid.uuid4()),
            workflow_instance_id=workflow_id,
            node_key=node_key,
            node_type=node_type,
            role_code=role_code,
            executor_type=executor_type,
            status=NodeStatus.PENDING.value,
            timeout_sec=timeout_sec,
            input_payload=input_payload or {},
        )

        return await self.workflow_repo.create_node(node)

    async def mark_node_running(self, workflow_id: str, node_key: str) -> WorkflowNode:
        """Mark node as running.

        Args:
            workflow_id: Workflow instance ID
            node_key: Node key

        Returns:
            Updated workflow node
        """
        return await self.workflow_repo.update_node_by_key(
            workflow_id,
            node_key,
            status=NodeStatus.RUNNING.value,
            started_at=datetime.utcnow(),
        )

    async def mark_node_completed(
        self, workflow_id: str, node_key: str, output_payload: dict[str, Any]
    ) -> WorkflowNode:
        """Mark node as completed.

        Args:
            workflow_id: Workflow instance ID
            node_key: Node key
            output_payload: Output payload

        Returns:
            Updated workflow node
        """
        return await self.workflow_repo.update_node_by_key(
            workflow_id,
            node_key,
            status=NodeStatus.COMPLETED.value,
            output_payload=output_payload,
            completed_at=datetime.utcnow(),
        )

    async def mark_node_failed(
        self, workflow_id: str, node_key: str, error_payload: dict[str, Any]
    ) -> WorkflowNode:
        """Mark node as failed.

        Args:
            workflow_id: Workflow instance ID
            node_key: Node key
            error_payload: Error payload

        Returns:
            Updated workflow node
        """
        return await self.workflow_repo.update_node_by_key(
            workflow_id,
            node_key,
            status=NodeStatus.FAILED.value,
            error_payload=error_payload,
            completed_at=datetime.utcnow(),
        )
