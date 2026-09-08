from unittest.mock import AsyncMock, patch

import pytest

from app.services.context_revalidate import (
    ContextRevalidationError,
    revalidate_execution_context,
)


@pytest.mark.asyncio
async def test_revalidate_rejects_missing_execution_context_when_context_version_exists():
    with pytest.raises(ContextRevalidationError, match="execution context missing"):
        await revalidate_execution_context(
            snapshot={"context_version": 1},
            run_id="run-1",
            attempt_id="attempt-1",
            generation=1,
            org_id="org-1",
            user_id="user-1",
        )


@pytest.mark.asyncio
async def test_revalidate_rejects_missing_execution_context_and_context_version():
    with pytest.raises(ContextRevalidationError, match="execution context missing"):
        await revalidate_execution_context(
            snapshot={},
            run_id="run-1",
            attempt_id="attempt-1",
            generation=1,
            org_id="org-1",
            user_id="user-1",
        )


@pytest.mark.asyncio
async def test_revalidate_rejects_missing_context_version_when_context_exists():
    with pytest.raises(ContextRevalidationError, match="context version missing"):
        await revalidate_execution_context(
            snapshot={"execution_context": {"descriptors": []}},
            run_id="run-1",
            attempt_id="attempt-1",
            generation=1,
            org_id="org-1",
            user_id="user-1",
        )


@pytest.mark.asyncio
async def test_revalidate_checks_session_before_backend_context_gate():
    session_db = AsyncMock()
    with patch(
        "app.services.context_revalidate.run_service.revalidate_run_session",
        new=AsyncMock(side_effect=ValueError("expired")),
    ), pytest.raises(ContextRevalidationError, match="run session revalidation denied"):
        await revalidate_execution_context(
            snapshot={
                "run_session_id": "sess-1",
                "context_version": 3,
                "execution_context": {"context_version": 3, "descriptors": []},
            },
            run_id="run-1",
            attempt_id="attempt-1",
            generation=1,
            org_id="org-1",
            user_id="user-1",
            session_db=session_db,
        )
