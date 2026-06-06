import logging
from collections.abc import AsyncIterator
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
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
        instance = await self._get_instance(task.agent_id)
        base_url = self._get_base_url(instance)
        if not base_url:
            raise BadRequestError("Hermes Agent 地址未配置", "errors.task.agent_no_base_url")

        output_dir = self._compute_output_dir(task)

        payload = {
            "task_id": task.id,
            "skill_id": task.skill_id,
            "tool_name": task.tool_name,
            "profile_id": task.profile_id,
            "workspace_id": task.workspace_id,
            "arguments": arguments,
            "output_dir": output_dir,
        }

        timeout = httpx.Timeout(
            connect=settings.HERMES_AGENT_CONNECT_TIMEOUT_SECONDS,
            read=settings.HERMES_AGENT_READ_TIMEOUT_SECONDS,
            write=settings.HERMES_AGENT_READ_TIMEOUT_SECONDS,
            pool=settings.HERMES_AGENT_READ_TIMEOUT_SECONDS,
        )
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(f"{base_url}/v1/runs", json=payload)

        if response.status_code >= 400:
            raise BadRequestError(
                f"Agent 返回错误: {response.status_code}",
                "errors.task.agent_run_error",
            )

        run_data = response.json()
        run_id = run_data.get("run_id") or run_data.get("id") or (run_data.get("data", {}) if isinstance(run_data.get("data"), dict) else {}).get("id")
        if not run_id:
            from app.core.exceptions import TaskAgentRunIdMissingError
            raise TaskAgentRunIdMissingError()
        task.hermes_run_id = run_id
        await self.db.flush()

        return run_data

    async def cancel_run(self, task: HermesTask) -> None:
        if not task.hermes_run_id:
            return
        instance = await self._get_instance(task.agent_id)
        base_url = self._get_base_url(instance)
        if not base_url:
            return

        timeout = httpx.Timeout(
            connect=settings.HERMES_AGENT_CONNECT_TIMEOUT_SECONDS,
            read=settings.HERMES_AGENT_READ_TIMEOUT_SECONDS,
        )
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                await client.delete(f"{base_url}/v1/runs/{task.hermes_run_id}")
            except httpx.HTTPError as exc:
                logger.warning("cancel_run 请求失败: %s", exc)

    async def read_run_events(self, task: HermesTask) -> AsyncIterator[dict]:
        if not task.hermes_run_id:
            return
        instance = await self._get_instance(task.agent_id)
        base_url = self._get_base_url(instance)
        if not base_url:
            return

        timeout = httpx.Timeout(
            connect=settings.HERMES_AGENT_CONNECT_TIMEOUT_SECONDS,
            read=settings.HERMES_AGENT_DEFAULT_TIMEOUT_SECONDS,
        )
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "GET",
                f"{base_url}/v1/runs/{task.hermes_run_id}/events",
            ) as response:
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    import json
                    try:
                        event_data = json.loads(line[6:])
                        yield event_data
                    except json.JSONDecodeError:
                        continue

    async def get_run(self, task: HermesTask) -> dict:
        if not task.hermes_run_id:
            raise BadRequestError("任务尚未关联 Hermes Run", "errors.task.no_hermes_run")
        instance = await self._get_instance(task.agent_id)
        base_url = self._get_base_url(instance)
        if not base_url:
            raise BadRequestError("Hermes Agent 地址未配置", "errors.task.agent_no_base_url")

        timeout = httpx.Timeout(
            connect=settings.HERMES_AGENT_CONNECT_TIMEOUT_SECONDS,
            read=settings.HERMES_AGENT_READ_TIMEOUT_SECONDS,
        )
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(f"{base_url}/v1/runs/{task.hermes_run_id}")

        if response.status_code >= 400:
            raise BadRequestError(
                f"获取 Run 状态失败: {response.status_code}",
                "errors.task.agent_get_run_error",
            )
        return response.json()

    async def get_run_status(self, task: HermesTask) -> dict:
        run_data = await self.get_run(task)
        status = run_data.get("status", "unknown")
        return {"status": status}

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
                "hermes.run.failed": EventType.TASK_FAILED,
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
        advanced_config = instance.advanced_config if hasattr(instance, "advanced_config") else None
        if advanced_config and isinstance(advanced_config, dict):
            hermes_base_url = advanced_config.get("hermes_base_url")
            if hermes_base_url:
                return hermes_base_url.rstrip("/")
            gateway_url = advanced_config.get("gateway_url")
            if gateway_url:
                return gateway_url.rstrip("/")

        if instance.ingress_domain:
            domain = instance.ingress_domain
            if not domain.startswith(("http://", "https://")):
                domain = f"https://{domain}"
            return domain.rstrip("/")
        return None

    @staticmethod
    def _compute_output_dir(task: HermesTask) -> str | None:
        return f".{settings.HERMES_OUTPUT_BASE_DIR_NAME.lstrip('.')}/runs/{task.id}/outputs"

    async def compute_output_dir_for_task(self, task: HermesTask) -> str:
        instance = await self._get_instance(task.agent_id)
        advanced = instance.advanced_config if hasattr(instance, "advanced_config") and instance.advanced_config else {}
        output_dir_mode = advanced.get("output_dir_mode", "relative")

        if output_dir_mode == "absolute":
            from app.services.hermes_skill.artifact_service import ArtifactService
            artifact_service = ArtifactService(self.db)
            outputs_dir = await artifact_service.compute_outputs_dir(task)
            return str(outputs_dir)

        return f".{settings.HERMES_OUTPUT_BASE_DIR_NAME.lstrip('.')}/runs/{task.id}/outputs"

    async def _get_instance(self, agent_id: str) -> Instance:
        stmt = select(Instance).where(
            not_deleted(Instance),
            Instance.id == agent_id,
        )
        result = await self.db.execute(stmt)
        instance = result.scalar_one_or_none()
        if not instance:
            raise NotFoundError("Agent 实例不存在", "errors.task.agent_not_found")
        return instance
