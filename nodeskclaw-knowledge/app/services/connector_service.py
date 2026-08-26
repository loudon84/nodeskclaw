"""Connector CRUD, test, pause/resume, sync trigger, delete policies."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.registry import get_connector_class, list_types
from app.core.exceptions import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from app.integrations.ragflow.client import RagflowClient
from app.models.base import not_deleted
from app.models.connector import (
    ConnectorCredential,
    ConnectorSourceObject,
    ConnectorSyncItem,
    ConnectorSyncRun,
    KnowledgeSourceConnector,
)
from app.models.enums import (
    ArchiveReason,
    AuditAction,
    ConnectorStatus,
    ConnectorSyncMode,
    ConnectorSyncRunStatus,
    ConnectorSyncTrigger,
    KbPermission,
    SourceKind,
    SourceSyncState,
)
from app.models.knowledge_base import KnowledgeBase
from app.models.source_file import SourceFile
from app.schemas.principal import KnowledgePrincipal
from app.services import knowledge_base_service, runtime_binding_service
from app.services.audit_service import write_audit
from app.services.connector_credential_service import get_credential_provider
from app.services.permission_service import has_kb_permission

MIN_SYNC_INTERVAL_SECONDS = 300


def _now() -> datetime:
    return datetime.now(UTC)


async def _require_kb_manage(db: AsyncSession, member: KnowledgePrincipal, kb_id: str) -> KnowledgeBase:
    kb = await knowledge_base_service.get_knowledge_base(db, member, kb_id)
    if not await has_kb_permission(db, member, kb.id, KbPermission.manage.value):
        raise ForbiddenError()
    return kb


async def _require_kb_read_for_connector(
    db: AsyncSession, member: KnowledgePrincipal, connector: KnowledgeSourceConnector
) -> None:
    if connector.org_id != member.org_id and not member.is_super_admin:
        raise NotFoundError(message="Connector 不存在", message_key="errors.knowledge.connector_not_found")
    if not await has_kb_permission(db, member, connector.knowledge_base_id, KbPermission.read.value):
        raise ForbiddenError()


async def get_connector(db: AsyncSession, member: KnowledgePrincipal, connector_id: str) -> KnowledgeSourceConnector:
    row = await db.get(KnowledgeSourceConnector, connector_id)
    if row is None or row.deleted_at is not None:
        raise NotFoundError(message="Connector 不存在", message_key="errors.knowledge.connector_not_found")
    await _require_kb_read_for_connector(db, member, row)
    return row


def validate_sync_settings(sync_mode: str, sync_interval_seconds: int | None) -> None:
    if sync_mode not in {ConnectorSyncMode.manual.value, ConnectorSyncMode.interval.value}:
        raise BadRequestError(message="无效 sync_mode", message_key="errors.knowledge.connector_config_invalid")
    if sync_mode == ConnectorSyncMode.interval.value:
        if sync_interval_seconds is None or int(sync_interval_seconds) < MIN_SYNC_INTERVAL_SECONDS:
            raise BadRequestError(
                message=f"sync_interval_seconds 最低 {MIN_SYNC_INTERVAL_SECONDS}",
                message_key="errors.knowledge.connector_interval_too_small",
                message_params={"min_seconds": str(MIN_SYNC_INTERVAL_SECONDS)},
            )


def sanitize_config(connector_type: str, config: dict[str, Any]) -> dict[str, Any]:
    cfg = dict(config or {})
    # Never allow secrets in config
    for key in list(cfg.keys()):
        lowered = key.lower()
        if any(tok in lowered for tok in ("password", "secret", "token", "access_key", "api_key")):
            raise BadRequestError(
                message="禁止在 connector.config 中存放密钥",
                message_key="errors.knowledge.connector_config_invalid",
                details={"key": key},
            )
    if connector_type == "filesystem":
        allowed = {"root_alias", "sub_path", "include_globs", "exclude_globs", "page_size", "metadata_mapping", "connector_managed_metadata_keys"}
        unknown = set(cfg) - allowed
        if unknown:
            raise BadRequestError(
                message="filesystem config 仅允许 root_alias/sub_path 等字段",
                message_key="errors.knowledge.connector_config_invalid",
                details={"unknown": sorted(unknown)},
            )
        if not cfg.get("root_alias"):
            raise BadRequestError(message="缺少 root_alias", message_key="errors.knowledge.connector_config_invalid")
    return cfg


async def connector_out_extra(db: AsyncSession, connector: KnowledgeSourceConnector) -> dict[str, Any]:
    result = await db.execute(
        select(ConnectorCredential).where(
            ConnectorCredential.connector_id == connector.id,
            not_deleted(ConnectorCredential),
        )
    )
    cred = result.scalar_one_or_none()
    return {
        "credential_configured": cred is not None,
        "credential_updated_at": cred.updated_at if cred else None,
    }


async def list_connector_types() -> list[dict[str, Any]]:
    return [{"connector_type": t} for t in list_types()]


async def list_connectors(
    db: AsyncSession,
    member: KnowledgePrincipal,
    *,
    knowledge_base_id: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[KnowledgeSourceConnector], int]:
    filters = [KnowledgeSourceConnector.org_id == member.org_id, not_deleted(KnowledgeSourceConnector)]
    if knowledge_base_id:
        filters.append(KnowledgeSourceConnector.knowledge_base_id == knowledge_base_id)
    result = await db.execute(select(KnowledgeSourceConnector).where(*filters).order_by(KnowledgeSourceConnector.created_at.desc()))
    rows = list(result.scalars().all())
    visible: list[KnowledgeSourceConnector] = []
    for row in rows:
        if await has_kb_permission(db, member, row.knowledge_base_id, KbPermission.read.value):
            visible.append(row)
    total = len(visible)
    start = (page - 1) * page_size
    return visible[start : start + page_size], total


async def create_connector(
    db: AsyncSession,
    member: KnowledgePrincipal,
    *,
    knowledge_base_id: str,
    name: str,
    connector_type: str,
    config: dict[str, Any],
    sync_mode: str = ConnectorSyncMode.manual.value,
    sync_interval_seconds: int | None = None,
) -> KnowledgeSourceConnector:
    await _require_kb_manage(db, member, knowledge_base_id)
    try:
        get_connector_class(connector_type)
    except KeyError as exc:
        raise BadRequestError(message="未知 connector_type", message_key="errors.knowledge.connector_type_unknown") from exc
    validate_sync_settings(sync_mode, sync_interval_seconds)
    cfg = sanitize_config(connector_type, config)
    row = KnowledgeSourceConnector(
        org_id=member.org_id,
        knowledge_base_id=knowledge_base_id,
        name=name,
        connector_type=connector_type,
        status=ConnectorStatus.active.value,
        config=cfg,
        owner_member_id=member.member_id,
        sync_mode=sync_mode,
        sync_interval_seconds=sync_interval_seconds,
        next_sync_at=_now() + timedelta(seconds=sync_interval_seconds or 0)
        if sync_mode == ConnectorSyncMode.interval.value
        else None,
    )
    db.add(row)
    await db.flush()
    await write_audit(
        db,
        org_id=member.org_id,
        member_id=member.member_id,
        action=AuditAction.connector_create.value,
        resource_type="connector",
        resource_id=row.id,
        details={"connector_type": connector_type, "name": name},
    )
    await db.commit()
    await db.refresh(row)
    return row


async def update_connector(
    db: AsyncSession,
    member: KnowledgePrincipal,
    connector_id: str,
    *,
    name: str | None = None,
    config: dict[str, Any] | None = None,
    sync_mode: str | None = None,
    sync_interval_seconds: int | None = None,
    status: str | None = None,
) -> KnowledgeSourceConnector:
    row = await get_connector(db, member, connector_id)
    if not await has_kb_permission(db, member, row.knowledge_base_id, KbPermission.manage.value):
        raise ForbiddenError()
    if name is not None:
        row.name = name
    if config is not None:
        row.config = sanitize_config(row.connector_type, config)
    mode = sync_mode if sync_mode is not None else row.sync_mode
    interval = sync_interval_seconds if sync_interval_seconds is not None else row.sync_interval_seconds
    validate_sync_settings(mode, interval if mode == ConnectorSyncMode.interval.value else None)
    row.sync_mode = mode
    row.sync_interval_seconds = interval
    if status is not None:
        row.status = status
    if mode == ConnectorSyncMode.interval.value and row.next_sync_at is None:
        row.next_sync_at = _now() + timedelta(seconds=int(interval or MIN_SYNC_INTERVAL_SECONDS))
    await write_audit(
        db,
        org_id=member.org_id,
        member_id=member.member_id,
        action=AuditAction.connector_update.value,
        resource_type="connector",
        resource_id=row.id,
        details={"name": row.name, "sync_mode": row.sync_mode},
    )
    await db.commit()
    await db.refresh(row)
    return row


async def put_credential(
    db: AsyncSession,
    member: KnowledgePrincipal,
    connector_id: str,
    payload: dict[str, Any],
) -> KnowledgeSourceConnector:
    row = await get_connector(db, member, connector_id)
    if not await has_kb_permission(db, member, row.knowledge_base_id, KbPermission.manage.value):
        raise ForbiddenError()
    provider = get_credential_provider()
    cred = await provider.put(db, connector_id=row.id, payload=payload, member_id=member.member_id)
    row.credential_id = cred.id
    await write_audit(
        db,
        org_id=member.org_id,
        member_id=member.member_id,
        action=AuditAction.connector_credential_update.value,
        resource_type="connector",
        resource_id=row.id,
        details={"credential_configured": True},
    )
    await db.commit()
    await db.refresh(row)
    return row


async def delete_credential(db: AsyncSession, member: KnowledgePrincipal, connector_id: str) -> None:
    row = await get_connector(db, member, connector_id)
    if not await has_kb_permission(db, member, row.knowledge_base_id, KbPermission.manage.value):
        raise ForbiddenError()
    provider = get_credential_provider()
    await provider.delete(db, connector_id=row.id)
    row.credential_id = None
    await db.commit()


async def test_connector(db: AsyncSession, member: KnowledgePrincipal, connector_id: str) -> dict[str, Any]:
    row = await get_connector(db, member, connector_id)
    if not await has_kb_permission(db, member, row.knowledge_base_id, KbPermission.manage.value):
        raise ForbiddenError()
    adapter = await build_adapter(db, row)
    try:
        return await adapter.test_connection()
    finally:
        await adapter.close()


async def pause_connector(db: AsyncSession, member: KnowledgePrincipal, connector_id: str) -> KnowledgeSourceConnector:
    row = await get_connector(db, member, connector_id)
    if not await has_kb_permission(db, member, row.knowledge_base_id, KbPermission.manage.value):
        raise ForbiddenError()
    row.status = ConnectorStatus.paused.value
    await db.commit()
    await db.refresh(row)
    return row


async def resume_connector(db: AsyncSession, member: KnowledgePrincipal, connector_id: str) -> KnowledgeSourceConnector:
    row = await get_connector(db, member, connector_id)
    if not await has_kb_permission(db, member, row.knowledge_base_id, KbPermission.manage.value):
        raise ForbiddenError()
    row.status = ConnectorStatus.active.value
    if row.sync_mode == ConnectorSyncMode.interval.value:
        row.next_sync_at = _now()
    await db.commit()
    await db.refresh(row)
    return row


async def trigger_sync(
    db: AsyncSession,
    member: KnowledgePrincipal,
    connector_id: str,
    *,
    trigger: str = ConnectorSyncTrigger.manual.value,
) -> ConnectorSyncRun:
    row = await get_connector(db, member, connector_id)
    if not await has_kb_permission(db, member, row.knowledge_base_id, KbPermission.manage.value):
        raise ForbiddenError()
    if row.status == ConnectorStatus.paused.value:
        raise ConflictError(message="Connector 已暂停", message_key="errors.knowledge.connector_paused")
    if row.status == ConnectorStatus.deleting.value:
        raise ConflictError(message="Connector 正在删除", message_key="errors.knowledge.connector_deleting")

    active = await db.execute(
        select(ConnectorSyncRun).where(
            ConnectorSyncRun.connector_id == row.id,
            ConnectorSyncRun.status.in_(
                [
                    ConnectorSyncRunStatus.pending.value,
                    ConnectorSyncRunStatus.discovering.value,
                    ConnectorSyncRunStatus.applying.value,
                    ConnectorSyncRunStatus.waiting_ingestion.value,
                ]
            ),
            not_deleted(ConnectorSyncRun),
        )
    )
    if active.scalar_one_or_none():
        raise ConflictError(message="已有进行中的同步任务", message_key="errors.knowledge.connector_sync_in_progress")

    run = ConnectorSyncRun(
        connector_id=row.id,
        status=ConnectorSyncRunStatus.pending.value,
        trigger=trigger,
        cursor_before=dict(row.sync_cursor) if row.sync_cursor else None,
        created_by_member_id=member.member_id,
        metrics={},
        next_run_at=_now(),
    )
    db.add(run)
    row.last_sync_started_at = _now()
    await write_audit(
        db,
        org_id=member.org_id,
        member_id=member.member_id,
        action=AuditAction.connector_sync_start.value,
        resource_type="connector_sync_run",
        resource_id=None,
        details={"connector_id": row.id, "trigger": trigger},
    )
    await db.commit()
    await db.refresh(run)
    return run


async def delete_connector(
    db: AsyncSession,
    member: KnowledgePrincipal,
    ragflow: RagflowClient,
    connector_id: str,
    *,
    policy: str = "archive_sources",
) -> None:
    row = await get_connector(db, member, connector_id)
    if not await has_kb_permission(db, member, row.knowledge_base_id, KbPermission.manage.value):
        raise ForbiddenError()
    if policy not in {"archive_sources", "detach_sources", "delete_sources"}:
        raise BadRequestError(message="无效删除策略", message_key="errors.knowledge.connector_delete_policy_invalid")
    row.status = ConnectorStatus.deleting.value
    await db.flush()

    result = await db.execute(
        select(SourceFile).where(
            SourceFile.connector_id == row.id,
            not_deleted(SourceFile),
        )
    )
    files = list(result.scalars().all())
    kb = await db.get(KnowledgeBase, row.knowledge_base_id)
    dataset_id = await runtime_binding_service.get_dataset_id(db, kb) if kb else None

    if policy == "archive_sources":
        for sf in files:
            if sf.archived_at is None:
                sf.archived_at = _now()
            sf.archive_reason = ArchiveReason.connector_deleted.value
            sf.sync_state = SourceSyncState.stale.value
            if dataset_id and sf.active_version_id:
                from app.models.source_file_version import SourceFileVersion

                version = await db.get(SourceFileVersion, sf.active_version_id)
                if version and version.ragflow_document_id:
                    try:
                        await ragflow.set_document_enabled(dataset_id, version.ragflow_document_id, False)
                    except Exception:
                        pass
    elif policy == "detach_sources":
        for sf in files:
            sf.source_kind = SourceKind.manual.value
            sf.connector_id = None
            sf.external_object_id = None
            sf.sync_state = SourceSyncState.detached.value
    elif policy == "delete_sources":
        for sf in files:
            if dataset_id and sf.active_version_id:
                from app.models.source_file_version import SourceFileVersion

                version = await db.get(SourceFileVersion, sf.active_version_id)
                if version and version.ragflow_document_id:
                    try:
                        await ragflow.set_document_enabled(
                            dataset_id, version.ragflow_document_id, False
                        )
                    except Exception:
                        pass
            sf.soft_delete()

    objs = await db.execute(
        select(ConnectorSourceObject).where(
            ConnectorSourceObject.connector_id == row.id,
            not_deleted(ConnectorSourceObject),
        )
    )
    for obj in objs.scalars().all():
        obj.soft_delete()

    provider = get_credential_provider()
    await provider.delete(db, connector_id=row.id)
    row.soft_delete()
    await write_audit(
        db,
        org_id=member.org_id,
        member_id=member.member_id,
        action=AuditAction.connector_delete.value,
        resource_type="connector",
        resource_id=connector_id,
        details={"policy": policy},
    )
    await db.commit()


async def list_sync_runs(
    db: AsyncSession,
    member: KnowledgePrincipal,
    connector_id: str,
    *,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[ConnectorSyncRun], int]:
    await get_connector(db, member, connector_id)
    filters = [ConnectorSyncRun.connector_id == connector_id, not_deleted(ConnectorSyncRun)]
    total = await db.scalar(select(func.count()).select_from(ConnectorSyncRun).where(*filters)) or 0
    result = await db.execute(
        select(ConnectorSyncRun)
        .where(*filters)
        .order_by(ConnectorSyncRun.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(result.scalars().all()), int(total)


async def get_sync_run(
    db: AsyncSession, member: KnowledgePrincipal, connector_id: str, run_id: str
) -> ConnectorSyncRun:
    await get_connector(db, member, connector_id)
    run = await db.get(ConnectorSyncRun, run_id)
    if run is None or run.deleted_at is not None or run.connector_id != connector_id:
        raise NotFoundError(message="SyncRun 不存在", message_key="errors.knowledge.connector_sync_run_not_found")
    return run


async def cancel_sync_run(
    db: AsyncSession, member: KnowledgePrincipal, connector_id: str, run_id: str
) -> ConnectorSyncRun:
    run = await get_sync_run(db, member, connector_id, run_id)
    connector = await get_connector(db, member, connector_id)
    if not await has_kb_permission(db, member, connector.knowledge_base_id, KbPermission.manage.value):
        raise ForbiddenError()
    if run.status in {
        ConnectorSyncRunStatus.completed.value,
        ConnectorSyncRunStatus.failed.value,
        ConnectorSyncRunStatus.cancelled.value,
    }:
        raise BadRequestError(message="当前状态不可取消", message_key="errors.knowledge.connector_sync_cancel_not_allowed")
    run.status = ConnectorSyncRunStatus.cancelled.value
    run.finished_at = _now()
    await db.commit()
    await db.refresh(run)
    return run


async def retry_sync_run(
    db: AsyncSession, member: KnowledgePrincipal, connector_id: str, run_id: str
) -> ConnectorSyncRun:
    run = await get_sync_run(db, member, connector_id, run_id)
    connector = await get_connector(db, member, connector_id)
    if not await has_kb_permission(db, member, connector.knowledge_base_id, KbPermission.manage.value):
        raise ForbiddenError()
    if run.status not in {ConnectorSyncRunStatus.failed.value, ConnectorSyncRunStatus.cancelled.value}:
        raise BadRequestError(message="当前状态不可重试", message_key="errors.knowledge.connector_sync_retry_not_allowed")
    return await trigger_sync(db, member, connector_id, trigger=run.trigger or ConnectorSyncTrigger.manual.value)


async def list_objects(
    db: AsyncSession,
    member: KnowledgePrincipal,
    connector_id: str,
    *,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[ConnectorSourceObject], int]:
    await get_connector(db, member, connector_id)
    filters = [ConnectorSourceObject.connector_id == connector_id, not_deleted(ConnectorSourceObject)]
    total = await db.scalar(select(func.count()).select_from(ConnectorSourceObject).where(*filters)) or 0
    result = await db.execute(
        select(ConnectorSourceObject)
        .where(*filters)
        .order_by(ConnectorSourceObject.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(result.scalars().all()), int(total)


async def get_object(
    db: AsyncSession, member: KnowledgePrincipal, connector_id: str, object_id: str
) -> ConnectorSourceObject:
    await get_connector(db, member, connector_id)
    obj = await db.get(ConnectorSourceObject, object_id)
    if obj is None or obj.deleted_at is not None or obj.connector_id != connector_id:
        raise NotFoundError(message="SourceObject 不存在", message_key="errors.knowledge.connector_object_not_found")
    return obj


async def build_adapter(db: AsyncSession, connector: KnowledgeSourceConnector):
    cls = get_connector_class(connector.connector_type)
    credentials: dict[str, Any] | None = None
    try:
        credentials = await get_credential_provider().get(db, connector_id=connector.id)
    except NotFoundError:
        credentials = None
    return cls(connector.config or {}, credentials=credentials)


async def schedule_due_connectors(db: AsyncSession) -> list[ConnectorSyncRun]:
    now = _now()
    result = await db.execute(
        select(KnowledgeSourceConnector).where(
            KnowledgeSourceConnector.status == ConnectorStatus.active.value,
            KnowledgeSourceConnector.sync_mode == ConnectorSyncMode.interval.value,
            KnowledgeSourceConnector.next_sync_at.is_not(None),
            KnowledgeSourceConnector.next_sync_at <= now,
            not_deleted(KnowledgeSourceConnector),
        )
    )
    created: list[ConnectorSyncRun] = []
    for connector in result.scalars().all():
        active = await db.execute(
            select(ConnectorSyncRun).where(
                ConnectorSyncRun.connector_id == connector.id,
                ConnectorSyncRun.status.in_(
                    [
                        ConnectorSyncRunStatus.pending.value,
                        ConnectorSyncRunStatus.discovering.value,
                        ConnectorSyncRunStatus.applying.value,
                        ConnectorSyncRunStatus.waiting_ingestion.value,
                    ]
                ),
                not_deleted(ConnectorSyncRun),
            )
        )
        if active.scalar_one_or_none():
            continue
        run = ConnectorSyncRun(
            connector_id=connector.id,
            status=ConnectorSyncRunStatus.pending.value,
            trigger=ConnectorSyncTrigger.interval.value,
            cursor_before=dict(connector.sync_cursor) if connector.sync_cursor else None,
            metrics={},
            next_run_at=now,
        )
        db.add(run)
        connector.last_sync_started_at = now
        interval = int(connector.sync_interval_seconds or MIN_SYNC_INTERVAL_SECONDS)
        connector.next_sync_at = now + timedelta(seconds=max(interval, MIN_SYNC_INTERVAL_SECONDS))
        created.append(run)
    if created:
        await db.commit()
        for run in created:
            await db.refresh(run)
    return created
