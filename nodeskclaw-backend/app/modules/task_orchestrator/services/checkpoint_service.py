"""Checkpoint service - PostgresCheckpointSaver for LangGraph."""

from datetime import datetime
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver, CheckpointTuple

from app.modules.task_orchestrator.repositories import CheckpointRepository


class PostgresCheckpointSaver(BaseCheckpointSaver):
    """PostgreSQL-based checkpoint saver for LangGraph.

    This class implements LangGraph's BaseCheckpointSaver interface
    using our CheckpointRepository for persistence.
    """

    def __init__(self, repo: CheckpointRepository):
        self.repo = repo

    async def aget_tuple(self, config: dict[str, Any]) -> CheckpointTuple | None:
        """Get checkpoint tuple for the given config.

        Args:
            config: Configuration containing thread_id

        Returns:
            CheckpointTuple if found, None otherwise
        """
        thread_id = config.get("configurable", {}).get("thread_id")
        checkpoint_ns = config.get("configurable", {}).get("checkpoint_ns", "")

        if not thread_id:
            return None

        # Get latest checkpoint
        checkpoint = await self.repo.get_checkpoint_by_thread(thread_id, checkpoint_ns)
        if not checkpoint:
            return None

        # Return as CheckpointTuple
        return CheckpointTuple(
            config=config,
            checkpoint={
                "id": checkpoint.checkpoint_id,
                **checkpoint.checkpoint_data,
            },
            metadata={
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "created_at": checkpoint.created_at.isoformat(),
            },
            parent_config=None,  # Would need to track parent for full support
        )

    async def aput(
        self,
        config: dict[str, Any],
        checkpoint: dict[str, Any],
        metadata: dict[str, Any],
        new_versions: dict[str, Any],
    ) -> dict[str, Any]:
        """Put a checkpoint.

        Args:
            config: Configuration containing thread_id
            checkpoint: Checkpoint data
            metadata: Checkpoint metadata
            new_versions: New channel versions

        Returns:
            Updated config
        """
        thread_id = config.get("configurable", {}).get("thread_id")
        checkpoint_ns = config.get("configurable", {}).get("checkpoint_ns", "")

        if not thread_id:
            raise ValueError("thread_id is required in config")

        # Extract checkpoint ID
        checkpoint_id = checkpoint.get("id", datetime.utcnow().isoformat())

        # Save checkpoint
        await self.repo.save_checkpoint(
            workflow_instance_id=thread_id,
            checkpoint_ns=checkpoint_ns,
            checkpoint_id=checkpoint_id,
            checkpoint_data=checkpoint,
            channel_versions=new_versions,
        )

        return config

    async def aput_writes(
        self,
        config: dict[str, Any],
        writes: list[tuple[str, Any]],
        task_id: str,
    ) -> None:
        """Put writes for a task.

        This is used for pending writes in LangGraph's execution model.

        Args:
            config: Configuration
            writes: List of writes
            task_id: Task ID
        """
        # For now, we don't implement pending writes
        # This would be needed for full LangGraph support
        pass
