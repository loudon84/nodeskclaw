from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.security import get_current_user, require_tenant_access
from app.models.user_cache import UserCache
from app.schemas.common import ApiResponse
from app.schemas.resource import ArtifactResponse, RpaRunResponse
from app.schemas.task import AutomationTaskCreate, AutomationTaskResponse, AutomationTaskUpdate, TaskMessageResponse
from app.services import artifact_service, automation_task_service

router = APIRouter()


@router.get("", response_model=ApiResponse[list[AutomationTaskResponse]])
async def list_tasks(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    tasks = await automation_task_service.list_tasks(db, tenant_id, status=status)
    return ApiResponse(data=[AutomationTaskResponse.model_validate(t) for t in tasks])


@router.post("", response_model=ApiResponse[AutomationTaskResponse])
async def create_task(
    body: AutomationTaskCreate,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    task = await automation_task_service.create_task(db, tenant_id, user, body)
    return ApiResponse(data=AutomationTaskResponse.model_validate(task))


@router.get("/{task_id}", response_model=ApiResponse[AutomationTaskResponse])
async def get_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    task = await automation_task_service.get_task(db, tenant_id, task_id)
    return ApiResponse(data=AutomationTaskResponse.model_validate(task))


@router.patch("/{task_id}", response_model=ApiResponse[AutomationTaskResponse])
async def update_task(
    task_id: str,
    body: AutomationTaskUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    task = await automation_task_service.update_task(db, tenant_id, task_id, body)
    return ApiResponse(data=AutomationTaskResponse.model_validate(task))


@router.post("/{task_id}/submit", response_model=ApiResponse[AutomationTaskResponse])
async def submit_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    task = await automation_task_service.submit_task(db, tenant_id, task_id)
    return ApiResponse(data=AutomationTaskResponse.model_validate(task))


@router.post("/{task_id}/start", response_model=ApiResponse[AutomationTaskResponse])
async def start_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    task = await automation_task_service.start_task(db, tenant_id, task_id)
    return ApiResponse(data=AutomationTaskResponse.model_validate(task))


@router.post("/{task_id}/cancel", response_model=ApiResponse[AutomationTaskResponse])
async def cancel_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    task = await automation_task_service.cancel_task(db, tenant_id, task_id)
    return ApiResponse(data=AutomationTaskResponse.model_validate(task))


@router.post("/{task_id}/retry", response_model=ApiResponse[AutomationTaskResponse])
async def retry_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    task = await automation_task_service.retry_task(db, tenant_id, task_id)
    return ApiResponse(data=AutomationTaskResponse.model_validate(task))


@router.post("/{task_id}/mark-success-manual", response_model=ApiResponse[AutomationTaskResponse])
async def mark_success_manual(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    task = await automation_task_service.mark_success_manual(db, tenant_id, task_id, user)
    return ApiResponse(data=AutomationTaskResponse.model_validate(task))


@router.get("/{task_id}/messages", response_model=ApiResponse[list[TaskMessageResponse]])
async def list_task_messages(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    messages = await automation_task_service.list_task_messages(db, tenant_id, task_id)
    return ApiResponse(data=[TaskMessageResponse.model_validate(m) for m in messages])


@router.get("/{task_id}/runs", response_model=ApiResponse[list[RpaRunResponse]])
async def list_task_runs(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    runs = await automation_task_service.list_task_runs(db, tenant_id, task_id)
    return ApiResponse(data=[RpaRunResponse.model_validate(r) for r in runs])


@router.get("/{task_id}/artifacts", response_model=ApiResponse[list[ArtifactResponse]])
async def list_task_artifacts(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    tenant_id = require_tenant_access(user)
    artifacts = await artifact_service.list_artifacts(db, tenant_id, task_id=task_id)
    return ApiResponse(data=[ArtifactResponse.model_validate(a) for a in artifacts])
