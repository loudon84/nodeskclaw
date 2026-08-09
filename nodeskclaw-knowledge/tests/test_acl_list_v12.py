"""ACL set list filtering and pagination total (PRD §71)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.principal import KnowledgePrincipal
from app.services import knowledge_set_service


def _member(**kwargs) -> KnowledgePrincipal:
    base = dict(
        user_id="u1",
        member_id="m1",
        org_id="o1",
        name="Zhang",
        department="sales",
        member_role="member",
        is_active=True,
        is_super_admin=False,
    )
    base.update(kwargs)
    return KnowledgePrincipal(**base)


def _set(id_: str, name: str, created_at: str = "2024-01-01"):
    return SimpleNamespace(
        id=id_,
        name=name,
        org_id="o1",
        created_at=created_at,
        updated_at=created_at,
        deleted_at=None,
    )


@pytest.mark.asyncio
async def test_list_sets_excludes_without_read_or_use():
    visible = _set("set_ok", "Visible")
    hidden = _set("set_deny", "Hidden")
    db = MagicMock()

    class Scalars:
        def all(self):
            return [visible, hidden]

    class Result:
        def scalars(self):
            return Scalars()

    db.execute = AsyncMock(return_value=Result())

    class Snapshot:
        def has_set_permission(self, set_id, permission):
            if set_id == "set_ok" and permission in ("read", "use"):
                return True
            return False

    with patch(
        "app.services.permission_snapshot_service.load_permission_snapshot",
        new=AsyncMock(return_value=Snapshot()),
    ):
        items, total = await knowledge_set_service.list_knowledge_sets(db, _member())

    assert [row.id for row in items] == ["set_ok"]
    assert total == 1


@pytest.mark.asyncio
async def test_list_sets_pagination_total_after_acl_filter():
    rows = [
        _set("s1", "A", "2024-01-03"),
        _set("s2", "B", "2024-01-02"),
        _set("s3", "C", "2024-01-01"),
        _set("s4", "D", "2023-12-01"),
        _set("s5", "E", "2023-11-01"),
    ]
    db = MagicMock()

    class Scalars:
        def all(self):
            return rows

    class Result:
        def scalars(self):
            return Scalars()

    db.execute = AsyncMock(return_value=Result())
    allowed = {"s1", "s2", "s3"}

    class Snapshot:
        def has_set_permission(self, set_id, permission):
            return set_id in allowed and permission in ("read", "use")

    with patch(
        "app.services.permission_snapshot_service.load_permission_snapshot",
        new=AsyncMock(return_value=Snapshot()),
    ):
        page1, total = await knowledge_set_service.list_knowledge_sets(
            db, _member(), page=1, page_size=2
        )
        page2, total2 = await knowledge_set_service.list_knowledge_sets(
            db, _member(), page=2, page_size=2
        )

    assert total == 3
    assert total2 == 3
    assert [row.id for row in page1] == ["s1", "s2"]
    assert [row.id for row in page2] == ["s3"]
    assert "s4" not in {row.id for row in page1 + page2}
    assert "s5" not in {row.id for row in page1 + page2}
