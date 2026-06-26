from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.feature_gate import feature_gate
from app.models.hermes_skill.hermes_artifact import HermesArtifact
from app.models.hermes_skill.hermes_task import HermesTask
from app.services.hermes_skill.path_guard import PathGuard
from app.services.hermes_skill.skill_audit_logger import SkillAuditLogger
from app.services.mcp_skill_gateway.artifact_materializer import ArtifactMaterializer
from app.services.mcp_skill_gateway.artifact_store_service import ArtifactStoreService
from app.services.mcp_skill_gateway.kb_ingestion_service import KbIngestionService

logger = logging.getLogger(__name__)

MATERIALIZED_SOURCE = "materialized"
PROMOTED_METADATA_SOURCE = "hermes_api_server_workspace_promoted"
OBJECT_STORE_TYPE = "object_store"
ARTIFACT_STORE_NAME = "nodeskclaw_artifact_store"
_PROMOTABLE_EXTENSIONS = {".md", ".txt", ".json", ".csv"}
_REPORT_KEYWORDS = ("报告", "客户画像", "风险评估", "联系窗口", "推广文案")


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

    @staticmethod
    def build_suggested_path_from_relative_path(relative_path: str) -> str:
        rel = relative_path.strip("/")
        if rel.startswith("workspace/"):
            return rel
        return f"workspace/{rel}"

    @staticmethod
    def _is_promotable_content_type(content_type: str | None) -> bool:
        if not content_type:
            return False
        lowered = content_type.lower()
        return lowered.startswith("text/") or lowered == "application/json"

    def _filter_promotable_artifacts(
        self,
        task: HermesTask,
        artifacts: list[HermesArtifact],
    ) -> list[HermesArtifact]:
        eligible: list[HermesArtifact] = []
        for artifact in artifacts:
            if artifact.deleted_at is not None:
                continue
            if artifact.task_id != task.id or artifact.org_id != task.org_id:
                continue
            if artifact.storage_type == OBJECT_STORE_TYPE and artifact.object_key:
                continue
            suffix = Path(artifact.file_name).suffix.lower()
            if suffix not in _PROMOTABLE_EXTENSIONS:
                continue
            if not self._is_promotable_content_type(artifact.content_type):
                continue
            host_path = Path(artifact.file_path)
            if not host_path.is_file():
                continue
            if host_path.stat().st_size <= 0:
                continue
            metadata = artifact.metadata_json or {}
            host_root = metadata.get("host_workspace_root")
            if host_root:
                try:
                    max_size = settings.HERMES_ARTIFACT_DISCOVERY_MAX_FILE_SIZE_MB * 1024 * 1024
                    PathGuard.validate_file_for_download(
                        host_path,
                        Path(host_root),
                        max_size=max_size,
                    )
                except Exception as exc:
                    logger.warning(
                        "promote skipped artifact %s: path guard failed: %s",
                        artifact.id,
                        exc,
                    )
                    continue
            eligible.append(artifact)
        return eligible

    def _rank_artifacts(
        self,
        artifacts: list[HermesArtifact],
        result_text: str | None,
    ) -> list[HermesArtifact]:
        if settings.HERMES_ARTIFACT_PROMOTE_MODE != "primary_only":
            return artifacts

        text = result_text or ""

        def score(artifact: HermesArtifact) -> tuple[int, int, int, int, float]:
            rel = artifact.relative_path or artifact.file_name or ""
            path_hit = 1 if rel and rel in text else 0
            keyword_hit = 1 if any(kw in artifact.file_name for kw in _REPORT_KEYWORDS) else 0
            markdown_hit = 1 if artifact.file_name.lower().endswith(".md") else 0
            size = artifact.size_bytes or 0
            mtime = 0.0
            try:
                mtime = Path(artifact.file_path).stat().st_mtime
            except OSError:
                pass
            return (path_hit, keyword_hit, markdown_hit, size, mtime)

        ranked = sorted(artifacts, key=score, reverse=True)
        return ranked[:1] if ranked else []

    async def create_from_discovered_artifacts(
        self,
        task: HermesTask,
        artifacts: list[HermesArtifact],
        output_policy: dict[str, Any] | None,
        *,
        result_text: str | None = None,
    ) -> list[dict[str, Any]]:
        policy = output_policy or {}
        if not policy.get("store_to_gateway", True):
            return []

        eligible = self._filter_promotable_artifacts(task, artifacts)
        if not eligible:
            return []

        selected = self._rank_artifacts(eligible, result_text)
        server_items: list[dict[str, Any]] = []

        for artifact in selected:
            await self.audit.log(
                action="mcp_artifact.discovery.promote.started",
                target_id=task.id,
                org_id=task.org_id,
                actor_type="system",
                actor_id=task.worker_id or "",
                details={
                    "artifact_id": artifact.id,
                    "artifact_name": artifact.file_name,
                    "tool_name": task.tool_name,
                },
            )
            try:
                host_path = Path(artifact.file_path)
                content = host_path.read_bytes()
                original_file_path = str(host_path)
                original_relative_path = artifact.relative_path or ""
                suggested_path = self.build_suggested_path_from_relative_path(original_relative_path)

                stored = await self.store.store(
                    org_id=task.org_id,
                    task_id=task.id,
                    artifact_id=artifact.id,
                    filename=artifact.file_name,
                    content=content,
                )

                kb = policy.get("kb_ingest") or {}
                kb_status = "none"
                if kb.get("enabled"):
                    kb_status = str(kb.get("mode") or "pending_review")

                resolved_format = artifact.format or artifact.artifact_type or "markdown"
                if artifact.file_name.lower().endswith(".json"):
                    resolved_format = "json"
                elif artifact.file_name.lower().endswith(".txt"):
                    resolved_format = "txt"
                elif artifact.file_name.lower().endswith(".csv"):
                    resolved_format = "csv"

                old_metadata = dict(artifact.metadata_json or {})
                artifact.storage_type = OBJECT_STORE_TYPE
                artifact.object_key = stored.object_key
                artifact.file_path = stored.object_key
                artifact.size_bytes = stored.size_bytes
                artifact.sha256 = stored.sha256
                artifact.source = MATERIALIZED_SOURCE
                artifact.kb_status = kb_status
                artifact.workspace_saved = False
                artifact.format = resolved_format
                artifact.suggested_workspace_path = suggested_path
                if "/" in original_relative_path:
                    artifact.suggested_workspace_dir = "/".join(
                        original_relative_path.strip("/").split("/")[:-1]
                    )
                artifact.metadata_json = {
                    **old_metadata,
                    "source": PROMOTED_METADATA_SOURCE,
                    "original_storage_type": old_metadata.get("original_storage_type", "local_fs"),
                    "original_file_path": original_file_path,
                    "original_relative_path": original_relative_path,
                    "artifact_mode": "pull_only",
                    "tool_name": task.tool_name,
                }
                await self.db.flush()

                await self.kb.create_job(artifact, policy)
                server_item = self.to_server_artifact_dict(artifact)
                server_items.append(server_item)

                await self.audit.log(
                    action="mcp_artifact.discovery.promote.completed",
                    target_id=artifact.id,
                    org_id=task.org_id,
                    actor_type="system",
                    actor_id=task.worker_id or "",
                    details={
                        "task_id": task.id,
                        "artifact_name": artifact.file_name,
                        "original_relative_path": original_relative_path,
                        "suggested_workspace_path": suggested_path,
                        "kb_status": artifact.kb_status,
                        "tool_name": task.tool_name,
                    },
                )
            except Exception as exc:
                logger.error(
                    "Promote discovered artifact failed task=%s artifact=%s: %s",
                    task.id,
                    artifact.id,
                    exc,
                    exc_info=True,
                )
                await self.audit.log(
                    action="mcp_artifact.discovery.promote.failed",
                    target_id=artifact.id,
                    org_id=task.org_id,
                    actor_type="system",
                    actor_id=task.worker_id or "",
                    details={
                        "task_id": task.id,
                        "artifact_name": artifact.file_name,
                        "error": str(exc)[:512],
                    },
                )

        return server_items

    async def create_from_task_result(
        self,
        task: HermesTask,
        full_result_text: str,
        output_policy: dict[str, Any] | None,
        *,
        fallback: bool = False,
    ) -> list[dict[str, Any]]:
        policy = output_policy or {}
        if not policy.get("store_to_gateway", True):
            return []

        artifact_id = str(uuid.uuid4())
        completed_at = task.completed_at or datetime.now(timezone.utc)

        started_action = (
            "mcp_artifact.materialize.fallback.started"
            if fallback
            else "mcp_artifact.materialize.started"
        )
        await self.audit.log(
            action=started_action,
            target_id=task.id,
            org_id=task.org_id,
            actor_type="system",
            actor_id=task.worker_id or "",
            details={"tool_name": task.tool_name, "artifact_mode": "pull_only", "fallback": fallback},
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

        metadata_source = "materialized_fallback" if fallback else MATERIALIZED_SOURCE
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
                "source": metadata_source,
                "tool_name": task.tool_name,
                "artifact_mode": "pull_only",
            },
            created_by=task.user_id,
        )
        self.db.add(artifact)
        await self.db.flush()

        await self.kb.create_job(artifact, policy)

        server_item = self.to_server_artifact_dict(artifact)
        completed_action = (
            "mcp_artifact.materialize.fallback.completed"
            if fallback
            else "mcp_artifact.materialize.completed"
        )
        await self.audit.log(
            action=completed_action,
            target_id=artifact.id,
            org_id=task.org_id,
            actor_type="system",
            actor_id=task.worker_id or "",
            details={
                "task_id": task.id,
                "artifact_name": artifact.file_name,
                "suggested_workspace_path": artifact.suggested_workspace_path,
                "kb_status": artifact.kb_status,
                "fallback": fallback,
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
