"""Workflow repository - Workflow instance and node data access layer."""

from datetime import datetime
from typing import Any

from sqlalchemy import select, and_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.base import not_deleted
from app.modules.task_orchestrator.enums import WorkflowStatus, NodeStatus
from app.modules.task_orchestrator.errors import WorkflowNotFoundError, WorkflowNodeNotFoundError
from app.modules.task_orchestrator.models import WorkflowInstance, WorkflowNode


class WorkflowRepository:
    """Repository for workflow instance and node data access."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # Workflow Instance Operations

    async def create_instance(self, instance: WorkflowInstance) -> WorkflowInstance:
        """Create a new workflow instance.

        Args:
            instance: Instance to create

        Returns:
            Created instance
        """
        self.db.add(instance)
        await self.db.flush()
        await self.db.refresh(instance)
        return instance

    async def get_instance_by_id(self, workflow_id: str) -> WorkflowInstance | None:
        """Get workflow instance by ID.

        Args:
            workflow_id: Workflow instance ID

        Returns:
            Instance if found, None otherwise
        """
        stmt = select(WorkflowInstance).where(
            and_(
                WorkflowInstance.id == workflow_id,
                not_deleted(WorkflowInstance),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_instance_by_thread_id(self, thread_id: str) -> WorkflowInstance | None:
        """Get workflow instance by thread ID.

        Args:
            thread_id: LangGraph thread ID

        Returns:
            Instance if found, None otherwise
        """
        stmt = select(WorkflowInstance).where(
            and_(
                WorkflowInstance.thread_id == thread_id,
                not_deleted(WorkflowInstance),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_with_nodes(self, workflow_id: str) -> WorkflowInstance | None:
        """Get workflow instance with all nodes loaded.

        Args:
            workflow_id: Workflow instance ID

        Returns:
            Instance with nodes if found, None otherwise
        """
        stmt = (
            select(WorkflowInstance)
            .where(
                and_(
                    WorkflowInstance.id == workflow_id,
                    not_deleted(WorkflowInstance),
                )
            )
        )
        result = await self.db.execute(stmt)
        instance = result.scalar_one_or_none()

        if instance:
            # Load nodes separately
            nodes = await self.list_nodes(workflow_id)
            # Attach to instance (not a proper relationship, but useful for DTOs)
            instance._nodes = nodes

        return instance

    async def update_instance_status(
        self, workflow_id: str, status: str, **extra_updates
    ) -> WorkflowInstance:
        """Update workflow instance status.

        Args:
            workflow_id: Workflow instance ID
            status: New status
            **extra_updates: Additional fields to update

        Returns:
            Updated instance

        Raises:
            WorkflowNotFoundError: If instance not found
        """
        instance = await self.get_instance_by_id(workflow_id)
        if not instance:
            raise WorkflowNotFoundError(workflow_id)

        instance.status = status
        for field, value in extra_updates.items():
            if hasattr(instance, field):
                setattr(instance, field, value)

        await self.db.flush()
        await self.db.refresh(instance)
        return instance

    async def update_instance_state(
        self, workflow_id: str, runtime_state: dict[str, Any], current_node_keys: list[str] | None = None
    ) -> WorkflowInstance:
        """Update workflow instance runtime state.

        Args:
            workflow_id: Workflow instance ID
            runtime_state: Updated runtime state
            current_node_keys: Updated current node keys (optional)

        Returns:
            Updated instance

        Raises:
            WorkflowNotFoundError: If instance not found
        """
        instance = await self.get_instance_by_id(workflow_id)
        if not instance:
            raise WorkflowNotFoundError(workflow_id)

        instance.runtime_state = runtime_state
        if current_node_keys is not None:
            instance.current_node_keys = current_node_keys

        await self.db.flush()
        await self.db.refresh(instance)
        return instance

    async def list_instances(
        self,
        template_key: str | None = None,
        status: str | None = None,
        org_id: str | None = None,
        workspace_id: str | None = None,
        source_ref_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[WorkflowInstance]:
        """List workflow instances with filters.

        Args:
            template_key: Filter by template key (optional)
            status: Filter by status (optional)
            org_id: Filter by org ID (optional)
            workspace_id: Filter by workspace ID (optional)
            source_ref_id: Filter by source ref ID (optional)
            limit: Maximum number of results
            offset: Result offset

        Returns:
            List of workflow instances
        """
        conditions = [not_deleted(WorkflowInstance)]

        if template_key:
            conditions.append(WorkflowInstance.template_key == template_key)
        if status:
            conditions.append(WorkflowInstance.status == status)
        if org_id:
            conditions.append(WorkflowInstance.org_id == org_id)
        if workspace_id:
            conditions.append(WorkflowInstance.workspace_id == workspace_id)
        if source_ref_id:
            conditions.append(WorkflowInstance.source_ref_id == source_ref_id)

        stmt = (
            select(WorkflowInstance)
            .where(and_(*conditions))
            .order_by(WorkflowInstance.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    # Workflow Node Operations

    async def create_node(self, node: WorkflowNode) -> WorkflowNode:
        """Create a workflow node.

        Args:
            node: Node to create

        Returns:
            Created node
        """
        self.db.add(node)
        await self.db.flush()
        await self.db.refresh(node)
        return node

    async def create_nodes_batch(self, nodes: list[WorkflowNode]) -> list[WorkflowNode]:
        """Create multiple workflow nodes in batch.

        Args:
            nodes: Nodes to create

        Returns:
            Created nodes
        """
        self.db.add_all(nodes)
        await self.db.flush()
        for node in nodes:
            await self.db.refresh(node)
        return nodes

    async def get_node_by_id(self, node_id: str) -> WorkflowNode | None:
        """Get workflow node by ID.

        Args:
            node_id: Node ID

        Returns:
            Node if found, None otherwise
        """
        stmt = select(WorkflowNode).where(
            and_(
                WorkflowNode.id == node_id,
                not_deleted(WorkflowNode),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_node_by_key(self, workflow_id: str, node_key: str) -> WorkflowNode | None:
        """Get workflow node by key.

        Args:
            workflow_id: Workflow instance ID
            node_key: Node key

        Returns:
            Node if found, None otherwise
        """
        stmt = select(WorkflowNode).where(
            and_(
                WorkflowNode.workflow_instance_id == workflow_id,
                WorkflowNode.node_key == node_key,
                not_deleted(WorkflowNode),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_nodes(self, workflow_id: str) -> list[WorkflowNode]:
        """List all nodes for a workflow instance.

        Args:
            workflow_id: Workflow instance ID

        Returns:
            List of nodes
        """
        stmt = (
            select(WorkflowNode)
            .where(
                and_(
                    WorkflowNode.workflow_instance_id == workflow_id,
                    not_deleted(WorkflowNode),
                )
            )
            .order_by(WorkflowNode.created_at)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update_node_status(
        self, node_id: str, status: str, **extra_updates
    ) -> WorkflowNode:
        """Update workflow node status.

        Args:
            node_id: Node ID
            status: New status
            **extra_updates: Additional fields to update

        Returns:
            Updated node

        Raises:
            WorkflowNodeNotFoundError: If node not found
        """
        node = await self.get_node_by_id(node_id)
        if not node:
            raise WorkflowNodeNotFoundError(node.workflow_instance_id, node.node_key)

        node.status = status
        for field, value in extra_updates.items():
            if hasattr(node, field):
                setattr(node, field, value)

        await self.db.flush()
        await self.db.refresh(node)
        return node

    async def update_node_by_key(
        self, workflow_id: str, node_key: str, **updates
    ) -> WorkflowNode:
        """Update workflow node by key.

        Args:
            workflow_id: Workflow instance ID
            node_key: Node key
            **updates: Fields to update

        Returns:
            Updated node

        Raises:
            WorkflowNodeNotFoundError: If node not found
        """
        node = await self.get_node_by_key(workflow_id, node_key)
        if not node:
            raise WorkflowNodeNotFoundError(workflow_id, node_key)

        for field, value in updates.items():
            if hasattr(node, field):
                setattr(node, field, value)

        await self.db.flush()
        await self.db.refresh(node)
        return node

    async def list_running_nodes_with_timeout(self) -> list[WorkflowNode]:
        """List all running nodes that have timed out.

        Returns:
            List of timed out nodes
        """
        now = datetime.utcnow()
        stmt = (
            select(WorkflowNode)
            .where(
                and_(
                    WorkflowNode.status == NodeStatus.RUNNING.value,
                    WorkflowNode.timeout_at < now,
                    not_deleted(WorkflowNode),
                )
            )
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def soft_delete_instance(self, workflow_id: str) -> None:
        """Soft delete a workflow instance and all its nodes.

        Args:
            workflow_id: Workflow instance ID

        Raises:
            WorkflowNotFoundError: If instance not found
        """
        instance = await self.get_instance_by_id(workflow_id)
        if not instance:
            raise WorkflowNotFoundError(workflow_id)

        now = datetime.utcnow()
        instance.deleted_at = now

        # Soft delete all nodes
        nodes = await self.list_nodes(workflow_id)
        for node in nodes:
            node.deleted_at = now

        await self.db.flush()
