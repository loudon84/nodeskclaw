"""Attempt Runtime Binding persist fencing (unit, mocked DB)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas import RunView
from app.services import run_service


def _binding_row(
    *,
    generation: int = 1,
    runtime_run_id: str | None = None,
    runtime_idempotency_key: str | None = None,
    runtime_bound_at: datetime | None = None,
) -> dict:
    return {
        "generation": generation,
        "runtime_type": "hermes" if runtime_run_id else None,
        "runtime_version": "v2026.8.31" if runtime_run_id else None,
        "runtime_run_id": runtime_run_id,
        "runtime_session_id": None,
        "runtime_profile": None,
        "runtime_capability_snapshot": {"features": ["run_submission"]} if runtime_run_id else None,
        "runtime_idempotency_key": runtime_idempotency_key,
        "runtime_bound_at": runtime_bound_at,
        "runtime_terminal_at": None,
    }


def _db(select_rows: list[dict | None], *, update_rowcount: int = 1) -> AsyncMock:
    db = AsyncMock()
    select_iter = iter(select_rows)

    async def execute(stmt, params=None):
        sql = str(stmt)
        mock_res = MagicMock()
        if "UPDATE" in sql.upper():
            mock_res.rowcount = update_rowcount
            return mock_res
        row = next(select_iter)
        mock_res.mappings.return_value.first.return_value = row
        return mock_res

    db.execute = execute
    return db


def test_run_view_omits_runtime_run_id():
    assert "runtime_run_id" not in RunView.model_fields
    omitted = run_service._omit_runtime_binding_keys(
        {"text": "ok", "runtime_run_id": "rr-secret", "step": "1"}
    )
    assert omitted == {"text": "ok", "step": "1"}


@pytest.mark.asyncio
async def test_persist_runtime_binding_first_bind():
    unbound = _binding_row()
    bound = _binding_row(
        runtime_run_id="rr-1",
        runtime_idempotency_key="run-1:att-1:1",
        runtime_bound_at=datetime.now(timezone.utc),
    )
    db = _db([unbound, bound])
    result = await run_service.persist_runtime_binding(
        db,
        attempt_id="att-1",
        generation=1,
        runtime_run_id="rr-1",
        runtime_version="v2026.8.31",
        runtime_capability_snapshot={"features": ["run_submission"]},
        runtime_idempotency_key="run-1:att-1:1",
    )
    assert result is not None
    assert result["runtime_run_id"] == "rr-1"
    assert result["generation"] == 1
    assert result["runtime_idempotency_key"] == "run-1:att-1:1"


@pytest.mark.asyncio
async def test_persist_runtime_binding_retry_same_runtime_run_id():
    bound = _binding_row(
        runtime_run_id="rr-1",
        runtime_idempotency_key="run-1:att-1:1",
        runtime_bound_at=datetime.now(timezone.utc),
    )
    db = _db([bound, bound])
    first = await run_service.persist_runtime_binding(
        db,
        attempt_id="att-1",
        generation=1,
        runtime_run_id="rr-1",
        runtime_idempotency_key="run-1:att-1:1",
    )
    assert first is not None
    assert first["runtime_run_id"] == "rr-1"

    db2 = _db([bound, bound])
    second = await run_service.persist_runtime_binding(
        db2,
        attempt_id="att-1",
        generation=1,
        runtime_run_id="rr-1",
        runtime_idempotency_key="run-1:att-1:1",
    )
    assert second is not None
    assert second["runtime_run_id"] == "rr-1"


@pytest.mark.asyncio
async def test_persist_runtime_binding_rejects_stale_generation():
    current = _binding_row(generation=2, runtime_run_id="rr-new")
    db = _db([current])
    result = await run_service.persist_runtime_binding(
        db,
        attempt_id="att-1",
        generation=1,
        runtime_run_id="rr-stale",
        runtime_idempotency_key="run-1:att-1:1",
    )
    assert result is None


@pytest.mark.asyncio
async def test_persist_runtime_binding_keeps_existing_runtime_run_id():
    bound = _binding_row(
        runtime_run_id="rr-1",
        runtime_idempotency_key="run-1:att-1:1",
        runtime_bound_at=datetime.now(timezone.utc),
    )
    db = _db([bound])
    result = await run_service.persist_runtime_binding(
        db,
        attempt_id="att-1",
        generation=1,
        runtime_run_id="rr-other",
        runtime_idempotency_key="run-1:att-1:1",
    )
    assert result is not None
    assert result["runtime_run_id"] == "rr-1"


@pytest.mark.asyncio
async def test_get_runtime_binding_missing_attempt():
    db = _db([None])
    assert await run_service.get_runtime_binding(db, "missing") is None


@pytest.mark.asyncio
async def test_mark_runtime_terminal_generation_fenced():
    db = _db([], update_rowcount=1)
    assert await run_service.mark_runtime_terminal(db, attempt_id="att-1", generation=1) is True
    db0 = _db([], update_rowcount=0)
    assert await run_service.mark_runtime_terminal(db0, attempt_id="att-1", generation=1) is False
