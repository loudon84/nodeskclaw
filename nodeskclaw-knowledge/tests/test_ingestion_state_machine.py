"""Ingestion state machine unit tests."""

from types import SimpleNamespace

from app.models.enums import IngestionJobStatus, ParseStatus
from app.services.ingestion_state_machine import (
    apply_parse_dispatched,
    apply_run_transition,
    map_ragflow_run_to_job_status,
)


def _job():
    return SimpleNamespace(
        status=IngestionJobStatus.metadata_synced.value,
        progress=60,
    )


def _version():
    return SimpleNamespace(
        parse_status=ParseStatus.pending.value,
        ragflow_status="UNSTART",
        ragflow_run="UNSTART",
        chunk_count=None,
        id="v2",
    )


def _source_file(active_version_id="v1"):
    return SimpleNamespace(
        active_version_id=active_version_id,
        status="updating",
        id="sf1",
    )


def test_parse_dispatched_not_active():
    job = _job()
    version = _version()
    apply_parse_dispatched(job, version)
    assert job.status == IngestionJobStatus.parse_dispatched.value
    assert version.parse_status == ParseStatus.parsing.value
    sf = _source_file("v1")
    assert sf.active_version_id == "v1"


def test_done_activates_version():
    job = _job()
    version = _version()
    sf = _source_file("v1")
    old = SimpleNamespace(id="v1", parse_status="active", superseded_at=None, activated_at=None)
    activated = apply_run_transition(job, version, sf, "DONE", old_active_version=old, chunk_count=3)
    assert activated is True
    assert job.status == IngestionJobStatus.active.value
    assert sf.active_version_id == "v2"
    assert version.parse_status == ParseStatus.active.value
    assert old.parse_status == ParseStatus.superseded.value


def test_fail_does_not_switch_active():
    job = _job()
    version = _version()
    sf = _source_file("v1")
    old = SimpleNamespace(id="v1", parse_status="active", superseded_at=None, activated_at=None)
    activated = apply_run_transition(job, version, sf, "FAIL", old_active_version=old)
    assert activated is False
    assert sf.active_version_id == "v1"
    assert version.parse_status == ParseStatus.failed.value
    assert old.parse_status == "active"


def test_map_ragflow_run_to_job_status():
    assert map_ragflow_run_to_job_status("UNSTART") == IngestionJobStatus.parse_dispatched.value
    assert map_ragflow_run_to_job_status("RUNNING") == IngestionJobStatus.parsing.value
    assert map_ragflow_run_to_job_status("DONE") == IngestionJobStatus.validating.value
