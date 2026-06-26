from typing import Any

from app.services.mcp_skill_gateway.mcp_task_wait_service import McpTaskWaitService

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ArtifactPreviewUnsupportedError, BadRequestError
from app.models.base import not_deleted
from app.models.hermes_skill.hermes_artifact import HermesArtifact
from app.models.hermes_skill.hermes_task import EventType, HermesTask, TaskStatus
from app.services.hermes_skill.artifact_service import ArtifactService
from app.services.hermes_skill.skill_audit_logger import SkillAuditLogger
from app.services.hermes_skill.task_event_service import TaskEventService
from app.services.hermes_skill.task_result_service import TaskResultService
from app.services.mcp_skill_gateway.auth import McpAuthContext
from app.services.mcp_skill_gateway.mcp_task_access_service import McpTaskAccessService
from app.services.mcp_skill_gateway.server_artifact_service import ServerArtifactService

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

_RUNNING_STATUSES = {
    TaskStatus.QUEUED,
    TaskStatus.ACCEPTED,
    TaskStatus.RUNNING,
    TaskStatus.WAITING_APPROVAL,
}

_FAILURE_STATUSES = {
    TaskStatus.FAILED,
    TaskStatus.TIMEOUT,
    TaskStatus.CANCELLED,
}


def _next_action_for_status(status: TaskStatus) -> str:
    if status == TaskStatus.COMPLETED:
        return "call_task_result"
    if status in _FAILURE_STATUSES:
        return "show_failure"
    return "poll_timeline_or_wait"


class BuiltinTaskToolExecutor:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.access = McpTaskAccessService(db)
        self.audit = SkillAuditLogger(db)

    async def call(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        auth_ctx: McpAuthContext,
    ) -> dict[str, Any]:
        if tool_name == "nodeskclaw_task_timeline":
            return await self._task_timeline(arguments, auth_ctx)
        if tool_name == "nodeskclaw_task_result":
            return await self._task_result(arguments, auth_ctx)
        if tool_name == "nodeskclaw_task_artifacts":
            return await self._task_artifacts(arguments, auth_ctx)
        if tool_name == "nodeskclaw_artifact_preview":
            return await self._artifact_preview(arguments, auth_ctx)
        if tool_name == "nodeskclaw_artifact_download_info":
            return await self._artifact_download_info(arguments, auth_ctx)
        if tool_name == "nodeskclaw_task_wait":
            return await self._task_wait(arguments, auth_ctx)
        raise BadRequestError(f"未知内置工具 {tool_name}", "errors.skill.tool_not_found")

    async def _task_timeline(
        self,
        arguments: dict[str, Any],
        auth_ctx: McpAuthContext,
    ) -> dict[str, Any]:
        task_id = str(arguments.get("task_id") or "").strip()
        limit = int(arguments.get("limit") or 50)
        limit = max(1, min(limit, 200))

        task = await self.access.assert_can_access_task(task_id, auth_ctx)
        events = await TaskEventService(self.db).get_events(task_id, auth_ctx.org.id)
        items = []
        for event in events[:limit]:
            items.append({
                "event_seq": event.event_seq,
                "event_type": event.event_type.value,
                "title": _EVENT_TITLES.get(event.event_type.value, event.event_type.value),
                "timestamp": event.created_at.isoformat() if event.created_at else None,
                "payload": event.payload,
            })

        structured = {
            "task_id": task.id,
            "task_no": task.task_no,
            "status": task.status.value,
            "items": items,
            "next_action": _next_action_for_status(task.status),
        }
        summary = (
            f"任务 {task.task_no} 当前状态：{task.status.value}。"
            f"共 {len(items)} 条时间线事件。"
        )
        if task.status in _RUNNING_STATUSES:
            summary += "建议继续查询进度或等待任务完成。"

        await self._log_audit(
            "mcp.task.timeline.viewed",
            task.id,
            auth_ctx,
            {"task_id": task.id, "task_no": task.task_no, "status": task.status.value},
        )
        return self._wrap_result(summary, structured)

    async def _task_result(
        self,
        arguments: dict[str, Any],
        auth_ctx: McpAuthContext,
    ) -> dict[str, Any]:
        task_id = str(arguments.get("task_id") or "").strip()
        include_timeline = bool(arguments.get("include_timeline", True))
        include_artifacts = bool(arguments.get("include_artifacts", True))

        task = await self.access.assert_can_access_task(task_id, auth_ctx)
        org_id = auth_ctx.org.id

        if task.status in _RUNNING_STATUSES:
            structured = {
                "task": {
                    "id": task.id,
                    "task_no": task.task_no,
                    "status": task.status.value,
                    "tool_name": task.tool_name,
                },
                "ready": False,
                "message": "任务仍在执行中",
                "next_action": "poll_timeline_or_wait",
                "poll_after_seconds": 5,
            }
            summary = (
                f"任务 {task.task_no} 当前状态：{task.status.value}，尚未完成。"
                "建议 5 秒后继续查询。"
            )
            await self._log_audit(
                "mcp.task.result.viewed",
                task.id,
                auth_ctx,
                {"task_id": task.id, "task_no": task.task_no, "status": task.status.value, "ready": False},
            )
            return self._wrap_result(summary, structured)

        if task.status in _FAILURE_STATUSES:
            structured = {
                "task": {
                    "id": task.id,
                    "task_no": task.task_no,
                    "status": task.status.value,
                    "tool_name": task.tool_name,
                },
                "ready": False,
                "error": {
                    "code": task.error_code or task.status.value.upper(),
                    "message": task.error_message or f"任务状态为 {task.status.value}",
                },
                "next_action": "show_failure",
            }
            summary = f"任务 {task.task_no} 失败，状态：{task.status.value}。"
            await self._log_audit(
                "mcp.task.result.viewed",
                task.id,
                auth_ctx,
                {"task_id": task.id, "task_no": task.task_no, "status": task.status.value, "ready": False},
            )
            return self._wrap_result(summary, structured)

        full = await TaskResultService(self.db).get_result(task_id, org_id)
        task_info = full.get("task") or {}
        server_artifacts = full.get("server_artifacts") or [] if include_artifacts else []
        structured: dict[str, Any] = {
            "task": task_info,
            "ready": True,
            "result_summary": full.get("result_summary"),
            "artifact_mode": full.get("artifact_mode", "pull_only"),
            "artifact_status": full.get("artifact_status"),
            "kb_status": full.get("kb_status"),
            "server_artifacts": server_artifacts,
            "next_action": "preview_artifact" if server_artifacts else "show_failure",
        }
        if include_timeline:
            structured["timeline"] = full.get("timeline") or []

        artifact_count = len(server_artifacts)
        summary = f"任务 {task.task_no} 已完成。"
        if artifact_count:
            names = "、".join(a.get("name", "") for a in server_artifacts[:3])
            summary += f"已生成 {artifact_count} 个中心产物：{names}。"
            first_id = server_artifacts[0].get("artifact_id")
            if first_id:
                summary += f"可调用 nodeskclaw_artifact_preview 预览 artifact_id={first_id}。"
        else:
            summary += "暂无中心产物。"

        await self._log_audit(
            "mcp.task.result.viewed",
            task.id,
            auth_ctx,
            {"task_id": task.id, "task_no": task.task_no, "status": task.status.value, "ready": True},
        )
        return self._wrap_result(summary, structured)

    async def _task_artifacts(
        self,
        arguments: dict[str, Any],
        auth_ctx: McpAuthContext,
    ) -> dict[str, Any]:
        task_id = str(arguments.get("task_id") or "").strip()
        server_only = bool(arguments.get("server_only", True))

        task = await self.access.assert_can_access_task(task_id, auth_ctx)
        org_id = auth_ctx.org.id
        server_artifacts = list(task.server_artifacts or [])
        if not server_artifacts:
            server_artifacts = await self._materialized_server_artifacts(task_id, org_id)

        discovery_artifacts: list[dict[str, Any]] = []
        if not server_only:
            discovery_artifacts = await self._discovery_artifact_dicts(task_id, org_id)

        structured = {
            "task_id": task.id,
            "artifact_mode": "pull_only",
            "server_artifacts": server_artifacts,
            "artifacts": discovery_artifacts,
        }
        summary = (
            f"任务 {task.task_no} 共有 {len(server_artifacts)} 个中心产物。"
        )
        await self._log_audit(
            "mcp.task.artifacts.viewed",
            task.id,
            auth_ctx,
            {"task_id": task.id, "task_no": task.task_no, "count": len(server_artifacts)},
        )
        return self._wrap_result(summary, structured)

    async def _artifact_preview(
        self,
        arguments: dict[str, Any],
        auth_ctx: McpAuthContext,
    ) -> dict[str, Any]:
        artifact_id = str(arguments.get("artifact_id") or "").strip()
        max_chars = int(arguments.get("max_chars") or 12000)
        max_chars = max(1000, min(max_chars, settings.MCP_TASK_PREVIEW_MAX_CHARS))

        artifact = await self.access.assert_can_access_artifact(artifact_id, auth_ctx)
        org_id = auth_ctx.org.id
        user_id = auth_ctx.user.id if auth_ctx.auth_type == "user_jwt" else None

        try:
            artifact, content, truncated, preview_type = await ArtifactService(self.db).preview(
                artifact_id,
                org_id,
                user_id=user_id,
            )
        except ArtifactPreviewUnsupportedError:
            structured = {
                "artifact_id": artifact.id,
                "name": artifact.file_name,
                "preview_type": "preview_unsupported",
                "content_type": artifact.content_type,
                "download_url": f"/api/v1/hermes/artifacts/{artifact.id}/download",
                "kb_status": artifact.kb_status,
            }
            summary = f"产物 {artifact.file_name} 不支持预览，请使用下载链接获取文件。"
            await self._log_audit(
                "mcp.artifact.previewed",
                artifact.id,
                auth_ctx,
                {"artifact_id": artifact.id, "preview_type": "preview_unsupported"},
            )
            return self._wrap_result(summary, structured)

        if len(content) > max_chars:
            content = content[:max_chars]
            truncated = True

        structured = {
            "artifact_id": artifact.id,
            "name": artifact.file_name,
            "content_type": artifact.content_type,
            "preview_type": preview_type,
            "content": content,
            "truncated": truncated,
            "size_bytes": artifact.size_bytes,
            "download_url": f"/api/v1/hermes/artifacts/{artifact.id}/download",
            "kb_status": artifact.kb_status,
        }
        summary = f"产物 {artifact.file_name} 预览"
        if truncated:
            summary += "（内容已截断）"
        await self._log_audit(
            "mcp.artifact.previewed",
            artifact.id,
            auth_ctx,
            {"artifact_id": artifact.id, "truncated": truncated},
        )
        return self._wrap_result(summary, structured)

    async def _artifact_download_info(
        self,
        arguments: dict[str, Any],
        auth_ctx: McpAuthContext,
    ) -> dict[str, Any]:
        artifact_id = str(arguments.get("artifact_id") or "").strip()
        artifact = await self.access.assert_can_access_artifact(artifact_id, auth_ctx)

        structured = {
            "artifact_id": artifact.id,
            "name": artifact.file_name,
            "mime_type": artifact.content_type,
            "size_bytes": artifact.size_bytes,
            "download_url": f"/api/v1/hermes/artifacts/{artifact.id}/download",
            "requires_portal_auth": True,
            "suggested_workspace_path": artifact.suggested_workspace_path,
            "artifact_mode": "pull_only",
        }
        summary = (
            f"产物 {artifact.file_name} 可通过 Portal 认证下载："
            f"{structured['download_url']}"
        )
        await self._log_audit(
            "mcp.artifact.download_info.viewed",
            artifact.id,
            auth_ctx,
            {"artifact_id": artifact.id},
        )
        return self._wrap_result(summary, structured)

    async def _task_wait(
        self,
        arguments: dict[str, Any],
        auth_ctx: McpAuthContext,
    ) -> dict[str, Any]:
        task_id = str(arguments.get("task_id") or "").strip()
        timeout_seconds = int(arguments.get("timeout_seconds") or 120)
        timeout_seconds = max(5, min(timeout_seconds, settings.MCP_TASK_WAIT_MAX_SECONDS))

        await self.access.assert_can_access_task(task_id, auth_ctx)
        wait_result = await McpTaskWaitService().wait_for_task_result(
            task_id,
            auth_ctx.org.id,
            timeout_seconds=timeout_seconds,
        )
        summary = _build_task_wait_summary(wait_result)
        await self._log_audit(
            "mcp.task.wait.viewed",
            task_id,
            auth_ctx,
            {
                "task_id": task_id,
                "status": wait_result.get("status"),
                "ready": wait_result.get("ready"),
                "wait_timeout": wait_result.get("wait_timeout"),
            },
        )
        return self._wrap_result(summary, wait_result)

    async def _materialized_server_artifacts(
        self,
        task_id: str,
        org_id: str,
    ) -> list[dict[str, Any]]:
        result = await self.db.execute(
            select(HermesArtifact).where(
                not_deleted(HermesArtifact),
                HermesArtifact.task_id == task_id,
                HermesArtifact.org_id == org_id,
                HermesArtifact.source == "materialized",
            ).order_by(HermesArtifact.created_at.asc())
        )
        artifacts = list(result.scalars().all())
        return [ServerArtifactService.to_server_artifact_dict(a) for a in artifacts]

    async def _discovery_artifact_dicts(
        self,
        task_id: str,
        org_id: str,
    ) -> list[dict[str, Any]]:
        result = await self.db.execute(
            select(HermesArtifact).where(
                not_deleted(HermesArtifact),
                HermesArtifact.task_id == task_id,
                HermesArtifact.org_id == org_id,
                HermesArtifact.source != "materialized",
            ).order_by(HermesArtifact.created_at.asc())
        )
        items: list[dict[str, Any]] = []
        for artifact in result.scalars().all():
            items.append({
                "artifact_id": artifact.id,
                "name": artifact.file_name,
                "type": artifact.format or artifact.artifact_type or "file",
                "mime_type": artifact.content_type,
                "preview_url": f"/api/v1/hermes/artifacts/{artifact.id}/preview",
                "download_url": f"/api/v1/hermes/artifacts/{artifact.id}/download",
                "kb_status": artifact.kb_status,
            })
        return items

    async def _log_audit(
        self,
        action: str,
        target_id: str,
        auth_ctx: McpAuthContext,
        details: dict[str, Any],
    ) -> None:
        audit_details = dict(details)
        audit_details["auth_type"] = auth_ctx.auth_type
        if auth_ctx.mcp_client_token_prefix:
            audit_details["mcp_client_token_prefix"] = auth_ctx.mcp_client_token_prefix
        if auth_ctx.hermes_agent_id:
            audit_details["hermes_agent_id"] = auth_ctx.hermes_agent_id
        await self.audit.log(
            action=action,
            target_id=target_id,
            org_id=auth_ctx.org.id,
            actor_id=auth_ctx.user.id,
            actor_type="mcp_client" if auth_ctx.auth_type == "mcp_client_token" else "user",
            details=audit_details,
        )

    @staticmethod
    def _wrap_result(summary: str, structured: dict[str, Any]) -> dict[str, Any]:
        return {
            "content": [{"type": "text", "text": summary}],
            "structuredContent": structured,
            "isError": bool(structured.get("isError")),
        }


def _build_task_wait_summary(result: dict[str, Any]) -> str:
    task_no = result.get("task_no") or result.get("task_id") or ""
    status = result.get("status") or ""
    if result.get("ready") is True and status == "completed":
        artifacts = result.get("server_artifacts") or []
        if artifacts:
            names = "、".join(a.get("name") or "" for a in artifacts[:3] if a.get("name"))
            return f"任务 {task_no} 已完成。已生成中心产物：{names}。"
        return f"任务 {task_no} 已完成。"
    if result.get("wait_timeout"):
        return (
            f"任务 {task_no} 仍在执行中，本次等待已超时。"
            "请稍后再次调用 nodeskclaw_task_wait。"
        )
    if result.get("isError") or status in ("failed", "timeout", "cancelled"):
        err = result.get("error") or {}
        return f"任务 {task_no} 执行失败：{err.get('message') or status}"
    return f"任务 {task_no} 当前状态：{status}。"
