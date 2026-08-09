"""Dashboard weekly_query_count origin filtering (PRD §71)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.enums import RetrievalOrigin
from app.schemas.principal import KnowledgePrincipal
from app.services import dashboard_service


def _member() -> KnowledgePrincipal:
    return KnowledgePrincipal(
        user_id="u1",
        member_id="m1",
        org_id="o1",
        name="Zhang",
        department="sales",
        member_role="member",
        is_active=True,
        is_super_admin=False,
    )


@pytest.mark.asyncio
async def test_weekly_query_count_excludes_evaluation_origin():
    db = MagicMock()
    empty = MagicMock()
    empty.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=empty)
    captured = {}

    async def fake_scalar(stmt):
        captured["stmt"] = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        return 7

    db.scalar = AsyncMock(side_effect=fake_scalar)

    class Snapshot:
        def has_kb_permission(self, *_a, **_k):
            return False

        def has_set_permission(self, *_a, **_k):
            return False

        def has_file_permission(self, *_a, **_k):
            return False

    with patch(
        "app.services.dashboard_service.load_permission_snapshot",
        new=AsyncMock(return_value=Snapshot()),
    ):
        result = await dashboard_service.get_dashboard(db, _member())

    assert result["stats"]["weekly_query_count"] == 7
    sql = captured["stmt"].lower()
    assert RetrievalOrigin.direct_retrieval.value in sql
    assert RetrievalOrigin.chat.value in sql
    assert RetrievalOrigin.agent.value in sql
    assert RetrievalOrigin.evaluation.value not in sql
