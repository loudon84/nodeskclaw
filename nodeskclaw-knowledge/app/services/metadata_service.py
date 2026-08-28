"""Business metadata schema validation and RAGFlow sync helpers."""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, ValidationError
from app.integrations.ragflow.exceptions import RagflowError
from app.models.base import not_deleted
from app.models.enums import AccessPlanKind, AuditAction, FilePermission, KbPermission
from app.models.knowledge_base import KnowledgeBase
from app.models.source_file import SourceFile
from app.models.source_file_version import SourceFileVersion
from app.schemas.principal import KnowledgePrincipal
from app.services import knowledge_base_service, runtime_binding_service, source_file_service
from app.services.audit_service import write_audit
from app.services.permission_service import AccessPlan, has_file_permission, has_kb_permission

ALLOWED_FIELD_TYPES = frozenset({"string", "number", "boolean", "date", "enum", "multi_enum"})
ACL_RESERVED_KEYS = frozenset(
    {
        "acl",
        "permission",
        "permissions",
        "allowed_users",
        "allowed_roles",
        "subject_type",
        "subject_id",
        "effect",
        "manage_acl",
        "acl_version",
    }
)
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# @lat: [[knowledge-objects#Metadata Governance]]
def build_meta_fields(
    *,
    source_file_id: str,
    file_version_id: str,
    knowledge_base_id: str,
    org_id: str,
    metadata: dict[str, Any] | None = None,
    metadata_revision: int = 0,
    source_kind: str | None = None,
    connector_id: str | None = None,
    external_object_id: str | None = None,
    source_revision: str | None = None,
) -> dict[str, str]:
    fields: dict[str, str] = {
        "nk_source_file_id": source_file_id,
        "nk_file_version_id": file_version_id,
        "nk_knowledge_base_id": knowledge_base_id,
        "nk_org_id": org_id,
        "nk_metadata_revision": str(int(metadata_revision or 0)),
    }
    if source_kind:
        fields["nk_source_kind"] = source_kind
    if connector_id:
        fields["nk_connector_id"] = connector_id
    if external_object_id:
        fields["nk_external_object_id"] = external_object_id
    if source_revision:
        fields["nk_source_revision"] = source_revision
    for key, value in (metadata or {}).items():
        if key.startswith("nk_") or key in ACL_RESERVED_KEYS or key.startswith("acl_"):
            continue
        if isinstance(value, list):
            fields[f"biz_{key}"] = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        elif isinstance(value, bool):
            fields[f"biz_{key}"] = "true" if value else "false"
        elif value is None:
            continue
        else:
            fields[f"biz_{key}"] = str(value)
    return fields


def resolve_connector_managed_metadata_keys(connector_config: dict[str, Any] | None) -> set[str]:
    config = connector_config or {}
    explicit = config.get("connector_managed_metadata_keys")
    keys: set[str] = set()
    if isinstance(explicit, list):
        keys.update(str(k) for k in explicit if k)
    mapping = config.get("metadata_mapping")
    if isinstance(mapping, dict):
        keys.update(str(v) for v in mapping.values() if v)
    return keys


def _metadata_invalid(message: str, *, details: dict[str, Any] | None = None) -> ValidationError:
    return ValidationError(
        message=message,
        message_key="errors.knowledge.metadata_invalid",
        details=details,
    )


def _reject_client_key(key: str) -> None:
    if key.startswith("nk_"):
        raise _metadata_invalid("禁止写入系统保留 metadata 键", details={"key": key})
    if key in ACL_RESERVED_KEYS or key.startswith("acl_"):
        raise _metadata_invalid("禁止写入 ACL 相关 metadata 键", details={"key": key})


def parse_metadata_form(raw: str | None) -> dict[str, Any]:
    if raw is None or raw.strip() == "":
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise _metadata_invalid("metadata 必须是合法 JSON 对象") from exc
    if not isinstance(parsed, dict):
        raise _metadata_invalid("metadata 必须是 JSON 对象")
    return parsed


def validate_schema_definition(schema: dict[str, Any] | None) -> dict[str, Any] | None:
    return normalize_metadata_schema(schema)


def normalize_metadata_schema(schema: dict[str, Any] | None) -> dict[str, Any] | None:
    if schema is None:
        return None
    if not isinstance(schema, dict):
        raise _metadata_invalid("metadata_schema 必须是对象")
    fields = schema.get("fields")
    if fields is None:
        raise _metadata_invalid("metadata_schema.fields 必填")
    if not isinstance(fields, list):
        raise _metadata_invalid("metadata_schema.fields 必须是数组")
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for idx, raw_field in enumerate(fields):
        if not isinstance(raw_field, dict):
            raise _metadata_invalid("metadata_schema.fields 项必须是对象", details={"index": idx})
        key = raw_field.get("key")
        field_type = raw_field.get("type")
        if not isinstance(key, str) or not key:
            raise _metadata_invalid("metadata field.key 无效", details={"index": idx})
        _reject_client_key(key)
        if key in seen:
            raise _metadata_invalid("metadata field.key 重复", details={"key": key})
        seen.add(key)
        if field_type not in ALLOWED_FIELD_TYPES:
            raise _metadata_invalid("不支持的 metadata field.type", details={"key": key, "type": field_type})
        entry: dict[str, Any] = {
            "key": key,
            "type": field_type,
            "required": bool(raw_field.get("required", False)),
        }
        options = raw_field.get("options")
        if field_type in {"enum", "multi_enum"}:
            if not isinstance(options, list) or not options:
                raise _metadata_invalid("enum/multi_enum 必须提供 options", details={"key": key})
            if not all(isinstance(item, (str, int, float, bool)) for item in options):
                raise _metadata_invalid("options 取值类型非法", details={"key": key})
            entry["options"] = list(options)
        elif options is not None:
            raise _metadata_invalid("仅 enum/multi_enum 允许 options", details={"key": key})
        normalized.append(entry)
    return {"fields": normalized}


def _schema_field_map(schema: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not schema:
        return {}
    return {f["key"]: f for f in (schema.get("fields") or []) if isinstance(f, dict) and "key" in f}


def _is_valid_date(value: Any) -> bool:
    if isinstance(value, date) and not isinstance(value, datetime):
        return True
    if isinstance(value, datetime):
        return True
    if not isinstance(value, str) or not DATE_RE.match(value):
        return False
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False


def _validate_field_value(field: dict[str, Any], value: Any) -> None:
    key = field["key"]
    field_type = field["type"]
    if field_type == "string":
        if not isinstance(value, str):
            raise _metadata_invalid("metadata 字段类型必须为 string", details={"key": key})
        return
    if field_type == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise _metadata_invalid("metadata 字段类型必须为 number", details={"key": key})
        return
    if field_type == "boolean":
        if not isinstance(value, bool):
            raise _metadata_invalid("metadata 字段类型必须为 boolean", details={"key": key})
        return
    if field_type == "date":
        if not _is_valid_date(value):
            raise _metadata_invalid("metadata 字段类型必须为 date", details={"key": key})
        return
    if field_type == "enum":
        options = field.get("options") or []
        if value not in options:
            raise _metadata_invalid("metadata enum 取值非法", details={"key": key, "value": value})
        return
    if field_type == "multi_enum":
        if not isinstance(value, list):
            raise _metadata_invalid("metadata multi_enum 必须为数组", details={"key": key})
        options = field.get("options") or []
        for item in value:
            if item not in options:
                raise _metadata_invalid("metadata multi_enum 取值非法", details={"key": key, "value": item})
        return
    raise _metadata_invalid("不支持的 metadata field.type", details={"key": key, "type": field_type})


def validate_metadata(
    metadata: dict[str, Any] | None,
    schema: dict[str, Any] | None,
    *,
    partial: bool = False,
) -> dict[str, Any]:
    return validate_metadata_values(metadata, schema, partial=partial)


def validate_metadata_values(
    metadata: dict[str, Any] | None,
    schema: dict[str, Any] | None,
    *,
    partial: bool = False,
) -> dict[str, Any]:
    data = dict(metadata or {})
    for key in data:
        _reject_client_key(key)
    field_map = _schema_field_map(schema)
    if not field_map:
        return data
    if not partial:
        for key, field in field_map.items():
            if field.get("required") and (key not in data or data[key] is None):
                raise _metadata_invalid("缺少必填 metadata 字段", details={"key": key})
    for key, value in data.items():
        if key not in field_map:
            raise _metadata_invalid("未知 metadata 字段", details={"key": key})
        if value is None:
            if field_map[key].get("required") and not partial:
                raise _metadata_invalid("缺少必填 metadata 字段", details={"key": key})
            continue
        _validate_field_value(field_map[key], value)
    return data


def validate_retrieval_filters(
    filters: dict[str, list] | None,
    schemas: list[dict[str, Any] | None],
) -> dict[str, list]:
    if not filters:
        return {}
    if not isinstance(filters, dict):
        raise _metadata_invalid("filters 必须是对象")
    normalized: dict[str, list] = {}
    for key, values in filters.items():
        _reject_client_key(key)
        if not isinstance(values, list) or not values:
            raise _metadata_invalid("filters 每个键的值必须是非空数组", details={"key": key})
        normalized[key] = list(values)

    field_maps = [_schema_field_map(schema) for schema in schemas if schema]
    if field_maps:
        known_keys = set()
        for field_map in field_maps:
            known_keys.update(field_map.keys())
        for key, values in normalized.items():
            if key not in known_keys:
                raise _metadata_invalid("filters 包含未定义字段", details={"key": key})
            for field_map in field_maps:
                field = field_map.get(key)
                if not field:
                    continue
                if field["type"] in {"enum", "multi_enum"}:
                    options = field.get("options") or []
                    for value in values:
                        if value not in options:
                            raise _metadata_invalid(
                                "filters 取值不在 schema options 内",
                                details={"key": key, "value": value},
                            )
    return normalized


def metadata_matches_filters(metadata: dict[str, Any] | None, filters: dict[str, list]) -> bool:
    if not filters:
        return True
    data = metadata or {}
    for key, expected_values in filters.items():
        actual = data.get(key)
        if actual is None:
            return False
        if isinstance(actual, list):
            if not any(item in expected_values for item in actual):
                return False
        elif actual not in expected_values:
            return False
    return True


async def get_metadata_schema(
    db: AsyncSession,
    member: KnowledgePrincipal,
    kb_id: str,
) -> dict[str, Any] | None:
    kb = await knowledge_base_service.get_knowledge_base(db, member, kb_id)
    return kb.metadata_schema


async def put_metadata_schema(
    db: AsyncSession,
    member: KnowledgePrincipal,
    kb_id: str,
    schema: dict[str, Any] | None,
) -> dict[str, Any] | None:
    kb = await knowledge_base_service.get_knowledge_base(db, member, kb_id)
    if not await has_kb_permission(db, member, kb.id, KbPermission.update.value) and not await has_kb_permission(
        db, member, kb.id, KbPermission.manage.value
    ):
        raise ForbiddenError()
    normalized = validate_schema_definition(schema)
    kb.metadata_schema = normalized
    await write_audit(
        db,
        org_id=member.org_id,
        member_id=member.member_id,
        action=AuditAction.metadata_schema_update.value,
        resource_type="knowledge_base",
        resource_id=kb.id,
        details={"metadata_schema": normalized},
    )
    await db.commit()
    await db.refresh(kb)
    return kb.metadata_schema


async def get_source_file_metadata(
    db: AsyncSession,
    member: KnowledgePrincipal,
    source_file_id: str,
) -> dict[str, Any]:
    sf = await source_file_service.get_source_file(db, member, source_file_id)
    return {
        "metadata": dict(sf.metadata_ or {}),
        "metadata_revision": int(sf.metadata_revision or 0),
    }


async def patch_source_file_metadata(
    db: AsyncSession,
    member: KnowledgePrincipal,
    ragflow: RagflowRuntimeAdapter,
    source_file_id: str,
    metadata_patch: dict[str, Any],
) -> dict[str, Any]:
    sf = await source_file_service.get_source_file(db, member, source_file_id)
    if not await has_file_permission(db, member, sf, FilePermission.update.value) and not await has_kb_permission(
        db, member, sf.knowledge_base_id, KbPermission.manage.value
    ):
        raise ForbiddenError()
    kb = await knowledge_base_service.get_knowledge_base(db, member, sf.knowledge_base_id)

    if sf.source_kind == "connector" and sf.connector_id and metadata_patch:
        from app.models.connector import KnowledgeSourceConnector

        connector = await db.get(KnowledgeSourceConnector, sf.connector_id)
        managed = resolve_connector_managed_metadata_keys(connector.config if connector else None)
        if managed:
            conflicts = sorted(k for k in metadata_patch.keys() if k in managed)
            if conflicts:
                raise ValidationError(
                    message="禁止覆盖 Connector 托管 metadata 字段",
                    message_key="errors.knowledge.connector_managed_metadata",
                    details={"keys": conflicts},
                )

    merged = {**(sf.metadata_ or {}), **(metadata_patch or {})}
    for key, value in list(merged.items()):
        if value is None:
            merged.pop(key, None)
    validated = validate_metadata_values(merged, kb.metadata_schema, partial=False)
    next_revision = int(sf.metadata_revision or 0) + 1
    sf.metadata_ = validated
    sf.metadata_revision = next_revision
    await db.flush()

    if sf.active_version_id:
        version = await db.get(SourceFileVersion, sf.active_version_id)
        dataset_id = await runtime_binding_service.get_dataset_id(db, kb)
        if version and version.ragflow_document_id and dataset_id and version.deleted_at is None:
            meta = build_meta_fields(
                source_file_id=sf.id,
                file_version_id=version.id,
                knowledge_base_id=kb.id,
                org_id=sf.org_id,
                metadata=validated,
                metadata_revision=next_revision,
                source_kind=sf.source_kind,
                connector_id=sf.connector_id,
                external_object_id=sf.external_object_id,
                source_revision=sf.source_revision,
            )
            try:
                await ragflow.update_document_metadata(dataset_id, version.ragflow_document_id, meta)
            except RagflowError as exc:
                await db.rollback()
                raise ValidationError(
                    message=exc.message,
                    message_key=exc.message_key or "errors.knowledge.metadata_invalid",
                ) from exc

    await write_audit(
        db,
        org_id=member.org_id,
        member_id=member.member_id,
        action=AuditAction.metadata_update.value,
        resource_type="source_file",
        resource_id=sf.id,
        details={"metadata": validated, "metadata_revision": next_revision},
    )
    await db.commit()
    await db.refresh(sf)
    return {
        "metadata": dict(sf.metadata_ or {}),
        "metadata_revision": int(sf.metadata_revision or 0),
    }


async def apply_metadata_filters_to_access_plan(
    db: AsyncSession,
    access_plan: AccessPlan,
    filters: dict[str, list],
    knowledge_bases: list[KnowledgeBase],
) -> AccessPlan:
    if not filters:
        return access_plan
    if access_plan.kind == AccessPlanKind.no_access:
        return access_plan

    kb_by_id = {kb.id: kb for kb in knowledge_bases}
    allowed_ids = list(access_plan.source_file_ids)
    if not allowed_ids:
        return AccessPlan(kind=AccessPlanKind.no_access)

    result = await db.execute(
        select(SourceFile).where(
            SourceFile.id.in_(allowed_ids),
            not_deleted(SourceFile),
        )
    )
    files = list(result.scalars().all())
    matched = [sf for sf in files if metadata_matches_filters(sf.metadata_, filters)]
    if not matched:
        return AccessPlan(kind=AccessPlanKind.no_access)

    partial_slices: list[dict] = []
    filtered_document_ids: list[str] = []
    matched_ids: list[str] = []
    dataset_ids: list[str] = []

    by_kb: dict[str, list[SourceFile]] = {}
    for sf in matched:
        by_kb.setdefault(sf.knowledge_base_id, []).append(sf)

    for kb_id, kb_files in by_kb.items():
        kb = kb_by_id.get(kb_id)
        if kb is None:
            continue
        dataset_id = await runtime_binding_service.get_dataset_id(db, kb)
        if not dataset_id:
            continue
        doc_ids: list[str] = []
        for sf in kb_files:
            matched_ids.append(sf.id)
            if not sf.active_version_id:
                continue
            version = await db.get(SourceFileVersion, sf.active_version_id)
            if version and version.ragflow_document_id and version.deleted_at is None:
                doc_ids.append(version.ragflow_document_id)
                filtered_document_ids.append(version.ragflow_document_id)
        if doc_ids:
            dataset_ids.append(dataset_id)
            partial_slices.append(
                {
                    "kind": "filtered_documents",
                    "dataset_id": dataset_id,
                    "knowledge_base_id": kb.id,
                    "document_ids": doc_ids,
                }
            )

    if not partial_slices:
        return AccessPlan(
            kind=AccessPlanKind.filtered_access,
            dataset_ids=[],
            document_ids=[],
            source_file_ids=list(dict.fromkeys(matched_ids)),
            knowledge_base_ids=list(by_kb.keys()),
            full_dataset_ids=[],
            partial_slices=[],
        )

    return AccessPlan(
        kind=AccessPlanKind.filtered_access,
        dataset_ids=list(dict.fromkeys(dataset_ids)),
        document_ids=list(dict.fromkeys(filtered_document_ids)),
        source_file_ids=list(dict.fromkeys(matched_ids)),
        knowledge_base_ids=list(by_kb.keys()),
        full_dataset_ids=[],
        partial_slices=partial_slices,
    )
