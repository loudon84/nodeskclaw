from unittest.mock import AsyncMock, patch

import pytest

from app.services.remote_acp.errors import EXPERT_NOT_FOUND
from app.services.remote_acp.run_context import build_run_context


@pytest.mark.asyncio
async def test_run_context_does_not_write_hermes_task():
    db = AsyncMock()
    catalog = AsyncMock()
    catalog.get_by_slug = AsyncMock(return_value=None)
    with patch("app.services.remote_acp.run_context.ExpertCatalogService", return_value=catalog):
        try:
            await build_run_context(
                db,
                org_id="org",
                user_id="user",
                agent_ref="missing",
                session_id="sess",
            )
            assert False
        except Exception as exc:
            assert exc is EXPERT_NOT_FOUND
    db.add.assert_not_called()
    db.commit.assert_not_called()
