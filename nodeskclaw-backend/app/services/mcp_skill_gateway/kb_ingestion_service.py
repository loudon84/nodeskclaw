from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, NotFoundError
from app.models.base import not_deleted
from app.models.hermes_skill.hermes_artifact import HermesArtifact
from app.models.hermes_skill.hermes_artifact_kb_ingestion_job import HermesArtifactKbIngestionJob
from app.services.hermes_skill.skill_audit_logger import SkillAuditLogger


class KbIngestionService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = SkillAuditLogger(db)

    async def create_job(
        self,
        artifact: HermesArtifact,
        output_policy: dict[str, Any],
    ) -> HermesArtifactKbIngestionJob | None:
        kb = output_policy.get("kb_ingest") or {}
        if not kb.get("enabled"):
            return None

        if artifact.sha256:
            existing = await self.db.execute(
                select(HermesArtifactKbIngestionJob).where(
                    not_deleted(HermesArtifactKbIngestionJob),
                    HermesArtifactKbIngestionJob.org_id == artifact.org_id,
                    HermesArtifactKbIngestionJob.sha256 == artifact.sha256,
                ).limit(1)
            )
            if existing.scalar_one_or_none():
                return None

        status = str(kb.get("mode") or "pending_review")
        job = HermesArtifactKbIngestionJob(
            id=str(uuid.uuid4()),
            org_id=artifact.org_id,
            artifact_id=artifact.id,
            task_id=artifact.task_id or "",
            knowledge_base=str(kb.get("knowledge_base") or "general"),
            status=status,
            tags=kb.get("tags") or [],
            sha256=artifact.sha256,
            metadata_json={
                "artifact_name": artifact.file_name,
                "tool_name": artifact.metadata_json.get("tool_name") if artifact.metadata_json else None,
            },
        )
        self.db.add(job)
        await self.db.flush()
        await self.audit.log(
            action="mcp_artifact.kb_job.created",
            target_id=job.id,
            org_id=artifact.org_id,
            actor_type="system",
            actor_id="",
            details={"artifact_id": artifact.id, "task_id": artifact.task_id, "status": status},
        )
        return job

    async def list_jobs(
        self,
        org_id: str,
        *,
        status: str | None = None,
        knowledge_base: str | None = None,
        task_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[HermesArtifactKbIngestionJob], int]:
        from sqlalchemy import func

        base = select(HermesArtifactKbIngestionJob).where(
            not_deleted(HermesArtifactKbIngestionJob),
            HermesArtifactKbIngestionJob.org_id == org_id,
        )
        if status:
            base = base.where(HermesArtifactKbIngestionJob.status == status)
        if knowledge_base:
            base = base.where(HermesArtifactKbIngestionJob.knowledge_base == knowledge_base)
        if task_id:
            base = base.where(HermesArtifactKbIngestionJob.task_id == task_id)

        total = (await self.db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
        result = await self.db.execute(
            base.order_by(HermesArtifactKbIngestionJob.created_at.desc()).offset(offset).limit(limit)
        )
        return list(result.scalars().all()), total

    async def _get_job(self, job_id: str, org_id: str) -> HermesArtifactKbIngestionJob:
        job = await self.db.get(HermesArtifactKbIngestionJob, job_id)
        if not job or job.deleted_at is not None or job.org_id != org_id:
            raise NotFoundError("入库任务不存在", "errors.hermes.kb_job.not_found")
        return job

    async def approve(self, job_id: str, org_id: str, reviewer_id: str) -> HermesArtifactKbIngestionJob:
        job = await self._get_job(job_id, org_id)
        if job.status not in ("pending_review", "approved"):
            raise BadRequestError("当前状态不可审核通过", "errors.hermes.kb_job.invalid_status")

        now = datetime.now(timezone.utc)
        job.status = "approved"
        job.reviewed_by = reviewer_id
        job.reviewed_at = now
        await self.db.flush()

        job.status = "indexing"
        await self.db.flush()

        job.status = "indexed"
        job.indexed_at = datetime.now(timezone.utc)
        await self.db.flush()

        artifact = await self.db.get(HermesArtifact, job.artifact_id)
        if artifact and artifact.deleted_at is None:
            artifact.kb_status = "indexed"

        await self.audit.log(
            action="mcp_artifact.kb_job.approved",
            target_id=job.id,
            org_id=org_id,
            actor_id=reviewer_id,
            details={"artifact_id": job.artifact_id},
        )
        await self.audit.log(
            action="mcp_artifact.kb_job.indexed",
            target_id=job.id,
            org_id=org_id,
            actor_id=reviewer_id,
            details={"artifact_id": job.artifact_id},
        )
        return job

    async def reject(
        self,
        job_id: str,
        org_id: str,
        reviewer_id: str,
        comment: str | None = None,
    ) -> HermesArtifactKbIngestionJob:
        job = await self._get_job(job_id, org_id)
        if job.status not in ("pending_review",):
            raise BadRequestError("当前状态不可拒绝", "errors.hermes.kb_job.invalid_status")

        job.status = "rejected"
        job.reviewed_by = reviewer_id
        job.reviewed_at = datetime.now(timezone.utc)
        job.review_comment = comment
        await self.db.flush()

        artifact = await self.db.get(HermesArtifact, job.artifact_id)
        if artifact and artifact.deleted_at is None:
            artifact.kb_status = "rejected"

        await self.audit.log(
            action="mcp_artifact.kb_job.rejected",
            target_id=job.id,
            org_id=org_id,
            actor_id=reviewer_id,
            details={"artifact_id": job.artifact_id, "comment": (comment or "")[:512]},
        )
        return job

    async def manual_ingest(
        self,
        artifact_id: str,
        org_id: str,
        actor_id: str,
        *,
        knowledge_base: str = "general",
        tags: list[str] | None = None,
    ) -> HermesArtifactKbIngestionJob:
        artifact = await self.db.get(HermesArtifact, artifact_id)
        if not artifact or artifact.deleted_at is not None or artifact.org_id != org_id:
            raise NotFoundError("产物不存在", "errors.artifact.not_found")

        job = HermesArtifactKbIngestionJob(
            id=str(uuid.uuid4()),
            org_id=org_id,
            artifact_id=artifact.id,
            task_id=artifact.task_id or "",
            knowledge_base=knowledge_base,
            status="pending_review",
            tags=tags or [],
            sha256=artifact.sha256,
        )
        self.db.add(job)
        artifact.kb_status = "pending_review"
        await self.db.flush()
        await self.audit.log(
            action="mcp_artifact.kb_job.created",
            target_id=job.id,
            org_id=org_id,
            actor_id=actor_id,
            details={"artifact_id": artifact.id, "manual": True},
        )
        return job
