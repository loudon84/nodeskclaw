import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.base import not_deleted
from app.models.hermes_skill.hermes_artifact import HermesArtifact
from app.models.hermes_skill.hermes_task import HermesTask, HermesTaskEvent
from app.models.hermes_skill.skill import HermesSkill
from app.services.hermes_skill.agent_alias_resolver import AgentAliasResolver
from app.services.hermes_skill.task_event_service import TaskEventService

logger = logging.getLogger(__name__)

_PREFERRED_FILENAMES = ("article.md", "output.md", "result.md")
_TEXT_CONTENT_PREFIXES = ("text/", "application/json", "application/markdown")


class TaskResultService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_result(self, task_id: str, org_id: str) -> dict:
        task = await self._get_task(task_id, org_id)
        artifacts = await self._list_task_artifacts(task_id, org_id)
        skill = await self._get_skill(task)
        primary_policy = None
        if skill and skill.extra_metadata:
            primary_policy = skill.extra_metadata.get("primary_artifact_policy")

        primary = self._select_primary_artifact(artifacts, primary_policy)
        timeline = await self._build_timeline(task_id, org_id)
        agent_alias = task.routing_metadata.get("agent_alias") if task.routing_metadata else None
        if not agent_alias and task.agent_id:
            resolution = await AgentAliasResolver(self.db).resolve(org_id, task.agent_id)
            if resolution:
                agent_alias = resolution.agent_alias

        return {
            "task": {
                "id": task.id,
                "task_no": task.task_no,
                "status": task.status.value,
                "tool_name": task.tool_name,
                "agent_alias": agent_alias,
                "agent_id": task.agent_id,
                "profile_id": task.profile_id,
                "workspace_id": task.workspace_id,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            },
            "primary_artifact": self._artifact_to_dict(primary) if primary else None,
            "artifacts": [self._artifact_to_dict(a) for a in artifacts if primary is None or a.id != primary.id],
            "timeline": timeline,
            "result_summary": task.result_summary,
        }

    async def _get_task(self, task_id: str, org_id: str) -> HermesTask:
        result = await self.db.execute(
            select(HermesTask).where(
                HermesTask.id == task_id,
                HermesTask.org_id == org_id,
                not_deleted(HermesTask),
            )
        )
        task = result.scalar_one_or_none()
        if task is None:
            raise NotFoundError("任务不存在", "errors.task.not_found")
        return task

    async def _list_task_artifacts(self, task_id: str, org_id: str) -> list[HermesArtifact]:
        result = await self.db.execute(
            select(HermesArtifact).where(
                HermesArtifact.task_id == task_id,
                HermesArtifact.org_id == org_id,
                not_deleted(HermesArtifact),
            ).order_by(HermesArtifact.created_at.asc())
        )
        return list(result.scalars().all())

    async def _get_skill(self, task: HermesTask) -> HermesSkill | None:
        if not task.skill_id:
            return None
        result = await self.db.execute(
            select(HermesSkill).where(
                HermesSkill.skill_id == task.skill_id,
                HermesSkill.org_id == task.org_id,
                not_deleted(HermesSkill),
            ).limit(1)
        )
        return result.scalar_one_or_none()

    async def _build_timeline(self, task_id: str, org_id: str) -> list[dict]:
        events = await TaskEventService(self.db).get_events(task_id, org_id)
        return [
            {
                "event_seq": event.event_seq,
                "event_type": event.event_type.value,
                "created_at": event.created_at.isoformat() if event.created_at else None,
                "payload": event.payload,
            }
            for event in events
        ]

    def _select_primary_artifact(
        self,
        artifacts: list[HermesArtifact],
        primary_policy: dict | None,
    ) -> HermesArtifact | None:
        if not artifacts:
            return None

        for artifact in artifacts:
            meta = artifact.metadata_json or {}
            if meta.get("primary") is True:
                return artifact

        if primary_policy:
            policy_type = primary_policy.get("artifact_type")
            prefer_name = primary_policy.get("prefer_file_name")
            if prefer_name:
                for artifact in artifacts:
                    if artifact.file_name == prefer_name:
                        return artifact
            if policy_type:
                for artifact in artifacts:
                    if artifact.artifact_type == policy_type:
                        return artifact

        for artifact in artifacts:
            if artifact.artifact_type == "markdown":
                return artifact
            if artifact.content_type and "markdown" in artifact.content_type:
                return artifact

        for prefer_name in _PREFERRED_FILENAMES:
            for artifact in artifacts:
                if artifact.file_name == prefer_name:
                    return artifact

        text_artifacts = [
            a for a in artifacts
            if self._is_text_artifact(a) and (a.size_bytes or 0) > 0
        ]
        if text_artifacts:
            return max(text_artifacts, key=lambda a: a.size_bytes or 0)

        return artifacts[0]

    @staticmethod
    def _is_text_artifact(artifact: HermesArtifact) -> bool:
        if artifact.content_type:
            return any(artifact.content_type.startswith(p) for p in _TEXT_CONTENT_PREFIXES)
        suffix = Path(artifact.file_name).suffix.lower()
        return suffix in {".md", ".txt", ".json", ".html", ".csv"}

    @staticmethod
    def _artifact_to_dict(artifact: HermesArtifact) -> dict:
        return {
            "id": artifact.id,
            "title": artifact.title or artifact.file_name,
            "file_name": artifact.file_name,
            "artifact_type": artifact.artifact_type,
            "content_type": artifact.content_type,
            "preview_url": f"/api/v1/hermes/artifacts/{artifact.id}/preview",
            "download_url": f"/api/v1/hermes/artifacts/{artifact.id}/download",
        }
