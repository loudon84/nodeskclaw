"""Artifact identity and revision lifecycle."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge_artifacts.base import ArtifactBuildResult
from app.models.base import not_deleted
from app.models.knowledge_artifact import KnowledgeArtifact, KnowledgeArtifactRevision


# @lat: [[knowledge-objects#Knowledge Artifact]]
async def get_or_create_identity(
    db: AsyncSession,
    *,
    org_id: str,
    knowledge_base_id: str,
    artifact_type: str,
    provider: str,
    scope: str,
    source_file_id: str | None = None,
    file_version_id: str | None = None,
) -> KnowledgeArtifact:
    stmt = select(KnowledgeArtifact).where(
        KnowledgeArtifact.org_id == org_id,
        KnowledgeArtifact.knowledge_base_id == knowledge_base_id,
        KnowledgeArtifact.artifact_type == artifact_type,
        KnowledgeArtifact.scope == scope,
        not_deleted(KnowledgeArtifact),
    )
    if source_file_id is not None:
        stmt = stmt.where(KnowledgeArtifact.source_file_id == source_file_id)
    else:
        stmt = stmt.where(KnowledgeArtifact.source_file_id.is_(None))

    row = await db.scalar(stmt)
    if row is not None:
        if file_version_id is not None:
            row.file_version_id = file_version_id
        return row

    row = KnowledgeArtifact(
        org_id=org_id,
        knowledge_base_id=knowledge_base_id,
        artifact_type=artifact_type,
        provider=provider,
        scope=scope,
        source_file_id=source_file_id,
        file_version_id=file_version_id,
        status="not_built",
    )
    db.add(row)
    await db.flush()
    return row


async def _next_revision_number(db: AsyncSession, artifact_id: str) -> int:
    current = await db.scalar(
        select(func.max(KnowledgeArtifactRevision.revision_number)).where(
            KnowledgeArtifactRevision.knowledge_artifact_id == artifact_id,
            not_deleted(KnowledgeArtifactRevision),
        )
    )
    return int(current or 0) + 1


def _sync_identity_from_revision(artifact: KnowledgeArtifact, revision: KnowledgeArtifactRevision) -> None:
    artifact.active_revision_id = revision.id
    artifact.artifact_uri = revision.artifact_uri
    artifact.input_manifest_hash = revision.input_manifest_hash
    artifact.validation_payload = revision.validation_payload
    artifact.coverage_payload = revision.coverage_payload
    artifact.provider_payload = revision.provider_payload
    artifact.lineage_payload = revision.lineage_payload
    artifact.last_built_at = revision.last_built_at
    artifact.last_validated_at = revision.last_validated_at
    artifact.last_error = revision.last_error
    artifact.file_version_id = revision.file_version_id
    artifact.version = revision.revision_number


async def publish_revision(
    db: AsyncSession,
    *,
    artifact: KnowledgeArtifact,
    build_result: ArtifactBuildResult,
    input_manifest_hash: str,
    file_version_id: str | None = None,
) -> KnowledgeArtifactRevision:
    now = datetime.now(UTC)
    revision_number = await _next_revision_number(db, artifact.id)
    ready_rows = await db.scalars(
        select(KnowledgeArtifactRevision).where(
            KnowledgeArtifactRevision.knowledge_artifact_id == artifact.id,
            KnowledgeArtifactRevision.status == "ready",
            not_deleted(KnowledgeArtifactRevision),
        )
    )
    for old in ready_rows.all():
        old.status = "stale"

    succeeded = build_result.status == "succeeded"
    revision = KnowledgeArtifactRevision(
        org_id=artifact.org_id,
        knowledge_artifact_id=artifact.id,
        revision_number=revision_number,
        file_version_id=file_version_id or artifact.file_version_id,
        input_manifest_hash=input_manifest_hash,
        artifact_uri=build_result.artifact_uri,
        status="ready" if succeeded else "failed",
        validation_payload=build_result.validation_payload,
        coverage_payload=build_result.coverage_payload,
        provider_payload=build_result.provider_payload,
        last_built_at=now if succeeded else None,
        last_validated_at=now if succeeded else None,
        last_error=build_result.error_message,
    )
    db.add(revision)
    await db.flush()

    if succeeded:
        _sync_identity_from_revision(artifact, revision)
        artifact.status = "ready"
    else:
        artifact.status = "failed"
        artifact.last_error = build_result.error_message

    return revision
