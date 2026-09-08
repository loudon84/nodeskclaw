from __future__ import annotations

import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BadRequestError
from app.models.base import not_deleted
from app.models.hermes_skill.skill_run_public_attachment import SkillRunPublicAttachment
from app.services import config_service, file_scan_service, storage_service
from app.services.upload_policy_service import get_surface_max_bytes, validate_upload_request

PUBLIC_ATTACHMENT_REF_RE = re.compile(r"^att_[A-Za-z0-9_-]+$")
BLOCKING_SCAN_STATUSES = frozenset({"pending", "blocked", "failed"})
CHAT_ATTACHMENT_SURFACE = "chat_attachment"


class PublicAttachmentContractError(Exception):
    def __init__(self, status_code: int, error_code: str, message_key: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.message_key = message_key
        self.message = message


def _rfc3339(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _contract_error(status_code: int, error_code: str, message_key: str, message: str) -> PublicAttachmentContractError:
    return PublicAttachmentContractError(status_code, error_code, message_key, message)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _storage_workspace_id(org_id: str, user_id: str) -> str:
    return f"skill-run-att/{org_id}/{user_id}"


def _new_attachment_ref() -> str:
    return f"att_{secrets.token_urlsafe(24)}"


async def _retention_days(db: AsyncSession) -> int:
    raw = await config_service.get_config("upload_chat_attachment_retention_days", db)
    if raw is None or str(raw).strip() == "":
        return int(settings.UPLOAD_CHAT_ATTACHMENT_RETENTION_DAYS)
    days = int(raw)
    if days <= 0:
        return int(settings.UPLOAD_CHAT_ATTACHMENT_RETENTION_DAYS)
    return days


def public_receipt(row: SkillRunPublicAttachment) -> dict[str, Any]:
    return {
        "attachment_ref": row.attachment_ref,
        "name": row.original_name,
        "size_bytes": int(row.size_bytes),
        "checksum_sha256": row.checksum_sha256,
        "content_type": row.content_type,
        "expires_at": _rfc3339(row.expires_at),
    }


# @lat: [[architecture/skill-agent#RM-18 Public Attachment Input]]
async def upload_public_attachment(
    db: AsyncSession,
    *,
    org_id: str,
    user_id: str,
    file,
) -> dict[str, Any]:
    filename = getattr(file, "filename", None) or "unnamed"
    content_type = getattr(file, "content_type", None) or "application/octet-stream"
    try:
        await validate_upload_request(
            CHAT_ATTACHMENT_SURFACE,
            filename=filename,
            content_type=content_type,
            size=0,
            db=db,
        )
    except storage_service.StorageUnavailableError as exc:
        raise _contract_error(
            503,
            "ATTACHMENT_SCAN_BLOCKED",
            "errors.run.attachment_scan_blocked",
            f"文件存储服务不可用：{exc.reason_code}",
        ) from exc
    except storage_service.UploadTooLargeError as exc:
        raise _contract_error(
            413,
            "ATTACHMENT_TOO_LARGE",
            "errors.run.attachment_too_large",
            f"文件大小超过限制（最大 {exc.limit_bytes // 1024 // 1024}MB）",
        ) from exc
    except BadRequestError as exc:
        raise _contract_error(
            400,
            "ATTACHMENT_TYPE_UNSUPPORTED",
            "errors.run.attachment_type_unsupported",
            exc.message,
        ) from exc

    try:
        scan_status, scan_reason = await file_scan_service.get_initial_scan_state(db)
    except file_scan_service.ScannerUnavailableError as exc:
        raise _contract_error(
            503,
            "ATTACHMENT_SCAN_BLOCKED",
            "errors.run.attachment_scan_blocked",
            "文件扫描服务不可用",
        ) from exc
    if scan_status in BLOCKING_SCAN_STATUSES:
        raise _contract_error(
            403,
            "ATTACHMENT_SCAN_BLOCKED",
            "errors.run.attachment_scan_blocked",
            "文件未通过安全扫描",
        )

    max_bytes = await get_surface_max_bytes(CHAT_ATTACHMENT_SURFACE, db)
    try:
        storage_key, file_size, checksum = await storage_service.upload_file_object(
            file,
            filename,
            content_type,
            _storage_workspace_id(org_id, user_id),
            max_bytes=max_bytes,
        )
    except storage_service.UploadTooLargeError as exc:
        raise _contract_error(
            413,
            "ATTACHMENT_TOO_LARGE",
            "errors.run.attachment_too_large",
            f"文件大小超过限制（最大 {exc.limit_bytes // 1024 // 1024}MB）",
        ) from exc
    except storage_service.StorageUnavailableError as exc:
        raise _contract_error(
            503,
            "ATTACHMENT_SCAN_BLOCKED",
            "errors.run.attachment_scan_blocked",
            f"文件存储服务不可用：{exc.reason_code}",
        ) from exc

    expires_at = _now() + timedelta(days=await _retention_days(db))
    row = SkillRunPublicAttachment(
        org_id=org_id,
        user_id=user_id,
        attachment_ref=_new_attachment_ref(),
        original_name=filename,
        size_bytes=file_size,
        content_type=content_type,
        storage_key=storage_key,
        checksum_sha256=checksum,
        expires_at=expires_at,
        scan_status=scan_status,
        scan_reason=scan_reason,
        scanned_at=_now() if scan_status == "skipped" else None,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return public_receipt(row)


async def prove_org_user_attachment(
    db: AsyncSession,
    *,
    org_id: str,
    user_id: str,
    attachment_ref: str,
) -> SkillRunPublicAttachment:
    ref = str(attachment_ref or "").strip()
    if not PUBLIC_ATTACHMENT_REF_RE.fullmatch(ref):
        raise _contract_error(
            400,
            "ATTACHMENT_REF_INVALID",
            "errors.run.attachment_ref_invalid",
            "附件引用格式无效",
        )
    result = await db.execute(
        select(SkillRunPublicAttachment).where(
            SkillRunPublicAttachment.attachment_ref == ref,
            not_deleted(SkillRunPublicAttachment),
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise _contract_error(
            404,
            "ATTACHMENT_NOT_FOUND",
            "errors.run.attachment_not_found",
            "附件引用不存在",
        )
    if row.org_id != org_id or row.user_id != user_id:
        raise _contract_error(
            403,
            "ATTACHMENT_SCOPE_DENIED",
            "errors.run.attachment_scope_denied",
            "附件引用不属于当前用户",
        )
    expires_at = row.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= _now():
        raise _contract_error(
            410,
            "ATTACHMENT_EXPIRED",
            "errors.run.attachment_expired",
            "附件引用已过期",
        )
    if (row.scan_status or "") in BLOCKING_SCAN_STATUSES:
        raise _contract_error(
            403,
            "ATTACHMENT_SCAN_BLOCKED",
            "errors.run.attachment_scan_blocked",
            "文件未通过安全扫描",
        )
    return row
