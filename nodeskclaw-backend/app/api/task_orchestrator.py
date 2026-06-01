"""Task Orchestrator API Router - User-facing endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.security import get_current_user
from app.modules.task_orchestrator.schemas.workflow import (
    WorkflowCreateRequest,
    WorkflowCreateResponse,
    WorkflowDetailResponse,
    WorkflowTimelineResponse,
    WorkflowActionResponse,
    RetryNodeRequest,
)
from app.modules.task_orchestrator.schemas.intervention import (
    InterventionCreateRequest,
    InterventionResponse,
)
from app.modules.task_orchestrator.schemas.common import PaginatedResponse
from app.modules.task_orchestrator.services.facade_service import TaskOrchestratorFacadeService

router = APIRouter(prefix="/task-orchestrator", tags=["task-orchestrator"])


@router.post("/workflow-instances", response_model=WorkflowCreateResponse)
async def create_workflow_instance(
    body: WorkflowCreateRequest,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user),
):
    """Create a new workflow instance."""
    service = TaskOrchestratorFacadeService(db, user)
    return await service.create_workflow_instance(body)


@router.get("/workflow-instances/{workflow_id}", response_model=WorkflowDetailResponse)
async def get_workflow_instance(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user),
):
    """Get workflow instance details."""
    service = TaskOrchestratorFacadeService(db, user)
    return await service.get_workflow_instance(workflow_id)


@router.get("/workflow-instances/{workflow_id}/timeline", response_model=WorkflowTimelineResponse)
async def get_workflow_timeline(
    workflow_id: str,
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user),
):
    """Get workflow timeline."""
    from app.modules.task_orchestrator.repositories import EventRepository
    from app.modules.task_orchestrator.schemas.workflow import WorkflowTimelineEvent

    repo = EventRepository(db)
    events = await repo.get_timeline(workflow_id, limit=limit, offset=offset)
    total = await repo.count_events_by_workflow(workflow_id)

    event_dtos = [
        WorkflowTimelineEvent(
            id=e.id,
            workflow_instance_id=e.workflow_instance_id,
            workflow_node_id=e.workflow_node_id,
            event_type=e.event_type,
            event_payload=e.event_payload,
            trace_id=e.trace_id,
            created_at=e.created_at,
        )
        for e in events
    ]

    return WorkflowTimelineResponse(
        workflow_instance_id=workflow_id,
        events=event_dtos,
        total=total,
    )


@router.post("/workflow-instances/{workflow_id}/pause", response_model=WorkflowActionResponse)
async def pause_workflow(
    workflow_id: str,
    reason: str | None = None,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user),
):
    """Pause a running workflow."""
    service = TaskOrchestratorFacadeService(db, user)
    return await service.pause_workflow(workflow_id, reason)


@router.post("/workflow-instances/{workflow_id}/resume", response_model=WorkflowActionResponse)
async def resume_workflow(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user),
):
    """Resume a paused workflow."""
    service = TaskOrchestratorFacadeService(db, user)
    return await service.resume_workflow(workflow_id)


@router.post("/workflow-instances/{workflow_id}/cancel", response_model=WorkflowActionResponse)
async def cancel_workflow(
    workflow_id: str,
    reason: str | None = None,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user),
):
    """Cancel a workflow."""
    service = TaskOrchestratorFacadeService(db, user)
    return await service.cancel_workflow(workflow_id, reason)


@router.post("/workflow-instances/{workflow_id}/interventions", response_model=InterventionResponse)
async def create_intervention(
    workflow_id: str,
    body: InterventionCreateRequest,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user),
):
    """Create a human intervention."""
    service = TaskOrchestratorFacadeService(db, user)
    return await service.create_intervention(workflow_id, body)


@router.post("/workflow-instances/{workflow_id}/retry-node", response_model=WorkflowActionResponse)
async def retry_node(
    workflow_id: str,
    body: RetryNodeRequest,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user),
):
    """Retry a failed node."""
    service = TaskOrchestratorFacadeService(db, user)
    return await service.retry_node(workflow_id, body)


@router.post("/callbacks/{executor_type}/{workflow_id}", response_model=WorkflowActionResponse)
async def handle_executor_callback(
    executor_type: str,
    workflow_id: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user),
):
    """Handle executor callback."""
    # TODO: Implement callback handling
    # 1. Validate callback signature
    # 2. Update node status
    # 3. Trigger PaperClip sync if needed

    return WorkflowActionResponse(
        workflow_instance_id=workflow_id,
        status="callback_received",
        message=f"Callback from {executor_type} received",
    )
