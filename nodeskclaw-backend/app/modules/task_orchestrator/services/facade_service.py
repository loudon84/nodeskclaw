"""Facade service - Unified API entry point for Task Orchestrator."""

from datetime import datetime
from typing import Any
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.task_orchestrator.enums import WorkflowStatus
from app.modules.task_orchestrator.errors import (
    WorkflowNotFoundError,
    InvalidWorkflowStateError,
)
from app.modules.task_orchestrator.models import WorkflowInstance, WorkflowNode
from app.modules.task_orchestrator.repositories import (
    TemplateRepository,
    WorkflowRepository,
    EventRepository,
)
from app.modules.task_orchestrator.schemas.workflow import (
    WorkflowCreateRequest,
    WorkflowCreateResponse,
    WorkflowDetailResponse,
    WorkflowActionResponse,
    RetryNodeRequest,
)
from app.modules.task_orchestrator.schemas.intervention import (
    InterventionCreateRequest,
    InterventionResponse,
)


class TaskOrchestratorFacadeService:
    """Facade service providing unified API for Task Orchestrator.

    This service acts as the single entry point for all workflow operations,
    coordinating between repositories, runtime service, and other services.
    """

    def __init__(self, db: AsyncSession, user: Any):
        self.db = db
        self.user = user
        self.template_repo = TemplateRepository(db)
        self.workflow_repo = WorkflowRepository(db)
        self.event_repo = EventRepository(db)

    async def create_workflow_instance(
        self, request: WorkflowCreateRequest
    ) -> WorkflowCreateResponse:
        """Create a new workflow instance.

        Args:
            request: Workflow creation request

        Returns:
            Workflow creation response with instance ID and thread ID
        """
        # Get template
        template = await self.template_repo.get_by_key_latest(request.template_key)
        if not template:
            from app.modules.task_orchestrator.errors import WorkflowTemplateNotFoundError
            raise WorkflowTemplateNotFoundError(request.template_key)

        # Generate IDs
        workflow_id = str(uuid.uuid4())
        thread_id = workflow_id  # Use workflow_id as thread_id for simplicity

        # Create workflow instance
        instance = WorkflowInstance(
            id=workflow_id,
            template_id=template.id,
            template_key=template.template_key,
            thread_id=thread_id,
            source_type=request.source_type.value,
            source_ref_id=request.source_ref_id,
            org_id=request.org_id,
            workspace_id=request.workspace_id,
            trigger_user_id=self.user.id if hasattr(self.user, 'id') else None,
            status=WorkflowStatus.CREATED.value,
            input_payload=request.input_payload,
            runtime_state={},
            current_node_keys=[],
            source_trace=request.options,
        )

        instance = await self.workflow_repo.create_instance(instance)

        # Create initial event
        from app.modules.task_orchestrator.models import WorkflowEvent
        event = WorkflowEvent(
            workflow_instance_id=workflow_id,
            event_type="workflow_created",
            event_payload={
                "template_key": template.template_key,
                "template_version": template.version,
            },
            trace_id=request.options.get("trace_id"),
            created_by_type="user",
            created_by_id=self.user.id if hasattr(self.user, 'id') else None,
        )
        await self.event_repo.create_event(event)

        # TODO: Trigger runtime service to start execution
        # await self.runtime_service.start(instance)

        return WorkflowCreateResponse(
            workflow_instance_id=workflow_id,
            thread_id=thread_id,
            status=WorkflowStatus.CREATED.value,
        )

    async def get_workflow_instance(self, workflow_id: str) -> WorkflowDetailResponse:
        """Get workflow instance details.

        Args:
            workflow_id: Workflow instance ID

        Returns:
            Workflow instance details

        Raises:
            WorkflowNotFoundError: If workflow not found
        """
        instance = await self.workflow_repo.get_with_nodes(workflow_id)
        if not instance:
            raise WorkflowNotFoundError(workflow_id)

        # Build response
        nodes = getattr(instance, '_nodes', [])
        node_dtos = [
            {
                "id": node.id,
                "node_key": node.node_key,
                "node_type": node.node_type,
                "executor_type": node.executor_type,
                "status": node.status,
                "role_code": node.role_code,
                "assigned_agent_id": node.assigned_agent_id,
                "external_run_id": node.external_run_id,
                "retry_count": node.retry_count,
                "timeout_sec": node.timeout_sec,
                "started_at": node.started_at,
                "completed_at": node.completed_at,
                "blocked_reason": node.blocked_reason,
            }
            for node in nodes
        ]

        return WorkflowDetailResponse(
            id=instance.id,
            template_key=instance.template_key,
            template_id=instance.template_id,
            status=instance.status,
            thread_id=instance.thread_id,
            source_type=instance.source_type,
            source_ref_id=instance.source_ref_id,
            org_id=instance.org_id,
            workspace_id=instance.workspace_id,
            input_payload=instance.input_payload,
            runtime_state=instance.runtime_state,
            current_node_keys=instance.current_node_keys,
            nodes=node_dtos,
            started_at=instance.started_at,
            completed_at=instance.completed_at,
            error_summary=instance.error_summary,
            created_at=instance.created_at,
            updated_at=instance.updated_at,
        )

    async def pause_workflow(self, workflow_id: str, reason: str | None = None) -> WorkflowActionResponse:
        """Pause a running workflow.

        Args:
            workflow_id: Workflow instance ID
            reason: Reason for pausing (optional)

        Returns:
            Workflow action response

        Raises:
            WorkflowNotFoundError: If workflow not found
            InvalidWorkflowStateError: If workflow cannot be paused
        """
        instance = await self.workflow_repo.get_instance_by_id(workflow_id)
        if not instance:
            raise WorkflowNotFoundError(workflow_id)

        if instance.status != WorkflowStatus.RUNNING.value:
            raise InvalidWorkflowStateError(
                workflow_id, instance.status, "pause"
            )

        # Update status
        instance = await self.workflow_repo.update_instance_status(
            workflow_id, WorkflowStatus.PAUSED.value
        )

        # Create event
        from app.modules.task_orchestrator.models import WorkflowEvent
        event = WorkflowEvent(
            workflow_instance_id=workflow_id,
            event_type="workflow_paused",
            event_payload={"reason": reason},
            created_by_type="user",
            created_by_id=self.user.id if hasattr(self.user, 'id') else None,
        )
        await self.event_repo.create_event(event)

        return WorkflowActionResponse(
            workflow_instance_id=workflow_id,
            status=WorkflowStatus.PAUSED.value,
            message="Workflow paused successfully",
        )

    async def resume_workflow(self, workflow_id: str) -> WorkflowActionResponse:
        """Resume a paused workflow.

        Args:
            workflow_id: Workflow instance ID

        Returns:
            Workflow action response

        Raises:
            WorkflowNotFoundError: If workflow not found
            InvalidWorkflowStateError: If workflow cannot be resumed
        """
        instance = await self.workflow_repo.get_instance_by_id(workflow_id)
        if not instance:
            raise WorkflowNotFoundError(workflow_id)

        if instance.status != WorkflowStatus.PAUSED.value:
            raise InvalidWorkflowStateError(
                workflow_id, instance.status, "resume"
            )

        # Update status
        instance = await self.workflow_repo.update_instance_status(
            workflow_id, WorkflowStatus.RUNNING.value
        )

        # Create event
        from app.modules.task_orchestrator.models import WorkflowEvent
        event = WorkflowEvent(
            workflow_instance_id=workflow_id,
            event_type="workflow_resumed",
            created_by_type="user",
            created_by_id=self.user.id if hasattr(self.user, 'id') else None,
        )
        await self.event_repo.create_event(event)

        # TODO: Trigger runtime service to resume execution
        # await self.runtime_service.resume(instance)

        return WorkflowActionResponse(
            workflow_instance_id=workflow_id,
            status=WorkflowStatus.RUNNING.value,
            message="Workflow resumed successfully",
        )

    async def cancel_workflow(self, workflow_id: str, reason: str | None = None) -> WorkflowActionResponse:
        """Cancel a workflow.

        Args:
            workflow_id: Workflow instance ID
            reason: Reason for cancellation (optional)

        Returns:
            Workflow action response

        Raises:
            WorkflowNotFoundError: If workflow not found
        """
        instance = await self.workflow_repo.get_instance_by_id(workflow_id)
        if not instance:
            raise WorkflowNotFoundError(workflow_id)

        # Update status
        instance = await self.workflow_repo.update_instance_status(
            workflow_id,
            WorkflowStatus.CANCELLED.value,
            completed_at=datetime.utcnow(),
            error_summary=reason,
        )

        # Create event
        from app.modules.task_orchestrator.models import WorkflowEvent
        event = WorkflowEvent(
            workflow_instance_id=workflow_id,
            event_type="workflow_cancelled",
            event_payload={"reason": reason},
            created_by_type="user",
            created_by_id=self.user.id if hasattr(self.user, 'id') else None,
        )
        await self.event_repo.create_event(event)

        return WorkflowActionResponse(
            workflow_instance_id=workflow_id,
            status=WorkflowStatus.CANCELLED.value,
            message="Workflow cancelled successfully",
        )

    async def create_intervention(
        self, workflow_id: str, request: InterventionCreateRequest
    ) -> InterventionResponse:
        """Create a human intervention.

        Args:
            workflow_id: Workflow instance ID
            request: Intervention creation request

        Returns:
            Intervention response

        Raises:
            WorkflowNotFoundError: If workflow not found
        """
        instance = await self.workflow_repo.get_instance_by_id(workflow_id)
        if not instance:
            raise WorkflowNotFoundError(workflow_id)

        # Create intervention
        from app.modules.task_orchestrator.models import HumanIntervention
        intervention = HumanIntervention(
            workflow_instance_id=workflow_id,
            workflow_node_id=request.workflow_node_id,
            intervention_type=request.intervention_type.value,
            status="pending",
            requested_by=self.user.id if hasattr(self.user, 'id') else None,
            request_payload=request.request_payload,
        )

        self.db.add(intervention)
        await self.db.flush()
        await self.db.refresh(intervention)

        return InterventionResponse(
            id=intervention.id,
            workflow_instance_id=intervention.workflow_instance_id,
            workflow_node_id=intervention.workflow_node_id,
            intervention_type=intervention.intervention_type,
            status=intervention.status,
            requested_by=intervention.requested_by,
            request_payload=intervention.request_payload,
            response_payload=intervention.response_payload,
            resolved_at=intervention.resolved_at,
            created_at=intervention.created_at,
            updated_at=intervention.updated_at,
        )

    async def retry_node(
        self, workflow_id: str, request: RetryNodeRequest
    ) -> WorkflowActionResponse:
        """Retry a failed node.

        Args:
            workflow_id: Workflow instance ID
            request: Retry node request

        Returns:
            Workflow action response

        Raises:
            WorkflowNotFoundError: If workflow not found
        """
        instance = await self.workflow_repo.get_instance_by_id(workflow_id)
        if not instance:
            raise WorkflowNotFoundError(workflow_id)

        # Get node
        node = await self.workflow_repo.get_node_by_key(workflow_id, request.node_key)
        if not node:
            from app.modules.task_orchestrator.errors import WorkflowNodeNotFoundError
            raise WorkflowNodeNotFoundError(workflow_id, request.node_key)

        # Update node for retry
        node = await self.workflow_repo.update_node_by_key(
            workflow_id,
            request.node_key,
            status="pending",
            retry_count=node.retry_count + 1,
        )

        # Create event
        from app.modules.task_orchestrator.models import WorkflowEvent
        event = WorkflowEvent(
            workflow_instance_id=workflow_id,
            workflow_node_id=node.id,
            event_type="node_retry",
            event_payload={
                "node_key": request.node_key,
                "reason": request.reason,
                "retry_count": node.retry_count,
            },
            created_by_type="user",
            created_by_id=self.user.id if hasattr(self.user, 'id') else None,
        )
        await self.event_repo.create_event(event)

        return WorkflowActionResponse(
            workflow_instance_id=workflow_id,
            status=instance.status,
            message=f"Node {request.node_key} scheduled for retry",
        )
