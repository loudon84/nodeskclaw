"""Template repository - Workflow template data access layer."""

from datetime import datetime

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import not_deleted
from app.modules.task_orchestrator.enums import TemplateStatus
from app.modules.task_orchestrator.errors import WorkflowTemplateNotFoundError
from app.modules.task_orchestrator.models import WorkflowTemplate


class TemplateRepository:
    """Repository for workflow template data access."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, template: WorkflowTemplate) -> WorkflowTemplate:
        """Create a new workflow template.

        Args:
            template: Template to create

        Returns:
            Created template
        """
        self.db.add(template)
        await self.db.flush()
        await self.db.refresh(template)
        return template

    async def get_by_id(self, template_id: str) -> WorkflowTemplate | None:
        """Get template by ID.

        Args:
            template_id: Template ID

        Returns:
            Template if found, None otherwise
        """
        stmt = select(WorkflowTemplate).where(
            and_(
                WorkflowTemplate.id == template_id,
                not_deleted(WorkflowTemplate),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_key_version(
        self, template_key: str, version: int = 1
    ) -> WorkflowTemplate | None:
        """Get template by key and version.

        Args:
            template_key: Template key
            version: Template version

        Returns:
            Template if found, None otherwise
        """
        stmt = select(WorkflowTemplate).where(
            and_(
                WorkflowTemplate.template_key == template_key,
                WorkflowTemplate.version == version,
                not_deleted(WorkflowTemplate),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_key_latest(self, template_key: str) -> WorkflowTemplate | None:
        """Get latest version of template by key.

        Args:
            template_key: Template key

        Returns:
            Latest template version if found, None otherwise
        """
        stmt = (
            select(WorkflowTemplate)
            .where(
                and_(
                    WorkflowTemplate.template_key == template_key,
                    WorkflowTemplate.is_active == True,
                    not_deleted(WorkflowTemplate),
                )
            )
            .order_by(WorkflowTemplate.version.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_active(
        self,
        source_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[WorkflowTemplate]:
        """List active templates.

        Args:
            source_type: Filter by source type (optional)
            limit: Maximum number of results
            offset: Result offset

        Returns:
            List of active templates
        """
        conditions = [
            WorkflowTemplate.is_active == True,
            WorkflowTemplate.status == TemplateStatus.ACTIVE.value,
            not_deleted(WorkflowTemplate),
        ]

        if source_type:
            conditions.append(WorkflowTemplate.source_type == source_type)

        stmt = (
            select(WorkflowTemplate)
            .where(and_(*conditions))
            .order_by(WorkflowTemplate.template_key, WorkflowTemplate.version.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_versions(
        self, template_key: str, limit: int = 100, offset: int = 0
    ) -> list[WorkflowTemplate]:
        """List all versions of a template.

        Args:
            template_key: Template key
            limit: Maximum number of results
            offset: Result offset

        Returns:
            List of template versions
        """
        stmt = (
            select(WorkflowTemplate)
            .where(
                and_(
                    WorkflowTemplate.template_key == template_key,
                    not_deleted(WorkflowTemplate),
                )
            )
            .order_by(WorkflowTemplate.version.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update_status(
        self, template_id: str, status: str
    ) -> WorkflowTemplate:
        """Update template status.

        Args:
            template_id: Template ID
            status: New status

        Returns:
            Updated template

        Raises:
            WorkflowTemplateNotFoundError: If template not found
        """
        template = await self.get_by_id(template_id)
        if not template:
            raise WorkflowTemplateNotFoundError(template_id)

        template.status = status
        await self.db.flush()
        await self.db.refresh(template)
        return template

    async def update(
        self, template_id: str, **updates
    ) -> WorkflowTemplate:
        """Update template fields.

        Args:
            template_id: Template ID
            **updates: Fields to update

        Returns:
            Updated template

        Raises:
            WorkflowTemplateNotFoundError: If template not found
        """
        template = await self.get_by_id(template_id)
        if not template:
            raise WorkflowTemplateNotFoundError(template_id)

        for field, value in updates.items():
            if hasattr(template, field):
                setattr(template, field, value)

        await self.db.flush()
        await self.db.refresh(template)
        return template

    async def soft_delete(self, template_id: str) -> None:
        """Soft delete a template.

        Args:
            template_id: Template ID

        Raises:
            WorkflowTemplateNotFoundError: If template not found
        """
        template = await self.get_by_id(template_id)
        if not template:
            raise WorkflowTemplateNotFoundError(template_id)

        template.deleted_at = datetime.utcnow()
        await self.db.flush()

    async def count_active(self, source_type: str | None = None) -> int:
        """Count active templates.

        Args:
            source_type: Filter by source type (optional)

        Returns:
            Number of active templates
        """
        conditions = [
            WorkflowTemplate.is_active == True,
            WorkflowTemplate.status == TemplateStatus.ACTIVE.value,
            not_deleted(WorkflowTemplate),
        ]

        if source_type:
            conditions.append(WorkflowTemplate.source_type == source_type)

        stmt = select(WorkflowTemplate).where(and_(*conditions))
        result = await self.db.execute(stmt)
        return len(list(result.scalars().all()))
