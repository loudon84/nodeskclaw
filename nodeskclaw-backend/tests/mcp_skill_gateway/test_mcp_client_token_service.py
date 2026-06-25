import hashlib
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.mcp_client_token import McpClientToken
from app.services.mcp_skill_gateway.mcp_client_token_service import McpClientTokenService


def _make_scalar_result(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


@pytest.mark.asyncio
async def test_create_token_format_and_hash():
    db = AsyncMock()
    service = McpClientTokenService(db)

    plain, record = await service.create_token(
        org_id="org-1",
        hermes_agent_id="agent-1",
        instance_name="common-writer",
        created_by="user-1",
        expires_days=180,
    )

    assert plain.startswith("ndsk_mcp_common_writer_")
    assert "." in plain
    prefix, secret = plain.split(".", 1)
    assert record.token_prefix == prefix
    assert record.token_hash == hashlib.sha256(plain.encode()).hexdigest()
    assert secret
    assert record.service_account_user_id == "user-1"
    db.add.assert_called_once()
    db.flush.assert_awaited()


@pytest.mark.asyncio
async def test_verify_token_success():
    plain = "ndsk_mcp_demo_abcd1234.secretpart"
    prefix = "ndsk_mcp_demo_abcd1234"
    record = McpClientToken(
        id="tok-1",
        org_id="org-1",
        name="demo",
        token_prefix=prefix,
        token_hash=hashlib.sha256(plain.encode()).hexdigest(),
        created_by="user-1",
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_make_scalar_result(record))
    service = McpClientTokenService(db)

    verified = await service.verify_token(plain)

    assert verified is record
    assert record.last_used_at is not None


@pytest.mark.asyncio
async def test_verify_token_rejects_revoked():
    plain = "ndsk_mcp_demo_abcd1234.secretpart"
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_make_scalar_result(None))
    service = McpClientTokenService(db)

    assert await service.verify_token(plain) is None


@pytest.mark.asyncio
async def test_revoke_token_sets_revoked_at():
    record = McpClientToken(
        id="tok-1",
        org_id="org-1",
        name="demo",
        token_prefix="ndsk_mcp_demo_abcd1234",
        token_hash="abc",
        created_by="user-1",
    )
    db = AsyncMock()
    service = McpClientTokenService(db)
    service.get_token_by_id = AsyncMock(return_value=record)

    revoked = await service.revoke_token("tok-1")

    assert revoked.revoked_at is not None


@pytest.mark.asyncio
async def test_is_expired():
    record = McpClientToken(
        id="tok-1",
        org_id="org-1",
        name="demo",
        token_prefix="p",
        token_hash="h",
        created_by="user-1",
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    assert McpClientTokenService.is_expired(record) is True
