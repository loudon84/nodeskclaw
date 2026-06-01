"""Runtime service - Graph execution management."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.task_orchestrator.langgraph.state import create_initial_state
from app.modules.task_orchestrator.langgraph.compiled_graph import get_or_build_graph
from app.modules.task_orchestrator.models import WorkflowInstance
from app.modules.task_orchestrator.repositories import TemplateRepository, CheckpointRepository
from app.modules.task_orchestrator.services.checkpoint_service import PostgresCheckpointSaver


class RuntimeService:
    """Service for managing LangGraph runtime execution."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.template_repo = TemplateRepository(db)
        self.checkpoint_repo = CheckpointRepository(db)

    async def start(self, instance: WorkflowInstance) -> dict[str, Any]:
        """Start workflow execution.

        Args:
            instance: Workflow instance to start

        Returns:
            Execution result
        """
        # Get template
        template = await self.template_repo.get_by_id(instance.template_id)
        if not template:
            raise ValueError(f"Template {instance.template_id} not found")

        # Create checkpoint saver
        checkpoint_saver = PostgresCheckpointSaver(self.checkpoint_repo)

        # Get or build compiled graph
        graph = get_or_build_graph(
            template.template_key,
            template.version,
            template.definition_json,
            checkpoint_saver,
        )

        # Create initial state
        initial_state = create_initial_state(
            workflow_instance_id=instance.id,
            thread_id=instance.thread_id,
            template_key=instance.template_key,
            source_ref={
                "type": instance.source_type,
                "ref_id": instance.source_ref_id,
            },
            input_payload=instance.input_payload,
            runtime_context={
                "org_id": instance.org_id,
                "workspace_id": instance.workspace_id,
                "trigger_user_id": instance.trigger_user_id,
            },
        )

        # Execute graph
        config = {"configurable": {"thread_id": instance.thread_id}}

        # Note: In production, this would be async and potentially backgrounded
        result = await graph.ainvoke(initial_state, config)

        return result

    async def resume(self, instance: WorkflowInstance, resume_value: dict[str, Any]) -> dict[str, Any]:
        """Resume workflow execution.

        Args:
            instance: Workflow instance to resume
            resume_value: Value to resume with

        Returns:
            Execution result
        """
        # Get template
        template = await self.template_repo.get_by_id(instance.template_id)
        if not template:
            raise ValueError(f"Template {instance.template_id} not found")

        # Create checkpoint saver
        checkpoint_saver = PostgresCheckpointSaver(self.checkpoint_repo)

        # Get compiled graph
        graph = get_or_build_graph(
            template.template_key,
            template.version,
            template.definition_json,
            checkpoint_saver,
        )

        # Resume execution
        config = {"configurable": {"thread_id": instance.thread_id}}

        from langgraph.types import Command
        result = await graph.ainvoke(Command(resume=resume_value), config)

        return result

    async def get_state(self, instance: WorkflowInstance) -> dict[str, Any]:
        """Get current workflow state.

        Args:
            instance: Workflow instance

        Returns:
            Current state
        """
        # Get template
        template = await self.template_repo.get_by_id(instance.template_id)
        if not template:
            raise ValueError(f"Template {instance.template_id} not found")

        # Create checkpoint saver
        checkpoint_saver = PostgresCheckpointSaver(self.checkpoint_repo)

        # Get compiled graph
        graph = get_or_build_graph(
            template.template_key,
            template.version,
            template.definition_json,
            checkpoint_saver,
        )

        # Get current state
        config = {"configurable": {"thread_id": instance.thread_id}}
        state = await graph.aget_state(config)

        return state.values if hasattr(state, 'values') else {}
