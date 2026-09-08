from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services.execution_observability import (
    ALLOWED_TRACE_ATTRS,
    METRIC_DEFINITIONS,
    ExecutionTrace,
    apply_runtime_binding,
    bind_from_snapshot,
    fail_open,
    get_current_trace,
    get_registry,
    normalize_request_trace_id,
    observe_stage,
    record_metric,
    trace_log_extra,
    update_trace_attrs,
)


@pytest.fixture(autouse=True)
def reset_registry():
    get_registry().reset()
    yield
    get_registry().reset()


def test_bind_from_snapshot_correlates_allowlisted_keys():
    snapshot = {
        "run_session_id": "sess-1",
        "skill_release_id": "rel-1",
        "request_trace_id": "req_trace-01",
        "placement": {"edge_node_id": "node-1"},
    }
    trace = bind_from_snapshot(
        snapshot,
        run_id="run-1",
        attempt_id="att-1",
        generation=2,
    )
    assert trace is not None
    assert trace.attrs["run_id"] == "run-1"
    assert trace.attrs["attempt_id"] == "att-1"
    assert trace.attrs["session_id"] == "sess-1"
    assert trace.attrs["skill_release_id"] == "rel-1"
    assert trace.attrs["request_trace_id"] == "req_trace-01"
    assert trace.attrs["generation"] == "2"
    assert trace.attrs["edge_node_id"] == "node-1"
    assert get_current_trace() is trace


def test_bind_from_snapshot_rejects_invalid_trace_id():
    snapshot = {"request_trace_id": "bad trace with spaces"}
    trace = bind_from_snapshot(snapshot, run_id="run-1")
    assert trace is not None
    assert "request_trace_id" not in trace.attrs


def test_normalize_request_trace_id_limits_and_charset():
    assert normalize_request_trace_id("req_ok-1.2:3") == "req_ok-1.2:3"
    assert normalize_request_trace_id("x" * 65) is None
    assert normalize_request_trace_id("has space") is None
    assert normalize_request_trace_id(None) is None


@pytest.mark.parametrize("name", list(METRIC_DEFINITIONS.keys()))
def test_metrics_definitions_documented(name):
    definition = METRIC_DEFINITIONS[name]
    assert definition["type"] in {"counter", "histogram"}
    assert definition["unit"]
    assert definition["labels"]


def test_metrics_registry_records_counter_and_histogram():
    record_metric("runs_claimed_total", labels={"role": "central", "outcome": "ok"})
    record_metric("run_execute_seconds", labels={"engine": "hermes", "outcome": "ok"}, observe_seconds=1.25)
    snapshot = get_registry().snapshot()
    counter_names = {item["name"] for item in snapshot["counters"]}
    histogram_names = {item["name"] for item in snapshot["histograms"]}
    assert "runs_claimed_total" in counter_names
    assert "run_execute_seconds" in histogram_names


def test_metrics_rejects_uuid_labels():
    record_metric(
        "runs_claimed_total",
        labels={"role": "550e8400-e29b-41d4-a716-446655440000", "outcome": "ok"},
    )
    snapshot = get_registry().snapshot()
    assert len(snapshot["counters"]) == 1
    assert "role" not in snapshot["counters"][0]["labels"]
    assert snapshot["counters"][0]["labels"]["outcome"] == "ok"


def test_metrics_rejects_forbidden_label_keys():
    record_metric(
        "runs_claimed_total",
        labels={"run_id": "run-1", "outcome": "ok"},
    )
    snapshot = get_registry().snapshot()
    assert len(snapshot["counters"]) == 1
    assert "run_id" not in snapshot["counters"][0]["labels"]
    assert snapshot["counters"][0]["labels"]["outcome"] == "ok"


def test_sensitive_attrs_excluded_from_trace():
    snapshot = {
        "request_trace_id": "req_1",
        "runtime_policy": {"api_key": "secret-value"},
        "client_context": {"prompt": "do something sensitive"},
    }
    trace = bind_from_snapshot(snapshot, run_id="run-1")
    assert trace is not None
    assert "prompt" not in trace.attrs
    assert "api_key" not in trace.attrs
    observe_stage("execute", outcome="ok", error_code="errors.test", token="hidden")
    assert "token" not in (get_current_trace() or ExecutionTrace()).attrs


def test_observe_stage_drops_raw_exception_text():
    observe_stage("execute", outcome="error", error_code="errors.test", message="Traceback (most recent call last)")
    trace = get_current_trace()
    assert trace is not None
    assert "Traceback" not in str(trace.attrs)


def test_fail_open_wrapper_does_not_raise():
    @fail_open
    def boom() -> None:
        raise RuntimeError("observe failed")

    assert boom() is None
    snapshot = get_registry().snapshot()
    assert any(item["name"] == "observe_errors_total" for item in snapshot["counters"])


def test_bind_failure_is_fail_open(monkeypatch):
    monkeypatch.setattr(
        "app.services.execution_observability._sanitize_attr_value",
        MagicMock(side_effect=RuntimeError("bind broke")),
    )
    assert bind_from_snapshot({"request_trace_id": "req_1"}, run_id="run-1") is None
    snapshot = get_registry().snapshot()
    assert any(
        item["name"] == "observe_errors_total" and item["labels"].get("stage") == "bind"
        for item in snapshot["counters"]
    )


def test_record_metric_registry_failure_is_fail_open(monkeypatch):
    registry = get_registry()

    def broken_increment(*args, **kwargs):
        raise RuntimeError("metrics broke")

    monkeypatch.setattr(registry, "increment", broken_increment)
    record_metric("runs_claimed_total", labels={"role": "central", "outcome": "ok"})


def test_bind_from_snapshot_includes_runtime_binding_fields():
    snapshot = {"run_session_id": "sess-1", "request_trace_id": "req_rt-1"}
    binding = {
        "runtime_type": "hermes",
        "runtime_version": "v2026.8.31",
        "runtime_run_id": "rr-1",
        "runtime_session_id": "rs-1",
        "runtime_idempotency_key": "rik-1",
    }
    trace = bind_from_snapshot(snapshot, run_id="run-1", attempt_id="att-1", runtime_binding=binding)
    assert trace is not None
    assert trace.attrs["runtime_type"] == "hermes"
    assert trace.attrs["runtime_version"] == "v2026.8.31"
    assert trace.attrs["runtime_run_id"] == "rr-1"
    assert trace.attrs["runtime_session_id"] == "rs-1"
    assert trace.attrs["runtime_idempotency_key"] == "rik-1"


def test_apply_runtime_binding_and_trace_log_extra():
    bind_from_snapshot({"request_trace_id": "req_1"}, run_id="run-1")
    apply_runtime_binding({"runtime_type": "hermes", "runtime_run_id": "rr-2"})
    update_trace_attrs(tool_call_id="tool-1", correlation_confidence="high")
    extra = trace_log_extra()
    assert extra["run_id"] == "run-1"
    assert extra["runtime_type"] == "hermes"
    assert extra["runtime_run_id"] == "rr-2"
    assert extra["tool_call_id"] == "tool-1"
    assert extra["correlation_confidence"] == "high"
    assert "delegation_topology" not in ALLOWED_TRACE_ATTRS
    observe_stage("execute", outcome="ok", delegation_topology="should-drop")
    assert "delegation_topology" not in (get_current_trace() or ExecutionTrace()).attrs


def test_runtime_ids_rejected_as_metric_labels():
    record_metric(
        "runs_claimed_total",
        labels={"role": "central", "outcome": "ok", "runtime_run_id": "rr-uuid"},
    )
    snapshot = get_registry().snapshot()
    assert len(snapshot["counters"]) == 1
    assert "runtime_run_id" not in snapshot["counters"][0]["labels"]
    assert snapshot["counters"][0]["labels"]["role"] == "central"
