"""Task Orchestrator Admin API Router - Admin-only endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.security import get_current_user
from app.modules.task_orchestrator.schemas.template import (
    WorkflowTemplateCreateRequest,
    WorkflowTemplateUpdateRequest,
    WorkflowTemplateResponse,
    WorkflowTemplateSummary,
)
from app.modules.task_orchestrator.schemas.common import PaginatedResponse
from app.modules.task_orchestrator.services.template_service import TemplateService

router = APIRouter(prefix="/task-orchestrator", tags=["admin-task-orchestrator"])


@router.post("/templates", response_model=WorkflowTemplateResponse)
async def create_template(
    body: WorkflowTemplateCreateRequest,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user),
):
    """Create a new workflow template."""
    service = TemplateService(db, user)
    return await service.create_template(body)


@router.get("/templates/{template_id}", response_model=WorkflowTemplateResponse)
async def get_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user),
):
    """Get template by ID."""
    service = TemplateService(db, user)
    return await service.get_template(template_id)


@router.get("/templates", response_model=PaginatedResponse[WorkflowTemplateSummary])
async def list_templates(
    source_type: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user),
):
    """List active templates."""
    service = TemplateService(db, user)
    items, total = await service.list_templates(source_type, page, page_size)

    return PaginatedResponse.create(items, total, page, page_size)


@router.get("/templates/by-key/{template_key}", response_model=WorkflowTemplateResponse)
async def get_template_by_key(
    template_key: str,
    version: int | None = None,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user),
):
    """Get template by key and optional version."""
    service = TemplateService(db, user)
    return await service.get_template_by_key(template_key, version)


@router.get("/templates/{template_key}/versions", response_model=PaginatedResponse[WorkflowTemplateSummary])
async def list_template_versions(
    template_key: str,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user),
):
    """List all versions of a template."""
    service = TemplateService(db, user)
    items, total = await service.list_template_versions(template_key, page, page_size)

    return PaginatedResponse.create(items, total, page, page_size)


@router.patch("/templates/{template_id}", response_model=WorkflowTemplateResponse)
async def update_template(
    template_id: str,
    body: WorkflowTemplateUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user),
):
    """Update a template."""
    service = TemplateService(db, user)
    return await service.update_template(template_id, body)


@router.post("/templates/{template_id}/activate", response_model=WorkflowTemplateResponse)
async def activate_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user),
):
    """Activate a template."""
    service = TemplateService(db, user)
    return await service.activate_template(template_id)


@router.post("/templates/{template_id}/deprecate", response_model=WorkflowTemplateResponse)
async def deprecate_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user),
):
    """Deprecate a template."""
    service = TemplateService(db, user)
    return await service.deprecate_template(template_id)


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user),
):
    """Delete a template."""
    service = TemplateService(db, user)
    await service.delete_template(template_id)
    return {"success": True, "message": "Template deleted"}
