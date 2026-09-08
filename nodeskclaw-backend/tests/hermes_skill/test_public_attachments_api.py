import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.responses import JSONResponse

from app.api.attachments import upload_attachment
from app.core.exceptions import BadRequestError
from app.models.hermes_skill.skill_run_public_attachment import SkillRunPublicAttachment
from app.services import storage_service
from app.services.hermes_skill.public_attachment_service import (
    PublicAttachmentContractError,
    prove_org_user_attachment,
    upload_public_attachment,
)


def _mock_user_org():
    user = MagicMock()
    user.id = "user-1"
    org = MagicMock()
    org.id = "org-1"
    return user, org


def _file(name="report.pdf", content_type="application/pdf"):
    file = MagicMock()
    file.filename = name
    file.content_type = content_type
    file.read = AsyncMock(side_effect=[b"hello", b""])
    return file


def _canonical(result) -> tuple[int, dict]:
    assert isinstance(result, JSONResponse)
    payload = json.loads(result.body.decode())
    assert set(payload) == {"error_code", "message_key", "message"}
    assert isinstance(payload["error_code"], str)
    assert "code" not in payload
    assert "data" not in payload
    return result.status_code, payload


def _db():
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.execute = AsyncMock()
    return db


@pytest.mark.asyncio
# @lat: [[architecture/skill-agent#RM-18 Public Attachment Input]]
async def test_upload_attachment_returns_bare_receipt_without_workspace():
    db = _db()
    user_org = _mock_user_org()
    receipt = {
        "attachment_ref": "att_abc",
        "name": "report.pdf",
        "size_bytes": 5,
        "checksum_sha256": "aaa",
        "content_type": "application/pdf",
        "expires_at": "2026-09-09T00:00:00Z",
    }
    with patch("app.api.attachments.PermissionChecker.require_permission", new=AsyncMock()), \
         patch("app.api.attachments.upload_public_attachment", new=AsyncMock(return_value=receipt)) as upload:
        result = await upload_attachment(file=_file(), user_org=user_org, db=db)
    assert result == receipt
    assert "workspace_id" not in result
    assert "code" not in result
    assert "data" not in result
    upload.assert_awaited_once()


@pytest.mark.asyncio
async def test_upload_attachment_maps_contract_error_to_canonical_envelope():
    db = _db()
    exc = PublicAttachmentContractError(
        413,
        "ATTACHMENT_TOO_LARGE",
        "errors.run.attachment_too_large",
        "too large",
    )
    with patch("app.api.attachments.PermissionChecker.require_permission", new=AsyncMock()), \
         patch("app.api.attachments.upload_public_attachment", new=AsyncMock(side_effect=exc)):
        result = await upload_attachment(file=_file(), user_org=_mock_user_org(), db=db)
    status, payload = _canonical(result)
    assert status == 413
    assert payload["error_code"] == "ATTACHMENT_TOO_LARGE"


@pytest.mark.asyncio
async def test_upload_public_attachment_success_omits_storage_and_workspace():
    db = _db()
    captured = {}

    async def _refresh(row):
        captured["row"] = row

    db.refresh = AsyncMock(side_effect=_refresh)
    with patch(
        "app.services.hermes_skill.public_attachment_service.validate_upload_request",
        new=AsyncMock(),
    ), patch(
        "app.services.hermes_skill.public_attachment_service.file_scan_service.get_initial_scan_state",
        new=AsyncMock(return_value=("skipped", "scan_disabled")),
    ), patch(
        "app.services.hermes_skill.public_attachment_service.get_surface_max_bytes",
        new=AsyncMock(return_value=1024),
    ), patch(
        "app.services.hermes_skill.public_attachment_service.storage_service.upload_file_object",
        new=AsyncMock(return_value=("workspace-files/skill-run-att/org-1/user-1/x/report.pdf", 5, "deadbeef")),
    ) as upload, patch(
        "app.services.hermes_skill.public_attachment_service.config_service.get_config",
        new=AsyncMock(return_value="7"),
    ):
        result = await upload_public_attachment(db, org_id="org-1", user_id="user-1", file=_file())
    assert result["attachment_ref"].startswith("att_")
    assert result["checksum_sha256"] == "deadbeef"
    assert result["size_bytes"] == 5
    assert "expires_at" in result
    assert "workspace_id" not in result
    assert "storage_key" not in result
    assert "code" not in result
    upload.assert_awaited_once()
    assert upload.await_args.args[3] == "skill-run-att/org-1/user-1"
    row = captured["row"]
    assert not hasattr(row, "workspace_id") or getattr(row, "workspace_id", None) is None
    assert row.storage_key.startswith("workspace-files/skill-run-att/")


@pytest.mark.asyncio
async def test_upload_public_attachment_scan_blocked_does_not_store():
    db = _db()
    with patch(
        "app.services.hermes_skill.public_attachment_service.validate_upload_request",
        new=AsyncMock(),
    ), patch(
        "app.services.hermes_skill.public_attachment_service.file_scan_service.get_initial_scan_state",
        new=AsyncMock(return_value=("pending", "queued")),
    ), patch(
        "app.services.hermes_skill.public_attachment_service.storage_service.upload_file_object",
        new=AsyncMock(),
    ) as upload:
        with pytest.raises(PublicAttachmentContractError) as exc_info:
            await upload_public_attachment(db, org_id="org-1", user_id="user-1", file=_file())
    assert exc_info.value.error_code == "ATTACHMENT_SCAN_BLOCKED"
    upload.assert_not_called()
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_upload_public_attachment_type_unsupported_canonical():
    db = _db()
    with patch(
        "app.services.hermes_skill.public_attachment_service.validate_upload_request",
        new=AsyncMock(side_effect=BadRequestError("blocked", "errors.upload.file_type_blocked")),
    ):
        with pytest.raises(PublicAttachmentContractError) as exc_info:
            await upload_public_attachment(db, org_id="org-1", user_id="user-1", file=_file(name="x.exe"))
    assert exc_info.value.error_code == "ATTACHMENT_TYPE_UNSUPPORTED"
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_upload_public_attachment_too_large_canonical():
    db = _db()
    with patch(
        "app.services.hermes_skill.public_attachment_service.validate_upload_request",
        new=AsyncMock(),
    ), patch(
        "app.services.hermes_skill.public_attachment_service.file_scan_service.get_initial_scan_state",
        new=AsyncMock(return_value=("skipped", "scan_disabled")),
    ), patch(
        "app.services.hermes_skill.public_attachment_service.get_surface_max_bytes",
        new=AsyncMock(return_value=1),
    ), patch(
        "app.services.hermes_skill.public_attachment_service.storage_service.upload_file_object",
        new=AsyncMock(side_effect=storage_service.UploadTooLargeError(1, 99)),
    ):
        with pytest.raises(PublicAttachmentContractError) as exc_info:
            await upload_public_attachment(db, org_id="org-1", user_id="user-1", file=_file())
    assert exc_info.value.error_code == "ATTACHMENT_TOO_LARGE"
    assert exc_info.value.status_code == 413


@pytest.mark.asyncio
async def test_prove_org_user_attachment_rejects_portal_and_chat_shapes():
    db = _db()
    for ref in ("file-uuid", "chat_attachment:abc", "artifact_id", "att"):
        with pytest.raises(PublicAttachmentContractError) as exc_info:
            await prove_org_user_attachment(db, org_id="org-1", user_id="user-1", attachment_ref=ref)
        assert exc_info.value.error_code == "ATTACHMENT_REF_INVALID"


@pytest.mark.asyncio
async def test_prove_org_user_attachment_scope_and_expiry():
    db = _db()
    other = SkillRunPublicAttachment(
        org_id="org-2",
        user_id="user-2",
        attachment_ref="att_other",
        original_name="a.pdf",
        size_bytes=1,
        content_type="application/pdf",
        storage_key="k",
        checksum_sha256="aa",
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        scan_status="skipped",
        scan_reason="scan_disabled",
    )
    loaded = MagicMock()
    loaded.scalar_one_or_none.return_value = other
    db.execute = AsyncMock(return_value=loaded)
    with pytest.raises(PublicAttachmentContractError) as exc_info:
        await prove_org_user_attachment(db, org_id="org-1", user_id="user-1", attachment_ref="att_other")
    assert exc_info.value.error_code == "ATTACHMENT_SCOPE_DENIED"

    expired = SimpleNamespace(
        org_id="org-1",
        user_id="user-1",
        attachment_ref="att_old",
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        scan_status="skipped",
    )
    loaded.scalar_one_or_none.return_value = expired
    with pytest.raises(PublicAttachmentContractError) as exc_info:
        await prove_org_user_attachment(db, org_id="org-1", user_id="user-1", attachment_ref="att_old")
    assert exc_info.value.error_code == "ATTACHMENT_EXPIRED"
