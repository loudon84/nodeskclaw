"""Artifact path ACL adapter over permission_service AccessPlan."""

# @lat: [[architecture/knowledge#Knowledge Intelligence V23]]

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.enums import AccessPlanKind, FilePermission, KbPermission
from app.models.knowledge_artifact import KnowledgeArtifact
from app.models.knowledge_base import KnowledgeBase
from app.models.source_file import SourceFile
from app.schemas.principal import KnowledgePrincipal
from app.services.permission_service import AccessPlan, build_access_plan, has_file_permission, has_kb_permission


def artifact_acl_enabled() -> bool:
    return settings.KNOWLEDGE_V24_ARTIFACT_ACL_ENABLED


async def _require_kb_access_plan(
    db: AsyncSession,
    member: KnowledgePrincipal,
    kb: KnowledgeBase,
) -> AccessPlan:
    plan = await build_access_plan(db, member, [kb])
    if plan.kind == AccessPlanKind.no_access:
        raise NotFoundError(
            message="Artifact 不存在",
            message_key="errors.knowledge.artifact_not_found",
        )
    return plan


async def authorize_kb_artifact_access(
    db: AsyncSession,
    member: KnowledgePrincipal,
    kb: KnowledgeBase,
) -> AccessPlan | None:
    if not artifact_acl_enabled():
        return None
    return await _require_kb_access_plan(db, member, kb)


async def authorize_artifact_read(
    db: AsyncSession,
    member: KnowledgePrincipal,
    artifact: KnowledgeArtifact,
    kb: KnowledgeBase,
) -> AccessPlan | None:
    if not artifact_acl_enabled():
        return None
    if artifact.org_id != member.org_id and not member.is_super_admin:
        raise NotFoundError(
            message="Artifact 不存在",
            message_key="errors.knowledge.artifact_not_found",
        )
    plan = await _require_kb_access_plan(db, member, kb)
    if artifact.scope == "file" and artifact.source_file_id:
        source_file = await db.get(SourceFile, artifact.source_file_id)
        if source_file is None or source_file.deleted_at is not None:
            raise NotFoundError(
                message="Artifact 不存在",
                message_key="errors.knowledge.artifact_not_found",
            )
        if not await has_file_permission(db, member, source_file, FilePermission.read.value):
            raise NotFoundError(
                message="Artifact 不存在",
                message_key="errors.knowledge.artifact_not_found",
            )
        if (
            artifact.file_version_id
            and source_file.active_version_id
            and artifact.file_version_id != source_file.active_version_id
        ):
            raise NotFoundError(
                message="Artifact 不存在",
                message_key="errors.knowledge.artifact_not_found",
            )
    elif not await has_kb_permission(db, member, kb.id, KbPermission.read.value):
        raise NotFoundError(
            message="Artifact 不存在",
            message_key="errors.knowledge.artifact_not_found",
        )
    return plan


async def can_read_artifact(
    db: AsyncSession,
    member: KnowledgePrincipal,
    artifact: KnowledgeArtifact,
    kb: KnowledgeBase,
) -> bool:
    try:
        await authorize_artifact_read(db, member, artifact, kb)
        return True
    except (ForbiddenError, NotFoundError):
        return False


def filter_source_refs(
    plan: AccessPlan | None,
    source_refs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if plan is None or plan.kind == AccessPlanKind.full_access:
        return list(source_refs)
    if plan.kind == AccessPlanKind.no_access:
        return []
    allowed = set(plan.source_file_ids)
    filtered: list[dict[str, Any]] = []
    for ref in source_refs:
        if not isinstance(ref, dict):
            continue
        source_file_id = ref.get("source_file_id")
        if source_file_id and source_file_id in allowed:
            filtered.append(ref)
    return filtered


def filter_artifact_content(
    content: dict[str, Any],
    plan: AccessPlan | None,
    *,
    artifact_type: str,
) -> dict[str, Any]:
    if plan is None or plan.kind == AccessPlanKind.full_access:
        return content
    if artifact_type == "outline" and isinstance(content.get("nodes"), list):
        nodes: list[dict[str, Any]] = []
        for node in content["nodes"]:
            if not isinstance(node, dict):
                continue
            node_copy = dict(node)
            refs = filter_source_refs(plan, node_copy.get("source_refs") or [])
            node_copy["source_refs"] = refs
            node_copy["citable"] = len(refs) > 0
            if plan.kind == AccessPlanKind.filtered_access and not refs:
                continue
            nodes.append(node_copy)
        return {**content, "nodes": nodes}
    if artifact_type == "table":
        if isinstance(content.get("tables"), list):
            tables: list[dict[str, Any]] = []
            for table in content["tables"]:
                if not isinstance(table, dict):
                    continue
                filtered_table = _filter_table_rows(table, plan)
                if filtered_table.get("rows"):
                    tables.append(filtered_table)
            return {**content, "tables": tables}
        return _filter_table_rows(content, plan)
    return content


def _filter_table_rows(table: dict[str, Any], plan: AccessPlan) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for row in table.get("rows") or []:
        if not isinstance(row, dict):
            continue
        row_copy = dict(row)
        refs = filter_source_refs(plan, row_copy.get("source_refs") or [])
        row_copy["source_refs"] = refs
        if plan.kind == AccessPlanKind.filtered_access and not refs:
            continue
        rows.append(row_copy)
    return {**table, "rows": rows}
