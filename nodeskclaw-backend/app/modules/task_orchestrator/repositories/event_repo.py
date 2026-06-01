"""Event repository - Workflow event logging and timeline data access."""

from datetime import datetime

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import not_deleted
from app.modules.task_orchestrator.models import WorkflowEvent


class EventRepository:
    """Repository for workflow event data access."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_event(self, event: WorkflowEvent) -> WorkflowEvent:
        """Create a workflow event.

        Args:
            event: Event to create

        Returns:
            Created event
        """
        self.db.add(event)
        await self.db.flush()
        await self.db.refresh(event)
        return event

    async def create_event_batch(self, events: list[WorkflowEvent]) -> list[WorkflowEvent]:
        """Create multiple events in batch.

        Args:
            events: Events to create

        Returns:
            Created events
        """
        self.db.add_all(events)
        await self.db.flush()
        for event in events:
            await self.db.refresh(event)
        return events

    async def get_event_by_id(self, event_id: str) -> WorkflowEvent | None:
        """Get event by ID.

        Args:
            event_id: Event ID

        Returns:
            Event if found, None otherwise
        """
        stmt = select(WorkflowEvent).where(
            and_(
                WorkflowEvent.id == event_id,
                not_deleted(WorkflowEvent),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_events_by_workflow(
        self,
        workflow_id: str,
        event_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[WorkflowEvent]:
        """List events for a workflow instance.

        Args:
            workflow_id: Workflow instance ID
            event_type: Filter by event type (optional)
            limit: Maximum number of results
            offset: Result offset

        Returns:
            List of events
        """
        conditions = [
            WorkflowEvent.workflow_instance_id == workflow_id,
            not_deleted(WorkflowEvent),
        ]

        if event_type:
            conditions.append(WorkflowEvent.event_type == event_type)

        stmt = (
            select(WorkflowEvent)
            .where(and_(*conditions))
            .order_by(WorkflowEvent.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_events_by_node(
        self,
        node_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[WorkflowEvent]:
        """List events for a workflow node.

        Args:
            node_id: Node ID
            limit: Maximum number of results
            offset: Result offset

        Returns:
            List of events
        """
        stmt = (
            select(WorkflowEvent)
            .where(
                and_(
                    WorkflowEvent.workflow_node_id == node_id,
                    not_deleted(WorkflowEvent),
                )
            )
            .order_by(WorkflowEvent.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_events_by_trace_id(
        self,
        trace_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[WorkflowEvent]:
        """List events by trace ID for distributed tracing.

        Args:
            trace_id: Distributed trace ID
            limit: Maximum number of results
            offset: Result offset

        Returns:
            List of events
        """
        stmt = (
            select(WorkflowEvent)
            .where(
                and_(
                    WorkflowEvent.trace_id == trace_id,
                    not_deleted(WorkflowEvent),
                )
            )
            .order_by(WorkflowEvent.created_at)
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_timeline(
        self,
        workflow_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[WorkflowEvent]:
        """Get workflow timeline (all events in chronological order).

        Args:
            workflow_id: Workflow instance ID
            limit: Maximum number of results
            offset: Result offset

        Returns:
            List of events in chronological order
        """
        stmt = (
            select(WorkflowEvent)
            .where(
                and_(
                    WorkflowEvent.workflow_instance_id == workflow_id,
                    not_deleted(WorkflowEvent),
                )
            )
            .order_by(WorkflowEvent.created_at)
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def count_events_by_workflow(
        self,
        workflow_id: str,
        event_type: str | None = None,
    ) -> int:
        """Count events for a workflow instance.

        Args:
            workflow_id: Workflow instance ID
            event_type: Filter by event type (optional)

        Returns:
            Number of events
        """
        conditions = [
            WorkflowEvent.workflow_instance_id == workflow_id,
            not_deleted(WorkflowEvent),
        ]

        if event_type:
            conditions.append(WorkflowEvent.event_type == event_type)

        stmt = select(WorkflowEvent).where(and_(*conditions))
        result = await self.db.execute(stmt)
        return len(list(result.scalars().all()))

    async def get_latest_event_by_type(
        self,
        workflow_id: str,
        event_type: str,
    ) -> WorkflowEvent | None:
        """Get latest event of a specific type for a workflow.

        Args:
            workflow_id: Workflow instance ID
            event_type: Event type

        Returns:
            Latest event if found, None otherwise
        """
        stmt = (
            select(WorkflowEvent)
            .where(
                and_(
                    WorkflowEvent.workflow_instance_id == workflow_id,
                    WorkflowEvent.event_type == event_type,
                    not_deleted(WorkflowEvent),
                )
            )
            .order_by(WorkflowEvent.created_at.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def delete_events_by_workflow(self, workflow_id: str) -> None:
        """Soft delete all events for a workflow instance.

        Args:
            workflow_id: Workflow instance ID
        """
        events = await self.list_events_by_workflow(workflow_id, limit=10000)
        now = datetime.utcnow()
        for event in events:
            event.deleted_at = now
        await self.db.flush()
