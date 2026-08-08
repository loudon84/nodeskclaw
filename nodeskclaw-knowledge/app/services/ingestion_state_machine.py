"""Ingestion job state transitions for worker and tests."""

from __future__ import annotations

from app.models.enums import IngestionJobStatus, ParseStatus
from app.models.ingestion_job import IngestionJob
from app.models.source_file import SourceFile
from app.models.source_file_version import SourceFileVersion


RAGFLOW_RUN_ACTIVE = "DONE"
RAGFLOW_RUN_FAIL = "FAIL"
RAGFLOW_RUN_CANCEL = "CANCEL"
RAGFLOW_RUN_RUNNING = "RUNNING"
RAGFLOW_RUN_UNSTART = "UNSTART"


def map_ragflow_run_to_job_status(run: str) -> str:
    mapping = {
        RAGFLOW_RUN_UNSTART: IngestionJobStatus.parse_dispatched.value,
        RAGFLOW_RUN_RUNNING: IngestionJobStatus.parsing.value,
        RAGFLOW_RUN_ACTIVE: IngestionJobStatus.validating.value,
        RAGFLOW_RUN_FAIL: IngestionJobStatus.failed.value,
        RAGFLOW_RUN_CANCEL: IngestionJobStatus.cancelled.value,
    }
    return mapping.get(run, IngestionJobStatus.parsing.value)


def map_ragflow_run_to_parse_status(run: str) -> str:
    if run == RAGFLOW_RUN_ACTIVE:
        return ParseStatus.active.value
    if run == RAGFLOW_RUN_FAIL:
        return ParseStatus.failed.value
    if run in {RAGFLOW_RUN_RUNNING, RAGFLOW_RUN_UNSTART}:
        return ParseStatus.parsing.value
    return ParseStatus.parsing.value


def should_activate_on_run(run: str) -> bool:
    return run == RAGFLOW_RUN_ACTIVE


def apply_parse_dispatched(
    job: IngestionJob,
    version: SourceFileVersion,
    *,
    ragflow_run: str = RAGFLOW_RUN_UNSTART,
) -> None:
    job.status = IngestionJobStatus.parse_dispatched.value
    job.progress = 70
    version.parse_status = ParseStatus.parsing.value
    version.ragflow_status = ragflow_run
    version.ragflow_run = ragflow_run


def apply_run_transition(
    job: IngestionJob,
    version: SourceFileVersion,
    source_file: SourceFile,
    run: str,
    *,
    old_active_version: SourceFileVersion | None = None,
    chunk_count: int | None = None,
) -> bool:
    version.ragflow_run = run
    version.ragflow_status = run
    job.status = map_ragflow_run_to_job_status(run)

    if run == RAGFLOW_RUN_RUNNING:
        job.progress = 80
        version.parse_status = ParseStatus.parsing.value
        return False

    if run == RAGFLOW_RUN_UNSTART:
        job.progress = 70
        version.parse_status = ParseStatus.parsing.value
        return False

    if run == RAGFLOW_RUN_FAIL:
        job.progress = 100
        version.parse_status = ParseStatus.failed.value
        return False

    if run == RAGFLOW_RUN_CANCEL:
        job.progress = 100
        version.parse_status = ParseStatus.failed.value
        return False

    if run == RAGFLOW_RUN_ACTIVE:
        if chunk_count is not None:
            version.chunk_count = chunk_count
        if chunk_count is not None and chunk_count <= 0:
            job.status = IngestionJobStatus.failed.value
            job.progress = 100
            version.parse_status = ParseStatus.failed.value
            return False
        job.status = IngestionJobStatus.validating.value
        job.progress = 90
        version.parse_status = ParseStatus.parsing.value
        activate_version_after_done(source_file, version, old_active_version)
        job.status = IngestionJobStatus.active.value
        job.progress = 100
        return True

    return False


def activate_version_after_done(
    source_file: SourceFile,
    new_version: SourceFileVersion,
    old_version: SourceFileVersion | None,
) -> None:
    from app.services.source_file_service import activate_version

    activate_version(source_file, new_version, old_version)
