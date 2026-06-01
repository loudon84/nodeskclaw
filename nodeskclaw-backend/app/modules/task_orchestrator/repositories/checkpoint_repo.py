"""Checkpoint repository - LangGraph checkpoint persistence."""

from datetime import datetime
from typing import Any

from sqlalchemy import select, and_, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import not_deleted
from app.modules.task_orchestrator.errors import CheckpointError
from app.modules.task_orchestrator.models import CheckpointSnapshot


class CheckpointRepository:
    """Repository for LangGraph checkpoint data access."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def save_checkpoint(
        self,
        workflow_instance_id: str,
        checkpoint_ns: str,
        checkpoint_id: str,
        checkpoint_data: dict[str, Any],
        channel_versions: dict[str, Any] | None = None,
    ) -> CheckpointSnapshot:
        """Save a checkpoint.

        Args:
            workflow_instance_id: Workflow instance ID
            checkpoint_ns: Checkpoint namespace
            checkpoint_id: Checkpoint ID
            checkpoint_data: Checkpoint data
            channel_versions: Channel versions (optional)

        Returns:
            Created checkpoint snapshot
        """
        checkpoint = CheckpointSnapshot(
            workflow_instance_id=workflow_instance_id,
            checkpoint_ns=checkpoint_ns,
            checkpoint_id=checkpoint_id,
            checkpoint_data=checkpoint_data,
            channel_versions=channel_versions or {},
        )
        self.db.add(checkpoint)
        await self.db.flush()
        await self.db.refresh(checkpoint)
        return checkpoint

    async def get_checkpoint_by_id(
        self, checkpoint_id: str
    ) -> CheckpointSnapshot | None:
        """Get checkpoint by ID.

        Args:
            checkpoint_id: Checkpoint ID

        Returns:
            Checkpoint if found, None otherwise
        """
        stmt = select(CheckpointSnapshot).where(
            and_(
                CheckpointSnapshot.checkpoint_id == checkpoint_id,
                not_deleted(CheckpointSnapshot),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_latest_checkpoint(
        self, workflow_instance_id: str, checkpoint_ns: str = ""
    ) -> CheckpointSnapshot | None:
        """Get latest checkpoint for a workflow instance.

        Args:
            workflow_instance_id: Workflow instance ID
            checkpoint_ns: Checkpoint namespace (default: "")

        Returns:
            Latest checkpoint if found, None otherwise
        """
        stmt = (
            select(CheckpointSnapshot)
            .where(
                and_(
                    CheckpointSnapshot.workflow_instance_id == workflow_instance_id,
                    CheckpointSnapshot.checkpoint_ns == checkpoint_ns,
                    not_deleted(CheckpointSnapshot),
                )
            )
            .order_by(CheckpointSnapshot.created_at.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_checkpoint_by_thread(
        self, thread_id: str, checkpoint_ns: str = ""
    ) -> CheckpointSnapshot | None:
        """Get checkpoint by thread ID (alias for workflow_instance_id).

        Args:
            thread_id: Thread ID (same as workflow_instance_id)
            checkpoint_ns: Checkpoint namespace (default: "")

        Returns:
            Latest checkpoint if found, None otherwise
        """
        return await self.get_latest_checkpoint(thread_id, checkpoint_ns)

    async def list_checkpoints(
        self,
        workflow_instance_id: str,
        checkpoint_ns: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[CheckpointSnapshot]:
        """List checkpoints for a workflow instance.

        Args:
            workflow_instance_id: Workflow instance ID
            checkpoint_ns: Filter by namespace (optional)
            limit: Maximum number of results
            offset: Result offset

        Returns:
            List of checkpoints
        """
        conditions = [
            CheckpointSnapshot.workflow_instance_id == workflow_instance_id,
            not_deleted(CheckpointSnapshot),
        ]

        if checkpoint_ns is not None:
            conditions.append(CheckpointSnapshot.checkpoint_ns == checkpoint_ns)

        stmt = (
            select(CheckpointSnapshot)
            .where(and_(*conditions))
            .order_by(CheckpointSnapshot.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update_checkpoint(
        self,
        checkpoint_id: str,
        checkpoint_data: dict[str, Any],
        channel_versions: dict[str, Any] | None = None,
    ) -> CheckpointSnapshot:
        """Update checkpoint data.

        Args:
            checkpoint_id: Checkpoint ID
            checkpoint_data: Updated checkpoint data
            channel_versions: Updated channel versions (optional)

        Returns:
            Updated checkpoint

        Raises:
            CheckpointError: If checkpoint not found
        """
        checkpoint = await self.get_checkpoint_by_id(checkpoint_id)
        if not checkpoint:
            raise CheckpointError(
                thread_id="",
                operation="update",
                reason=f"Checkpoint not found: {checkpoint_id}",
            )

        checkpoint.checkpoint_data = checkpoint_data
        if channel_versions is not None:
            checkpoint.channel_versions = channel_versions

        await self.db.flush()
        await self.db.refresh(checkpoint)
        return checkpoint

    async def delete_checkpoint(self, checkpoint_id: str) -> None:
        """Soft delete a checkpoint.

        Args:
            checkpoint_id: Checkpoint ID
        """
        checkpoint = await self.get_checkpoint_by_id(checkpoint_id)
        if checkpoint:
            checkpoint.deleted_at = datetime.utcnow()
            await self.db.flush()

    async def delete_checkpoints_by_workflow(
        self, workflow_instance_id: str
    ) -> None:
        """Soft delete all checkpoints for a workflow instance.

        Args:
            workflow_instance_id: Workflow instance ID
        """
        checkpoints = await self.list_checkpoints(
            workflow_instance_id, limit=10000
        )
        now = datetime.utcnow()
        for checkpoint in checkpoints:
            checkpoint.deleted_at = now
        await self.db.flush()

    async def count_checkpoints(
        self, workflow_instance_id: str, checkpoint_ns: str | None = None
    ) -> int:
        """Count checkpoints for a workflow instance.

        Args:
            workflow_instance_id: Workflow instance ID
            checkpoint_ns: Filter by namespace (optional)

        Returns:
            Number of checkpoints
        """
        conditions = [
            CheckpointSnapshot.workflow_instance_id == workflow_instance_id,
            not_deleted(CheckpointSnapshot),
        ]

        if checkpoint_ns is not None:
            conditions.append(CheckpointSnapshot.checkpoint_ns == checkpoint_ns)

        stmt = select(CheckpointSnapshot).where(and_(*conditions))
        result = await self.db.execute(stmt)
        return len(list(result.scalars().all()))

    async def get_checkpoint_tuple(
        self, thread_id: str, checkpoint_ns: str = ""
    ) -> tuple[dict[str, Any], dict[str, Any]] | None:
        """Get checkpoint tuple (data, metadata) for LangGraph.

        This method provides the interface expected by LangGraph's BaseCheckpointSaver.

        Args:
            thread_id: Thread ID
            checkpoint_ns: Checkpoint namespace (default: "")

        Returns:
            Tuple of (checkpoint_data, channel_versions) if found, None otherwise
        """
        checkpoint = await self.get_checkpoint_by_thread(thread_id, checkpoint_ns)
        if not checkpoint:
            return None

        return (checkpoint.checkpoint_data, checkpoint.channel_versions)

    async def put_checkpoint_tuple(
        self,
        thread_id: str,
        checkpoint_ns: str,
        checkpoint_id: str,
        checkpoint_data: dict[str, Any],
        channel_versions: dict[str, Any],
    ) -> str:
        """Put checkpoint tuple for LangGraph.

        This method provides the interface expected by LangGraph's BaseCheckpointSaver.

        Args:
            thread_id: Thread ID
            checkpoint_ns: Checkpoint namespace
            checkpoint_id: Checkpoint ID
            checkpoint_data: Checkpoint data
            channel_versions: Channel versions

        Returns:
            Checkpoint ID
        """
        await self.save_checkpoint(
            workflow_instance_id=thread_id,
            checkpoint_ns=checkpoint_ns,
            checkpoint_id=checkpoint_id,
            checkpoint_data=checkpoint_data,
            channel_versions=channel_versions,
        )
        return checkpoint_id
