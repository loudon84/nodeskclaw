from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.hermes_skill.hermes_task import EventType, HermesTaskEvent
from app.services.hermes_skill.task_event_service import TaskEventService
from app.services.hermes_skill.task_result_service import TaskResultService


class TaskEventPublisher:
    def __init__(self, db: AsyncSession):
        self.db = db
        self._events = TaskEventService(db)

    async def publish(
        self,
        task_id: str,
        org_id: str,
        event_type: EventType,
        payload: dict | None = None,
        *,
        source: str = "backend",
        source_event_seq: int | None = None,
    ) -> HermesTaskEvent:
        return await self._events.write_event(
            task_id=task_id,
            org_id=org_id,
            event_type=event_type,
            payload=payload,
            source=source,
            source_event_seq=source_event_seq,
        )

    async def publish_progress(
        self,
        task_id: str,
        org_id: str,
        *,
        stage: str,
        progress: float | None = None,
        message: str | None = None,
    ) -> HermesTaskEvent:
        payload: dict[str, Any] = {
            "mcp_event": "task.progress",
            "stage": stage,
        }
        if progress is not None:
            payload["progress"] = progress
        if message:
            payload["message"] = message
        return await self.publish(
            task_id,
            org_id,
            EventType.HERMES_RUN_DELTA,
            payload,
            source="publisher",
        )

    async def publish_artifact_ready(
        self,
        task_id: str,
        org_id: str,
        artifact: dict[str, Any],
    ) -> HermesTaskEvent:
        return await self.publish(
            task_id,
            org_id,
            EventType.ARTIFACT_CREATED,
            {
                "mcp_event": "task.artifact.ready",
                "artifact": artifact,
            },
            source="publisher",
        )

    async def publish_completed_with_result(
        self,
        task_id: str,
        org_id: str,
    ) -> HermesTaskEvent:
        result_data = await TaskResultService(self.db).get_result(task_id, org_id)
        artifacts = result_data.get("server_artifacts") or []
        return await self.publish(
            task_id,
            org_id,
            EventType.TASK_COMPLETED,
            {
                "mcp_event": "task.completed",
                "result": {
                    "summary": result_data.get("result_summary"),
                    "artifacts": artifacts,
                    "artifact_mode": result_data.get("artifact_mode"),
                    "kb_status": result_data.get("kb_status"),
                },
            },
            source="publisher",
        )

    @staticmethod
    def extract_progress_from_delta(payload: dict | None) -> dict[str, Any] | None:
        if not payload:
            return None
        inner = payload
        if payload.get("source") == "hermes" and isinstance(payload.get("payload"), dict):
            inner = payload["payload"]
        stage = (
            inner.get("stage")
            or inner.get("step")
            or inner.get("tool_name")
            or inner.get("name")
        )
        if not stage:
            return None
        result: dict[str, Any] = {"stage": str(stage)}
        if inner.get("progress") is not None:
            result["progress"] = inner.get("progress")
        if inner.get("message"):
            result["message"] = inner.get("message")
        return result
