import hashlib
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.mcp_client_token import McpClientToken
from app.models.organization import Organization
from app.models.user import User
from app.services.mcp_skill_gateway.auth import resolve_mcp_client_token, resolve_mcp_user


def _scalar(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


@pytest.mark.asyncio
async def test_resolve_mcp_client_token_success():
    plain = "ndsk_mcp_writer_abcd1234.secrettoken"
    prefix = "ndsk_mcp_writer_abcd1234"
    token_record = McpClientToken(
        id="tok-1",
        org_id="org-1",
        name="demo",
        token_prefix=prefix,
        token_hash=hashlib.sha256(plain.encode()).hexdigest(),
        created_by="user-1",
        service_account_user_id="user-1",
        profile="default",
        workspace_id="default",
        scopes=["mcp:tools:list"],
        allowed_skills=["skill.a"],
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
    )
    user = User(id="user-1", email="admin@example.com", username="admin")
    org = Organization(id="org-1", name="Org", slug="org")

    db = AsyncMock()

    async def fake_execute(stmt):
        stmt_str = str(stmt)
        if "users" in stmt_str:
            return _scalar(user)
        if "organizations" in stmt_str:
            return _scalar(org)
        return _scalar(None)

    db.execute = fake_execute

    with patch(
        "app.services.mcp_skill_gateway.mcp_client_token_service.McpClientTokenService",
    ) as mock_cls:
        mock_cls.return_value.verify_token = AsyncMock(return_value=token_record)
        ctx = await resolve_mcp_client_token(plain, db)

    assert ctx is not None
    assert ctx.auth_type == "mcp_client_token"
    assert ctx.mcp_client_token_id == "tok-1"
    assert ctx.profile == "default"
    assert ctx.allowed_skills == ["skill.a"]


@pytest.mark.asyncio
async def test_resolve_mcp_user_routes_ndsk_mcp_prefix():
    plain = "ndsk_mcp_writer_abcd1234.secrettoken"
    expected = MagicMock()
    expected.auth_type = "mcp_client_token"

    db = AsyncMock()
    with patch(
        "app.services.mcp_skill_gateway.auth.resolve_mcp_client_token",
        new=AsyncMock(return_value=expected),
    ):
        result = await resolve_mcp_user(f"Bearer {plain}", db)

    assert result is expected
