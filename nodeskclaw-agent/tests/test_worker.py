from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.worker import RunWorker, build_hybrid_step_plan, needs_edge_jobs


def test_build_hybrid_step_plan_structure():
    # 1. None snapshot
    plan1 = build_hybrid_step_plan(None)
    assert len(plan1) == 1
    assert plan1[0]["step_id"] == "central"
    assert plan1[0]["required"] is True

    # 2. Hybrid snapshot
    snap_hybrid = {
        "placement": {"role": "hybrid", "engine": "hybrid"},
        "runtime_policy": {
            "connector_bindings": [
                {"id": "b1", "placement": "edge", "node_id": "edge-node-1"},
                {"id": "b2", "placement": "central"},
            ]
        },
    }
    plan2 = build_hybrid_step_plan(snap_hybrid)
    assert len(plan2) == 2
    assert plan2[0]["step_id"] == "central_hermes"
    assert plan2[0]["required"] is True
    assert plan2[0]["dependencies"] == []

    assert plan2[1]["step_id"] == "edge_connector_b1"
    assert plan2[1]["role"] == "edge"
    assert plan2[1]["required"] is True
    assert plan2[1]["dependencies"] == ["central_hermes"]


def test_needs_edge_jobs():
    assert needs_edge_jobs(None) is False
    assert needs_edge_jobs({"runtime_policy": {}}) is False
    assert (
        needs_edge_jobs(
            {
                "runtime_policy": {
                    "connector_bindings": [
                        {"placement": "central"},
                        {"placement": "edge"},
                    ]
                }
            }
        )
        is True
    )


@pytest.mark.asyncio
async def test_worker_execute_hybrid_sets_waiting_edge_and_enqueues_edge_job():
    worker = RunWorker()
    claimed = {
        "id": "run-hybrid-1",
        "org_id": "org-1",
        "tool_name": "test_tool",
        "arguments": {"q": "hello"},
        "snapshot": {
            "org_id": "org-1",
            "placement": {"role": "hybrid", "engine": "hybrid"},
            "runtime_policy": {
                "connector_bindings": [
                    {"id": "edge-bind-1", "placement": "edge", "edge_node_id": "node-1"}
                ]
            },
            "request_trace_id": "trace-xyz",
        },
        "attempt_id": "attempt-1",
        "generation": 1,
    }

    # Mock DB session
    mock_db = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.rollback = AsyncMock()

    # Mock execute_engine to return central run.completed
    async def mock_engine_gen(*args, **kwargs):
        yield {"event_type": "step.init", "payload": {}}
        yield {"event_type": "run.completed", "payload": {"summary": "central done"}}

    # Mock HTTP client for enqueue
    mock_http_resp = MagicMock()
    mock_http_resp.raise_for_status = MagicMock()
    mock_http_resp.json.return_value = {
        "code": 0,
        "data": {"job_id": "edge-job-123", "status": "PENDING", "run_id": "run-hybrid-1"},
    }

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    mock_client.post = AsyncMock(return_value=mock_http_resp)

    set_status_calls = []

    async def mock_set_status(db, run_id, status, **kwargs):
        set_status_calls.append((run_id, status, kwargs))
        return True

    events_appended = []

    async def mock_append_event(db, run_id, event_type, payload, **kwargs):
        events_appended.append((run_id, event_type, payload))
        return MagicMock(event_id="evt-1", event_seq=1)

    with patch("app.services.worker.SessionLocal", return_value=mock_db), \
         patch("app.services.worker.execute_engine", side_effect=mock_engine_gen), \
         patch("app.services.worker.httpx.AsyncClient", return_value=mock_client), \
         patch("app.services.worker.run_service.set_status", side_effect=mock_set_status), \
         patch("app.services.worker.run_service.append_event", side_effect=mock_append_event), \
         patch("app.services.worker.run_service.get_run", return_value=None):

        await worker._execute(claimed)

    # Verify run transitions: RUNNING -> WAITING_EDGE (NOT COMPLETED!)
    statuses = [s[1] for s in set_status_calls]
    assert "RUNNING" in statuses
    assert "WAITING_EDGE" in statuses
    assert "COMPLETED" not in statuses

    # Verify HTTP enqueue called
    assert mock_client.post.call_count == 1
    call_args = mock_client.post.call_args
    assert "/api/v1/internal/edge/jobs/enqueue" in call_args.args[0]
    enqueue_body = call_args.kwargs["json"]
    assert enqueue_body["run_id"] == "run-hybrid-1"
    assert enqueue_body["attempt_id"] == "attempt-1"
    assert enqueue_body["step_id"] == "edge_connector_edge-bind-1"
    assert enqueue_body["idempotency_key"] == "run-hybrid-1:attempt-1:1:edge_connector_edge-bind-1"
    assert enqueue_body["edge_node_id"] == "node-1"

    # Verify events
    event_types = [e[1] for e in events_appended]
    assert "run.started" in event_types
    assert "run.plan" in event_types
    assert "run.central_step_completed" in event_types
    assert "run.waiting_edge" in event_types
    assert "run.edge_steps_queued" in event_types


@pytest.mark.asyncio
async def test_hybrid_waits_for_edge_steps():
    # Alias / regression check for hybrid non-terminal before edge steps
    await test_worker_execute_hybrid_sets_waiting_edge_and_enqueues_edge_job()


@pytest.mark.asyncio
async def test_worker_semantic_events_do_not_aggregate_terminal():
    worker = RunWorker()
    claimed = {
        "id": "run-sem-1",
        "org_id": "org-1",
        "tool_name": "test_tool",
        "arguments": {"q": "hello"},
        "snapshot": {
            "org_id": "org-1",
            "placement": {"role": "central", "engine": "hermes"},
            "request_trace_id": "trace-sem",
        },
        "attempt_id": "attempt-1",
        "generation": 1,
    }

    mock_db = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.rollback = AsyncMock()

    async def mock_engine_gen(*args, **kwargs):
        yield {
            "event_type": "assistant.message",
            "payload": {"text": "hello"},
            "source": "agent",
            "source_event_id": "asst-1",
        }
        yield {
            "event_type": "tool.call",
            "payload": {"tool_name": "search", "call_id": "c1", "status": "started"},
            "source": "agent",
            "source_event_id": "tool-1",
        }
        yield {"event_type": "run.completed", "payload": {"summary": "done"}}

    set_status_calls = []
    events_appended = []
    aggregate_calls = []

    async def mock_set_status(db, run_id, status, **kwargs):
        set_status_calls.append(status)
        return True

    async def mock_append_event(db, run_id, event_type, payload, **kwargs):
        events_appended.append(
            {
                "event_type": event_type,
                "payload": payload,
                "source_event_id": kwargs.get("source_event_id"),
            }
        )
        return MagicMock(event_id="evt", event_seq=len(events_appended))

    async def mock_aggregate(*args, **kwargs):
        aggregate_calls.append(kwargs)

    with patch("app.services.worker.SessionLocal", return_value=mock_db), \
         patch("app.services.worker.execute_engine", side_effect=mock_engine_gen), \
         patch("app.services.worker.run_service.set_status", side_effect=mock_set_status), \
         patch("app.services.worker.run_service.append_event", side_effect=mock_append_event), \
         patch("app.services.worker.run_service.aggregate_run_terminal", side_effect=mock_aggregate), \
         patch("app.services.worker.run_service.update_step_state", new=AsyncMock()), \
         patch("app.services.worker.run_service.persist_step_plan", new=AsyncMock(return_value=[])), \
         patch("app.services.worker.run_service.get_run", return_value=None):
        await worker._execute(claimed)

    event_types = [e["event_type"] for e in events_appended]
    assert "assistant.message" in event_types
    assert "tool.call" in event_types
    assert any(e["source_event_id"] == "asst-1" for e in events_appended)
    assert len(aggregate_calls) == 1
    terminal = next(t for t in event_types if t in ("run.completed", "run.central_step_completed"))
    assert event_types.index("assistant.message") < event_types.index(terminal)

