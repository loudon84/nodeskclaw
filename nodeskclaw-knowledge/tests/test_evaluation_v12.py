"""Evaluation metrics and unauthorized FAIL unit tests."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.enums import EvaluationRunStatus
from app.services import evaluation_service
from app.services.evaluation_runner import (
    has_unauthorized_source,
    hit_at_k,
    mean_reciprocal_rank,
    process_evaluation_run,
    recall_at_k,
)


def test_hit_at_k_present():
    assert hit_at_k(["a", "b", "c"], ["b"], 8) == 1.0


def test_hit_at_k_absent():
    assert hit_at_k(["a", "c"], ["b"], 8) == 0.0


def test_recall_at_k_partial():
    assert recall_at_k(["a", "b"], ["a", "b", "c"], 8) == pytest.approx(2 / 3)


def test_mrr_first_rank():
    assert mean_reciprocal_rank(["b", "a"], ["a"]) == pytest.approx(0.5)


def test_unauthorized_source_fails_check():
    assert has_unauthorized_source(["sf_ok", "sf_bad"], {"sf_ok"}) is True
    assert has_unauthorized_source(["sf_ok"], {"sf_ok"}) is False


@pytest.mark.asyncio
async def test_process_run_fails_on_unauthorized_source():
    db = MagicMock()
    db.add = MagicMock()
    db.get = AsyncMock(
        side_effect=[
            SimpleNamespace(id="es1", org_id="o1", knowledge_set_id="set1", deleted_at=None),
            SimpleNamespace(id="p1", deleted_at=None, config={"top_n": 8}),
        ]
    )
    cases = [
        SimpleNamespace(
            id="c1",
            query="q",
            expected_source_file_ids=["sf_expected"],
            created_at=None,
        )
    ]

    class Scalars:
        def all(self):
            return cases

    class Result:
        def scalars(self):
            return Scalars()

    db.execute = AsyncMock(return_value=Result())

    run = SimpleNamespace(
        id="run1",
        evaluation_set_id="es1",
        retrieval_profile_id="p1",
        created_by_member_id="m1",
        attempt_count=0,
        max_attempts=5,
        status=EvaluationRunStatus.running.value,
        metrics=None,
        last_error=None,
        finished_at=None,
        lease_owner="w1",
        lease_until=None,
        next_run_at=None,
    )
    ragflow = AsyncMock()

    async def fake_retrieve(*_args, **_kwargs):
        return {
            "chunks": [{"source_file_id": "sf_unauthorized", "chunk_id": "x"}],
            "status": "success",
            "latency_ms": 12,
        }

    with (
        patch(
            "app.services.evaluation_runner.knowledge_set_service.list_bound_knowledge_bases",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "app.services.evaluation_runner.build_access_plan",
            new=AsyncMock(return_value=SimpleNamespace(source_file_ids=["sf_expected"])),
        ),
        patch("app.services.evaluation_runner.retrieval_service.retrieve", new=fake_retrieve),
    ):
        await process_evaluation_run(db, ragflow, run)

    assert run.status == EvaluationRunStatus.failed.value
    assert run.last_error == "errors.knowledge.evaluation_failed"
    assert run.finished_at is not None


@pytest.mark.asyncio
async def test_compare_profiles_delta_from_completed_runs():
    db = MagicMock()
    member = SimpleNamespace(member_id="m1", org_id="o1")
    run_a = SimpleNamespace(
        id="run_a",
        evaluation_set_id="es1",
        retrieval_profile_id="pa",
        status=EvaluationRunStatus.completed.value,
        metrics={
            "hit_at_k": 0.5,
            "mrr": 0.4,
            "avg_latency_ms": 100.0,
            "empty_rate": 0.2,
            "degraded_rate": 0.1,
        },
    )
    run_b = SimpleNamespace(
        id="run_b",
        evaluation_set_id="es1",
        retrieval_profile_id="pb",
        status=EvaluationRunStatus.completed.value,
        metrics={
            "hit_at_k": 0.8,
            "mrr": 0.6,
            "avg_latency_ms": 80.0,
            "empty_rate": 0.1,
            "degraded_rate": 0.0,
        },
    )

    with (
        patch(
            "app.services.evaluation_service._require_eval_set_manage",
            new=AsyncMock(),
        ),
        patch(
            "app.services.evaluation_service.get_run",
            new=AsyncMock(side_effect=[run_a, run_b]),
        ),
    ):
        result = await evaluation_service.compare_profiles(
            db,
            member,
            evaluation_set_id="es1",
            run_a_id="run_a",
            run_b_id="run_b",
        )

    assert result["profile_a"]["metrics"]["hit_at_8"] == 0.5
    assert result["profile_b"]["metrics"]["hit_at_8"] == 0.8
    assert result["delta"]["hit_at_8"] == pytest.approx(0.3)
    assert result["delta"]["mrr"] == pytest.approx(0.2)
    assert result["delta"]["avg_latency_ms"] == pytest.approx(-20.0)
    assert result["delta"]["empty_rate"] == pytest.approx(-0.1)
    assert result["delta"]["degraded_rate"] == pytest.approx(-0.1)
