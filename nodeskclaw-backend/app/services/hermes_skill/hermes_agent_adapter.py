import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, BadRequestError
from app.models.base import not_deleted
from app.models.hermes_skill.hermes_task import HermesTask, TaskStatus, EventType
from app.models.instance import Instance

logger = logging.getLogger(__name__)


class HermesAgentAdapter:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def submit_run(
        self,
        task: HermesTask,
        arguments: dict,
    ) -> dict:
        stmt = select(Instance).where(
            not_deleted(Instance),
            Instance.id == task.agent_id,
        )
        result = await self.db.execute(stmt)
        instance = result.scalar_one_or_none()
        if not instance:
            raise NotFoundError("Agent 实例不存在", "errors.task.agent_not_found")

        base_url = self._get_base_url(instance)
        if not base_url:
            raise BadRequestError("Agent 缺少 base_url", "errors.task.agent_no_base_url")

        payload = {
            "run_id": task.id,
            "skill_id": task.skill_id,
            "tool_name": task.tool_name,
            "arguments": arguments,
        }

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(f"{base_url}/v1/runs", json=payload)

        if response.status_code >= 400:
            raise BadRequestError(
                f"Agent 返回错误: {response.status_code}",
                "errors.task.agent_run_error",
            )

        run_data = response.json()
        task.hermes_run_id = run_data.get("run_id", task.hermes_run_id)
        await self.db.flush()

        return run_data

    @staticmethod
    def convert_events(hermes_events: list[dict]) -> list[dict]:
        converted = []
        for event in hermes_events:
            hermes_type = event.get("event_type", "")
            event_seq = event.get("event_seq", 0)
            payload = event.get("payload", {})

            mapping = {
                "hermes.run.created": EventType.HERMES_RUN_CREATED,
                "hermes.run.started": EventType.HERMES_RUN_STARTED,
                "hermes.run.delta": EventType.HERMES_RUN_DELTA,
                "hermes.run.completed": EventType.HERMES_RUN_COMPLETED,
            }

            task_event_type = mapping.get(hermes_type)
            if not task_event_type:
                continue

            if hermes_type == "hermes.run.completed":
                status = payload.get("status", "completed")
                if status == "failed":
                    task_event_type = EventType.TASK_FAILED
                else:
                    task_event_type = EventType.TASK_COMPLETED

            converted.append({
                "event_type": task_event_type,
                "event_seq": event_seq,
                "payload": payload,
            })

        return converted

    @staticmethod
    def _get_base_url(instance: Instance) -> str | None:
        if instance.ingress_domain:
            scheme = "https" if instance.ingress_domain.startswith("https://") else "http"
            domain = instance.ingress_domain
            if not domain.startswith(("http://", "https://")):
                domain = f"https://{domain}"
            return domain.rstrip("/")
        return None
