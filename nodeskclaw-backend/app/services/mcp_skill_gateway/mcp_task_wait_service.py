import asyncio
import time
from typing import Any

from sqlalchemy import select

from app.core.config import settings
from app.core.deps import async_session_factory
from app.models.base import not_deleted
from app.models.hermes_skill.hermes_task import EventType, HermesTask, TaskStatus
from app.services.hermes_skill.task_result_service import TaskResultService

_TERMINAL_STATUSES = {
    TaskStatus.COMPLETED,
    TaskStatus.FAILED,
    TaskStatus.TIMEOUT,
    TaskStatus.CANCELLED,
}

_FAILURE_STATUSES = {
    TaskStatus.FAILED,
    TaskStatus.TIMEOUT,
    TaskStatus.CANCELLED,
}

_EVENT_TITLES: dict[str, str] = {
    EventType.TASK_CREATED.value: "任务创建",
    EventType.TASK_QUEUED.value: "任务入队",
    EventType.TASK_ACCEPTED.value: "任务已接受",
    EventType.TASK_STARTED.value: "任务开始",
    EventType.TASK_RETRYING.value: "任务重试",
    EventType.TASK_CANCEL_REQUESTED.value: "取消请求",
    EventType.TASK_COMPLETED.value: "任务完成",
    EventType.TASK_FAILED.value: "任务失败",
    EventType.TASK_CANCELLED.value: "任务已取消",
    EventType.TASK_TIMEOUT.value: "任务超时",
    EventType.HERMES_RUN_CREATED.value: "Hermes Run 创建",
    EventType.HERMES_RUN_STARTED.value: "Hermes Run 开始",
    EventType.HERMES_RUN_DELTA.value: "Hermes Run 增量",
    EventType.HERMES_RUN_COMPLETED.value: "Hermes Run 完成",
    EventType.HERMES_RUN_FAILED.value: "Hermes Run 失败",
    EventType.ARTIFACT_SCAN_STARTED.value: "产物扫描开始",
    EventType.ARTIFACT_CREATED.value: "产物创建",
    EventType.ARTIFACT_SCAN_COMPLETED.value: "产物扫描完成",
    EventType.ARTIFACT_SCAN_FAILED.value: "产物扫描失败",
}


class McpTaskWaitService:
    async def wait_for_task_result(
        self,
        task_id: str,
        org_id: str,
        *,
        timeout_seconds: int | None = None,
        poll_interval_seconds: int | None = None,
        include_timeline: bool | None = None,
        include_artifacts: bool | None = None,
    ) -> dict[str, Any]:
        timeout = timeout_seconds if timeout_seconds is not None else settings.MCP_TASK_WAIT_TIMEOUT_SECONDS
        timeout = max(1, min(timeout, settings.MCP_TASK_WAIT_MAX_TIMEOUT_SECONDS))
        poll_interval = poll_interval_seconds if poll_interval_seconds is not None else settings.MCP_TASK_WAIT_POLL_INTERVAL_SECONDS
        poll_interval = max(1, min(poll_interval, 30))
        include_timeline = settings.MCP_TASK_WAIT_RETURN_TIMELINE if include_timeline is None else include_timeline
        include_artifacts = settings.MCP_TASK_WAIT_RETURN_ARTIFACTS if include_artifacts is None else include_artifacts

        deadline = time.monotonic() + timeout
        task_no = task_id

        while time.monotonic() < deadline:
            task = await self._load_task(task_id, org_id)
            if task is None:
                return {
                    "task_id": task_id,
                    "task_no": task_no,
                    "status": "unknown",
                    "ready": False,
                    "isError": True,
                    "error": {"code": "TASK_NOT_FOUND", "message": "任务不存在"},
                    "next_action": "show_failure",
                }
            task_no = task.task_no

            if task.status in _TERMINAL_STATUSES:
                return await self._build_terminal_result(
                    task,
                    include_timeline=include_timeline,
                    include_artifacts=include_artifacts,
                )

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break

            wait_seconds = min(poll_interval, remaining)
            from app.services.hermes_skill.event_bus import EventBus
            notified = await EventBus.get_instance().wait(task_id, timeout=wait_seconds)
            if not notified:
                await asyncio.sleep(0)

        task = await self._load_task(task_id, org_id)
        if task and task.status in _TERMINAL_STATUSES:
            return await self._build_terminal_result(
                task,
                include_timeline=include_timeline,
                include_artifacts=include_artifacts,
            )
        return await self._build_still_running_result(task_id, org_id, task)

    async def build_result_for_task(
        self,
        task: HermesTask,
        *,
        include_timeline: bool | None = None,
        include_artifacts: bool | None = None,
    ) -> dict[str, Any]:
        include_timeline = settings.MCP_TASK_WAIT_RETURN_TIMELINE if include_timeline is None else include_timeline
        include_artifacts = settings.MCP_TASK_WAIT_RETURN_ARTIFACTS if include_artifacts is None else include_artifacts
        if task.status in _TERMINAL_STATUSES:
            return await self._build_terminal_result(
                task,
                include_timeline=include_timeline,
                include_artifacts=include_artifacts,
            )
        return {
            "task_id": task.id,
            "task_no": task.task_no,
            "status": task.status.value,
            "ready": False,
            "message": "任务仍在执行中",
            "next_action": "poll_timeline_or_wait",
            "poll_after_seconds": 5,
        }

    async def _load_task(self, task_id: str, org_id: str) -> HermesTask | None:
        async with async_session_factory() as session:
            result = await session.execute(
                select(HermesTask).where(
                    HermesTask.id == task_id,
                    HermesTask.org_id == org_id,
                    not_deleted(HermesTask),
                )
            )
            return result.scalar_one_or_none()

    async def _build_terminal_result(
        self,
        task: HermesTask,
        *,
        include_timeline: bool,
        include_artifacts: bool,
    ) -> dict[str, Any]:
        if task.status == TaskStatus.COMPLETED:
            return await self._build_completed_result(
                task,
                include_timeline=include_timeline,
                include_artifacts=include_artifacts,
            )
        return self._build_failed_result(task)

    async def _build_completed_result(
        self,
        task: HermesTask,
        *,
        include_timeline: bool,
        include_artifacts: bool,
    ) -> dict[str, Any]:
        async with async_session_factory() as session:
            data = await TaskResultService(session).get_result(task.id, task.org_id)

        timeline = data.get("timeline") or []
        if include_timeline:
            timeline = [
                {
                    "event_type": item.get("event_type"),
                    "title": _EVENT_TITLES.get(item.get("event_type", ""), item.get("event_type")),
                    "timestamp": item.get("created_at"),
                    "payload": item.get("payload"),
                }
                for item in timeline
            ]
        else:
            timeline = []

        server_artifacts = data.get("server_artifacts") or [] if include_artifacts else []

        result: dict[str, Any] = {
            "task_id": task.id,
            "task_no": task.task_no,
            "status": task.status.value,
            "ready": True,
            "result_summary": data.get("result_summary"),
            "artifact_mode": data.get("artifact_mode", "pull_only"),
            "artifact_status": data.get("artifact_status"),
            "kb_status": data.get("kb_status"),
            "server_artifacts": server_artifacts,
            "primary_artifact": data.get("primary_artifact") if include_artifacts else None,
            "timeline": timeline,
            "next_action": "answer_user",
        }
        if settings.MCP_TASK_WAIT_INCLUDE_PRIMARY_PREVIEW and data.get("primary_artifact"):
            result["primary_preview_included"] = True
        return result

    @staticmethod
    def _build_failed_result(task: HermesTask) -> dict[str, Any]:
        return {
            "task_id": task.id,
            "task_no": task.task_no,
            "status": task.status.value,
            "ready": False,
            "isError": True,
            "error": {
                "code": task.error_code or task.status.value.upper(),
                "message": task.error_message or f"任务状态为 {task.status.value}",
            },
            "timeline": [],
            "next_action": "show_failure",
        }

    async def _build_still_running_result(
        self,
        task_id: str,
        org_id: str,
        task: HermesTask | None,
    ) -> dict[str, Any]:
        status = task.status.value if task else "running"
        task_no = task.task_no if task else task_id
        timeline: list[dict[str, Any]] = []
        if task and settings.MCP_TASK_WAIT_RETURN_TIMELINE:
            async with async_session_factory() as session:
                data = await TaskResultService(session).get_result(task.id, org_id)
            timeline = [
                {
                    "event_type": item.get("event_type"),
                    "title": _EVENT_TITLES.get(item.get("event_type", ""), item.get("event_type")),
                    "timestamp": item.get("created_at"),
                }
                for item in (data.get("timeline") or [])[:20]
            ]
        return {
            "task_id": task_id,
            "task_no": task_no,
            "status": status,
            "ready": False,
            "wait_timeout": True,
            "message": "任务仍在执行中，稍后请调用 nodeskclaw_task_wait 查询。",
            "next_tool": "nodeskclaw_task_wait",
            "next_action": "call_task_wait",
            "poll_after_seconds": 15,
            "timeline": timeline,
        }
