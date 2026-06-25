from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.feature_gate import feature_gate
from app.models.hermes_skill.hermes_artifact import HermesArtifact
from app.models.hermes_skill.hermes_task import HermesTask
from app.services.hermes_skill.skill_audit_logger import SkillAuditLogger
from app.services.mcp_skill_gateway.artifact_materializer import ArtifactMaterializer
from app.services.mcp_skill_gateway.artifact_store_service import ArtifactStoreService
from app.services.mcp_skill_gateway.kb_ingestion_service import KbIngestionService

logger = logging.getLogger(__name__)

MATERIALIZED_SOURCE = "materialized"
OBJECT_STORE_TYPE = "object_store"
ARTIFACT_STORE_NAME = "nodeskclaw_artifact_store"


class ServerArtifactService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = SkillAuditLogger(db)
        self.store = ArtifactStoreService()
        self.materializer = ArtifactMaterializer()
        self.kb = KbIngestionService(db)

    @staticmethod
    def to_server_artifact_dict(artifact: HermesArtifact) -> dict[str, Any]:
        return {
            "artifact_id": artifact.id,
            "name": artifact.file_name,
            "type": artifact.format or artifact.artifact_type or "markdown",
            "mime_type": artifact.content_type,
            "stored": True,
            "store": ARTIFACT_STORE_NAME,
            "download_url": f"/api/v1/hermes/artifacts/{artifact.id}/download",
            "preview_url": f"/api/v1/hermes/artifacts/{artifact.id}/preview",
            "suggested_workspace_path": artifact.suggested_workspace_path,
            "workspace_saved": bool(artifact.workspace_saved),
            "kb_status": artifact.kb_status,
        }

    @staticmethod
    def resolve_task_kb_status(server_artifacts: list[dict[str, Any]]) -> str:
        if not server_artifacts:
            return "none"
        statuses = {item.get("kb_status") for item in server_artifacts if item.get("kb_status")}
        if "pending_review" in statuses:
            return "pending_review"
        if "indexed" in statuses:
            return "indexed"
        if "rejected" in statuses:
            return "rejected"
        return next(iter(statuses), "none")

    async def create_from_task_result(
        self,
        task: HermesTask,
        full_result_text: str,
        output_policy: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        policy = output_policy or {}
        if not policy.get("store_to_gateway", True):
            return []

        artifact_id = str(uuid.uuid4())
        completed_at = task.completed_at or datetime.now(timezone.utc)

        await self.audit.log(
            action="mcp_artifact.materialize.started",
            target_id=task.id,
            org_id=task.org_id,
            actor_type="system",
            actor_id=task.worker_id or "",
            details={"tool_name": task.tool_name, "artifact_mode": "pull_only"},
        )

        content = self.materializer.materialize(
            task,
            full_result_text,
            policy,
            artifact_id=artifact_id,
            completed_at=completed_at,
        )
        stored = await self.store.store(
            org_id=task.org_id,
            task_id=task.id,
            artifact_id=artifact_id,
            filename=content.filename,
            content=content.content,
        )

        kb = policy.get("kb_ingest") or {}
        kb_status = "none"
        if kb.get("enabled"):
            kb_status = str(kb.get("mode") or "pending_review")

        permission_scope = "org" if not feature_gate.is_ee else "workspace"
        if feature_gate.is_ee and not task.workspace_id:
            permission_scope = "task_creator"

        preview_supported = bool(
            content.mime_type.startswith(("text/", "application/json"))
        )

        artifact = HermesArtifact(
            id=artifact_id,
            org_id=task.org_id,
            task_id=task.id,
            skill_id=task.skill_id,
            agent_id=task.agent_id,
            workspace_id=task.workspace_id,
            file_name=content.filename,
            file_path=stored.object_key,
            relative_path=content.suggested_workspace_path,
            content_type=content.mime_type,
            size_bytes=stored.size_bytes,
            sha256=stored.sha256,
            storage_type=OBJECT_STORE_TYPE,
            object_key=stored.object_key,
            suggested_workspace_dir=content.suggested_workspace_dir,
            suggested_workspace_path=content.suggested_workspace_path,
            workspace_saved=False,
            kb_status=kb_status,
            format=content.format,
            source=MATERIALIZED_SOURCE,
            permission_scope=permission_scope,
            preview_supported=preview_supported,
            title=content.filename,
            artifact_type=content.format,
            metadata_json={
                "source": MATERIALIZED_SOURCE,
                "tool_name": task.tool_name,
                "artifact_mode": "pull_only",
            },
            created_by=task.user_id,
        )
        self.db.add(artifact)
        await self.db.flush()

        await self.kb.create_job(artifact, policy)

        server_item = self.to_server_artifact_dict(artifact)
        await self.audit.log(
            action="mcp_artifact.materialize.completed",
            target_id=artifact.id,
            org_id=task.org_id,
            actor_type="system",
            actor_id=task.worker_id or "",
            details={
                "task_id": task.id,
                "artifact_name": artifact.file_name,
                "suggested_workspace_path": artifact.suggested_workspace_path,
                "kb_status": artifact.kb_status,
            },
        )
        await self.audit.log(
            action="mcp_artifact.store.completed",
            target_id=artifact.id,
            org_id=task.org_id,
            actor_type="system",
            actor_id=task.worker_id or "",
            details={"object_key": stored.object_key, "size_bytes": stored.size_bytes},
        )
        return [server_item]

    @staticmethod
    def append_artifact_links(result_summary: str, server_artifacts: list[dict[str, Any]]) -> str:
        if not server_artifacts:
            return result_summary
        lines = [result_summary.rstrip(), "", "报告已保存到 nodeskclaw 中心产物库。"]
        for item in server_artifacts:
            lines.append(f"- 预览：{item.get('preview_url')}")
            lines.append(f"- 下载：{item.get('download_url')}")
            lines.append(f"- 建议导入路径：{item.get('suggested_workspace_path')}")
            lines.append(f"- 知识库状态：{item.get('kb_status')}")
        merged = "\n".join(lines)
        return merged[:500]
