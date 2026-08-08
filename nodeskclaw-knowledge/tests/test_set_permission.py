"""KnowledgeSet bind permission tests."""

from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import ForbiddenError
from app.schemas.principal import KnowledgePrincipal
from app.services import knowledge_set_service


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
async def test_bind_without_manage_forbidden():
    db = AsyncMock()
    member = _member()

    with patch(
        "app.services.knowledge_set_service.get_knowledge_set",
        new=AsyncMock(return_value=object()),
    ):
        with patch(
            "app.services.knowledge_set_service.has_set_permission",
            new=AsyncMock(return_value=False),
        ):
            with pytest.raises(ForbiddenError):
                await knowledge_set_service.bind_knowledge_base(
                    db,
                    member,
                    "set1",
                    "kb1",
                )
