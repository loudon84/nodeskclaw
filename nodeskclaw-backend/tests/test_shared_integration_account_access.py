from types import SimpleNamespace

import pytest

from app.services.integration_account_access_resolver import IntegrationAccountAccessResolver
from app.services.integration_account_service import load_accounts_for_run
from app.services.remote_agent_provider_service import RemoteAgentRouteError


class _GrantDB:
    def __init__(self, accounts, grants=None, role="member"):
        self.accounts = {row.id: row for row in accounts}
        self.grants = grants or []
        self.role = role

    async def get(self, model, account_id):
        return self.accounts.get(account_id)

    async def execute(self, stmt):
        text = str(stmt)
        if "org_memberships" in text.lower() or "OrgMembership" in text:
            return SimpleNamespace(scalar_one_or_none=lambda: self.role)

        class Result:
            def __init__(self, rows):
                self._rows = rows

            def scalar_one_or_none(self):
                return self._rows[0] if self._rows else None

            def scalars(self):
                return SimpleNamespace(all=lambda: list(self._rows), first=lambda: self._rows[0] if self._rows else None)

        if "integration_account_grants" in text.lower() or "IntegrationAccountGrant" in text:
            return Result([grant.id for grant in self.grants] if self.grants else [])
        return Result([])


def _personal(**overrides):
    base = dict(
        id="11111111-1111-4111-8111-111111111111",
        deleted_at=None,
        org_id="org",
        user_id="user",
        owner_type="USER",
        owner_id="user",
        status="ACTIVE",
        provider="composio",
        toolkit_slug="gmail",
        connected_account_id="ca_1",
        provider_user_id="nodeskclaw:org:user",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _shared(**overrides):
    base = dict(
        id="22222222-2222-4222-8222-222222222222",
        deleted_at=None,
        org_id="org",
        user_id=None,
        owner_type="ORGANIZATION",
        owner_id="org",
        status="ACTIVE",
        provider="composio",
        toolkit_slug="gmail",
        connected_account_id="ca_shared",
        provider_user_id="nodeskclaw:org:shared",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.mark.asyncio
async def test_personal_use_still_owner_only(monkeypatch):
    async def fake_role(db, user_id, org_id):
        return "member"

    monkeypatch.setattr(
        "app.services.integration_account_access_resolver.PermissionChecker.get_user_role",
        fake_role,
    )
    monkeypatch.setattr(
        "app.services.integration_account_access_resolver.PermissionChecker.has_permission",
        lambda *a, **k: False,
    )
    row = _personal()
    resolver = IntegrationAccountAccessResolver(_GrantDB([row]))
    assert await resolver.can_use(org_id="org", user_id="user", row=row) is True
    assert await resolver.can_use(org_id="org", user_id="other", row=row) is False


@pytest.mark.asyncio
async def test_shared_requires_use_grant(monkeypatch):
    async def fake_role(db, user_id, org_id):
        return "member"

    async def fake_has(db, user_id, org_id, permission):
        return False

    monkeypatch.setattr(
        "app.services.integration_account_access_resolver.PermissionChecker.get_user_role",
        fake_role,
    )
    monkeypatch.setattr(
        "app.services.integration_account_access_resolver.PermissionChecker.has_permission",
        fake_has,
    )

    class GrantAwareDB(_GrantDB):
        async def execute(self, stmt):
            class Result:
                def scalar_one_or_none(self_inner):
                    return "grant-1" if self.grants else None

            return Result()

    shared = _shared()
    denied = IntegrationAccountAccessResolver(GrantAwareDB([shared], grants=[]))
    assert await denied.can_use(org_id="org", user_id="user", row=shared) is False
    allowed = IntegrationAccountAccessResolver(
        GrantAwareDB([shared], grants=[SimpleNamespace(id="grant-1")])
    )
    assert await allowed.can_use(org_id="org", user_id="user", row=shared) is True


@pytest.mark.asyncio
async def test_load_accounts_shared_without_grant_is_not_found(monkeypatch):
    async def fake_role(db, user_id, org_id):
        return "member"

    monkeypatch.setattr(
        "app.services.integration_account_access_resolver.PermissionChecker.get_user_role",
        fake_role,
    )

    class DB(_GrantDB):
        async def execute(self, stmt):
            return SimpleNamespace(scalar_one_or_none=lambda: None)

    with pytest.raises(RemoteAgentRouteError) as exc:
        await load_accounts_for_run(
            DB([_shared()]),
            org_id="org",
            user_id="user",
            account_ids=["22222222-2222-4222-8222-222222222222"],
        )
    assert exc.value.code == 40404
