"""Template service - Workflow template management."""

from typing import Any
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.task_orchestrator.enums import TemplateStatus
from app.modules.task_orchestrator.errors import WorkflowTemplateNotFoundError
from app.modules.task_orchestrator.models import WorkflowTemplate
from app.modules.task_orchestrator.repositories import TemplateRepository
from app.modules.task_orchestrator.schemas.template import (
    WorkflowTemplateCreateRequest,
    WorkflowTemplateUpdateRequest,
    WorkflowTemplateResponse,
    WorkflowTemplateSummary,
)


class TemplateService:
    """Service for workflow template management."""

    def __init__(self, db: AsyncSession, user: Any = None):
        self.db = db
        self.user = user
        self.template_repo = TemplateRepository(db)

    async def create_template(
        self, request: WorkflowTemplateCreateRequest
    ) -> WorkflowTemplateResponse:
        """Create a new workflow template.

        Args:
            request: Template creation request

        Returns:
            Created template response
        """
        # Check if template with same key and version exists
        existing = await self.template_repo.get_by_key_version(
            request.template_key, request.version
        )
        if existing:
            raise ValueError(
                f"Template {request.template_key} version {request.version} already exists"
            )

        # Create template
        template = WorkflowTemplate(
            id=str(uuid.uuid4()),
            template_key=request.template_key,
            name=request.name,
            version=request.version,
            source_type=request.source_type.value,
            status=TemplateStatus.ACTIVE.value if request.is_active else TemplateStatus.DRAFT.value,
            definition_json=request.definition.model_dump(),
            is_active=request.is_active,
            description=request.description,
            created_by=self.user.id if hasattr(self.user, 'id') else None,
        )

        template = await self.template_repo.create(template)

        return await self._to_response(template)

    async def get_template(self, template_id: str) -> WorkflowTemplateResponse:
        """Get template by ID.

        Args:
            template_id: Template ID

        Returns:
            Template response

        Raises:
            WorkflowTemplateNotFoundError: If template not found
        """
        template = await self.template_repo.get_by_id(template_id)
        if not template:
            raise WorkflowTemplateNotFoundError(template_id)

        return await self._to_response(template)

    async def get_template_by_key(
        self, template_key: str, version: int | None = None
    ) -> WorkflowTemplateResponse:
        """Get template by key and optional version.

        Args:
            template_key: Template key
            version: Template version (optional, defaults to latest)

        Returns:
            Template response

        Raises:
            WorkflowTemplateNotFoundError: If template not found
        """
        if version:
            template = await self.template_repo.get_by_key_version(template_key, version)
        else:
            template = await self.template_repo.get_by_key_latest(template_key)

        if not template:
            raise WorkflowTemplateNotFoundError(template_key, version)

        return await self._to_response(template)

    async def list_templates(
        self,
        source_type: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[WorkflowTemplateSummary], int]:
        """List active templates with pagination.

        Args:
            source_type: Filter by source type (optional)
            page: Page number (1-indexed)
            page_size: Items per page

        Returns:
            Tuple of (template summaries, total count)
        """
        offset = (page - 1) * page_size

        templates = await self.template_repo.list_active(
            source_type=source_type,
            limit=page_size,
            offset=offset,
        )

        total = await self.template_repo.count_active(source_type)

        summaries = [await self._to_summary(t) for t in templates]

        return summaries, total

    async def list_template_versions(
        self, template_key: str, page: int = 1, page_size: int = 20
    ) -> tuple[list[WorkflowTemplateSummary], int]:
        """List all versions of a template.

        Args:
            template_key: Template key
            page: Page number
            page_size: Items per page

        Returns:
            Tuple of (template summaries, total count)
        """
        offset = (page - 1) * page_size

        templates = await self.template_repo.list_versions(
            template_key, limit=page_size, offset=offset
        )

        # Get total count (approximate)
        all_versions = await self.template_repo.list_versions(template_key, limit=1000)
        total = len(all_versions)

        summaries = [await self._to_summary(t) for t in templates]

        return summaries, total

    async def update_template(
        self, template_id: str, request: WorkflowTemplateUpdateRequest
    ) -> WorkflowTemplateResponse:
        """Update a template.

        Args:
            template_id: Template ID
            request: Update request

        Returns:
            Updated template response

        Raises:
            WorkflowTemplateNotFoundError: If template not found
        """
        updates = {}

        if request.name is not None:
            updates["name"] = request.name
        if request.description is not None:
            updates["description"] = request.description
        if request.is_active is not None:
            updates["is_active"] = request.is_active
        if request.status is not None:
            updates["status"] = request.status.value
        if request.definition is not None:
            updates["definition_json"] = request.definition.model_dump()

        template = await self.template_repo.update(template_id, **updates)

        return await self._to_response(template)

    async def activate_template(self, template_id: str) -> WorkflowTemplateResponse:
        """Activate a template.

        Args:
            template_id: Template ID

        Returns:
            Updated template response
        """
        template = await self.template_repo.update_status(
            template_id, TemplateStatus.ACTIVE.value
        )
        template.is_active = True
        await self.db.flush()
        await self.db.refresh(template)

        return await self._to_response(template)

    async def deprecate_template(self, template_id: str) -> WorkflowTemplateResponse:
        """Deprecate a template.

        Args:
            template_id: Template ID

        Returns:
            Updated template response
        """
        template = await self.template_repo.update_status(
            template_id, TemplateStatus.DEPRECATED.value
        )
        template.is_active = False
        await self.db.flush()
        await self.db.refresh(template)

        return await self._to_response(template)

    async def delete_template(self, template_id: str) -> None:
        """Soft delete a template.

        Args:
            template_id: Template ID
        """
        await self.template_repo.soft_delete(template_id)

    async def _to_response(self, template: WorkflowTemplate) -> WorkflowTemplateResponse:
        """Convert template model to response DTO.

        Args:
            template: Template model

        Returns:
            Template response
        """
        return WorkflowTemplateResponse(
            id=template.id,
            template_key=template.template_key,
            name=template.name,
            version=template.version,
            source_type=template.source_type,
            status=template.status,
            definition=template.definition_json,
            is_active=template.is_active,
            description=template.description,
            created_by=template.created_by,
            created_at=template.created_at,
            updated_at=template.updated_at,
        )

    async def _to_summary(self, template: WorkflowTemplate) -> WorkflowTemplateSummary:
        """Convert template model to summary DTO.

        Args:
            template: Template model

        Returns:
            Template summary
        """
        return WorkflowTemplateSummary(
            id=template.id,
            template_key=template.template_key,
            name=template.name,
            version=template.version,
            source_type=template.source_type,
            status=template.status,
            is_active=template.is_active,
            description=template.description,
            created_at=template.created_at,
        )
