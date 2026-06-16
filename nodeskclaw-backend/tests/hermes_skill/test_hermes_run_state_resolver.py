import pytest

from app.services.hermes_skill.hermes_run_state_resolver import (
    HermesRunStateResolver,
    RunStateTracker,
)
from app.models.hermes_skill.hermes_task import EventType, TaskStatus


def test_convert_hermes_failed_event():
    converted = HermesRunStateResolver.convert_hermes_event({
        "event_type": "hermes.run.failed",
        "event_seq": 5,
        "payload": {"error_message": "boom"},
    })
    assert converted is not None
    assert converted["event_type"] == EventType.HERMES_RUN_FAILED
    assert converted["source_event_seq"] == 5


def test_convert_completed_with_failed_status_maps_task_failed():
    converted = HermesRunStateResolver.convert_hermes_event({
        "event_type": "hermes.run.completed",
        "event_seq": 6,
        "payload": {"status": "failed"},
    })
    assert converted["event_type"] == EventType.TASK_FAILED


def test_tracker_seen_failed_wins_over_completed():
    tracker = RunStateTracker()
    tracker.observe_event_type(EventType.HERMES_RUN_COMPLETED, {"status": "completed"})
    tracker.observe_event_type(EventType.HERMES_RUN_FAILED, {"error_message": "err"})
    assert tracker.resolve_after_stream(stream_interrupted=False) == TaskStatus.FAILED


def test_tracker_unknown_run_status_keeps_running():
    tracker = RunStateTracker()
    assert tracker.map_hermes_run_status("unknown") == TaskStatus.RUNNING
    assert tracker.resolve_after_stream(stream_interrupted=True, run_status="unknown") == TaskStatus.RUNNING


def test_tracker_completed_on_normal_stream():
    tracker = RunStateTracker()
    tracker.observe_event_type(EventType.HERMES_RUN_COMPLETED, {"status": "completed"})
    assert tracker.resolve_after_stream(stream_interrupted=False) == TaskStatus.COMPLETED
