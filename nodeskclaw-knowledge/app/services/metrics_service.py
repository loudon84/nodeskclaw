"""Prometheus metrics for Knowledge observability (v1.2)."""

from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

# @lat: [[knowledge#Observability Metrics]]

HTTP_REQUESTS = Counter(
    "knowledge_http_requests_total",
    "Total HTTP requests handled by knowledge API",
    ["method", "path", "status"],
)

RAGFLOW_REQUESTS = Counter(
    "knowledge_ragflow_requests_total",
    "Total RAGFlow adapter requests",
    ["method", "path", "status"],
)
RAGFLOW_DURATION = Histogram(
    "knowledge_ragflow_request_duration_seconds",
    "RAGFlow adapter request duration in seconds",
    ["method", "path"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)

RETRIEVAL_TOTAL = Counter(
    "knowledge_retrieval_total",
    "Total secure retrieval attempts",
    ["status"],
)
RETRIEVAL_DURATION = Histogram(
    "knowledge_retrieval_duration_seconds",
    "Secure retrieval duration in seconds",
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)
RETRIEVAL_DEGRADED = Counter(
    "knowledge_retrieval_degraded_total",
    "Retrievals completed in degraded mode",
)
RETRIEVAL_FAILED = Counter(
    "knowledge_retrieval_failed_total",
    "Retrievals that failed (fail-closed or hard error)",
)

SECURITY_CHUNKS_DROPPED = Counter(
    "knowledge_security_chunks_dropped_total",
    "Chunks dropped by security cleaner",
    ["reason"],
)

INGESTION_JOBS = Counter(
    "knowledge_ingestion_jobs_total",
    "Ingestion jobs completed",
    ["status"],
)
INGESTION_FAILED = Counter(
    "knowledge_ingestion_failed_total",
    "Ingestion jobs that failed",
)
INGESTION_DURATION = Histogram(
    "knowledge_ingestion_duration_seconds",
    "Ingestion job duration in seconds",
    buckets=(1.0, 5.0, 15.0, 30.0, 60.0, 120.0, 300.0, 600.0, 1800.0),
)

LLM_REQUESTS = Counter(
    "knowledge_llm_requests_total",
    "LLM Proxy chat completion requests",
    ["status"],
)
LLM_DURATION = Histogram(
    "knowledge_llm_duration_seconds",
    "LLM Proxy request duration in seconds",
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0),
)
LLM_PROMPT_TOKENS = Counter(
    "knowledge_llm_prompt_tokens_total",
    "LLM prompt tokens consumed",
)
LLM_COMPLETION_TOKENS = Counter(
    "knowledge_llm_completion_tokens_total",
    "LLM completion tokens consumed",
)

CONNECTOR_SYNC_TOTAL = Counter(
    "knowledge_connector_sync_total",
    "Connector sync runs finished",
    ["connector_type", "status"],
)
CONNECTOR_SYNC_DURATION = Histogram(
    "knowledge_connector_sync_duration_seconds",
    "Connector sync duration in seconds",
    ["connector_type"],
    buckets=(1.0, 5.0, 15.0, 30.0, 60.0, 120.0, 300.0, 600.0, 1800.0, 3600.0),
)
CONNECTOR_OBJECTS_DISCOVERED = Counter(
    "knowledge_connector_objects_discovered_total",
    "Objects discovered during connector sync",
    ["connector_type"],
)
CONNECTOR_OBJECTS_CHANGED = Counter(
    "knowledge_connector_objects_changed_total",
    "Objects changed (create/update/archive/restore) during connector sync",
    ["connector_type"],
)
CONNECTOR_FETCH_TOTAL = Counter(
    "knowledge_connector_fetch_total",
    "Connector fetch attempts",
    ["connector_type", "status"],
)
CONNECTOR_FETCH_DURATION = Histogram(
    "knowledge_connector_fetch_duration_seconds",
    "Connector fetch duration in seconds",
    ["connector_type"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 15.0, 30.0, 60.0, 120.0),
)
CONNECTOR_FETCH_FAILED = Counter(
    "knowledge_connector_fetch_failed_total",
    "Connector fetch failures",
    ["connector_type"],
)
CONNECTOR_SYNC_LAG = Histogram(
    "knowledge_connector_sync_lag_seconds",
    "Lag between interval due time and sync start",
    ["connector_type"],
    buckets=(1.0, 5.0, 15.0, 30.0, 60.0, 300.0, 900.0, 3600.0, 21600.0),
)
CONNECTOR_AUTH_ERROR = Counter(
    "knowledge_connector_auth_error_total",
    "Connector authentication errors",
    ["connector_type"],
)

BINDING_DRIFT = Counter(
    "knowledge_binding_drift_total",
    "Runtime Binding drift detections",
    ["reason"],
)
INDEX_DRIFT = Counter(
    "knowledge_index_drift_total",
    "Index State drift detections",
    ["index_type"],
)
BUILD_JOBS = Counter(
    "knowledge_build_jobs_total",
    "Knowledge build jobs by status",
    ["status"],
)
CAPABILITY_PLANS = Counter(
    "knowledge_capability_plans_total",
    "Capability planner invocations",
    ["reason_code"],
)
TRANSLATION_DRIFT = Counter(
    "knowledge_translation_drift_total",
    "Translation artifact drift detections",
    ["reason"],
)
EVIDENCE_RETURNED = Counter(
    "knowledge_evidence_returned_total",
    "Evidence items returned by type",
    ["evidence_type"],
)

RUNTIME_DRIFT = Counter(
    "knowledge_runtime_drift_total",
    "Runtime binding or config drift detections",
    ["reason"],
)
RUNTIME_RECONCILE = Counter(
    "knowledge_runtime_reconcile_total",
    "Runtime reconcile operations",
    ["status"],
)
RUNTIME_MODE_REQUESTS = Counter(
    "knowledge_runtime_mode_requests_total",
    "Retrieval runtime mode invocations",
    ["mode"],
)
RUNTIME_CONTRACT_PROBE = Counter(
    "knowledge_runtime_contract_probe_total",
    "RAGFlow contract probe runs",
    ["level", "status"],
)
BUILD_VALIDATION = Counter(
    "knowledge_build_validation_total",
    "Build artifact validation outcomes",
    ["index_type", "status"],
)
AGGREGATE_SECURITY_FALLBACK = Counter(
    "knowledge_aggregate_security_fallback_total",
    "Aggregate security gate fallbacks",
    ["reason"],
)
APPLICATION_READINESS_FAILURE = Counter(
    "application_readiness_failure_total",
    "Application readiness blocking checks",
    ["reason"],
)

WORKER_HEARTBEAT = Gauge(
    "knowledge_worker_heartbeat_timestamp",
    "Last worker heartbeat unix timestamp",
    ["worker_role"],
)

_WORKER_HEARTBEAT_TS: dict[str, float] = {}

METRICS_CONTENT_TYPE = CONTENT_TYPE_LATEST


def render_metrics() -> bytes:
    return generate_latest()


def normalize_http_path(path: str) -> str:
    if not path:
        return "/"
    if path.startswith("/metrics") or path.startswith("/health"):
        return path.rstrip("/") or path
    parts = path.split("?")[0].strip("/").split("/")
    out: list[str] = []
    for part in parts:
        if not part:
            continue
        if len(part) == 36 and part.count("-") == 4:
            out.append(":id")
        else:
            out.append(part)
    return "/" + "/".join(out) if out else "/"


def observe_http_request(*, method: str, path: str, status: int) -> None:
    HTTP_REQUESTS.labels(method=method.upper(), path=normalize_http_path(path), status=str(status)).inc()


def observe_ragflow_request(*, method: str, path: str, status: str, duration_seconds: float) -> None:
    label_path = path.split("?")[0]
    RAGFLOW_REQUESTS.labels(method=method.upper(), path=label_path, status=status).inc()
    RAGFLOW_DURATION.labels(method=method.upper(), path=label_path).observe(duration_seconds)


def observe_retrieval(*, status: str, duration_seconds: float) -> None:
    RETRIEVAL_TOTAL.labels(status=status).inc()
    RETRIEVAL_DURATION.observe(duration_seconds)
    if status == "degraded":
        RETRIEVAL_DEGRADED.inc()
    elif status in {"failed", "error"}:
        RETRIEVAL_FAILED.inc()


def observe_security_chunk_drop(*, reason: str) -> None:
    SECURITY_CHUNKS_DROPPED.labels(reason=reason or "unknown").inc()


def observe_ingestion_job(*, status: str, duration_seconds: float | None = None) -> None:
    INGESTION_JOBS.labels(status=status).inc()
    if status == "failed":
        INGESTION_FAILED.inc()
    if duration_seconds is not None and duration_seconds >= 0:
        INGESTION_DURATION.observe(duration_seconds)


def observe_llm_request(
    *,
    status: str,
    duration_seconds: float,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
) -> None:
    LLM_REQUESTS.labels(status=status).inc()
    LLM_DURATION.observe(duration_seconds)
    if prompt_tokens > 0:
        LLM_PROMPT_TOKENS.inc(prompt_tokens)
    if completion_tokens > 0:
        LLM_COMPLETION_TOKENS.inc(completion_tokens)


def observe_connector_sync(
    *,
    connector_type: str,
    status: str,
    duration_seconds: float | None = None,
    objects_discovered: int = 0,
    objects_changed: int = 0,
    sync_lag_seconds: float | None = None,
) -> None:
    ctype = connector_type or "unknown"
    CONNECTOR_SYNC_TOTAL.labels(connector_type=ctype, status=status or "unknown").inc()
    if duration_seconds is not None and duration_seconds >= 0:
        CONNECTOR_SYNC_DURATION.labels(connector_type=ctype).observe(duration_seconds)
    if objects_discovered > 0:
        CONNECTOR_OBJECTS_DISCOVERED.labels(connector_type=ctype).inc(objects_discovered)
    if objects_changed > 0:
        CONNECTOR_OBJECTS_CHANGED.labels(connector_type=ctype).inc(objects_changed)
    if sync_lag_seconds is not None and sync_lag_seconds >= 0:
        CONNECTOR_SYNC_LAG.labels(connector_type=ctype).observe(sync_lag_seconds)


def observe_connector_fetch(*, connector_type: str, status: str, duration_seconds: float | None = None) -> None:
    ctype = connector_type or "unknown"
    CONNECTOR_FETCH_TOTAL.labels(connector_type=ctype, status=status or "unknown").inc()
    if status == "failed":
        CONNECTOR_FETCH_FAILED.labels(connector_type=ctype).inc()
    if duration_seconds is not None and duration_seconds >= 0:
        CONNECTOR_FETCH_DURATION.labels(connector_type=ctype).observe(duration_seconds)


def observe_connector_auth_error(*, connector_type: str) -> None:
    CONNECTOR_AUTH_ERROR.labels(connector_type=connector_type or "unknown").inc()


def observe_binding_drift(*, reason: str) -> None:
    BINDING_DRIFT.labels(reason=reason or "unknown").inc()


def observe_index_drift(*, index_type: str) -> None:
    INDEX_DRIFT.labels(index_type=index_type or "unknown").inc()


def observe_build_job(*, status: str) -> None:
    BUILD_JOBS.labels(status=status or "unknown").inc()


def observe_capability_plan(*, reason_code: str) -> None:
    CAPABILITY_PLANS.labels(reason_code=reason_code or "unknown").inc()


def observe_translation_drift(*, reason: str) -> None:
    TRANSLATION_DRIFT.labels(reason=reason or "unknown").inc()


def observe_evidence_returned(*, evidence_type: str) -> None:
    EVIDENCE_RETURNED.labels(evidence_type=evidence_type or "unknown").inc()


def observe_runtime_drift(*, reason: str) -> None:
    RUNTIME_DRIFT.labels(reason=reason or "unknown").inc()


def observe_runtime_reconcile(*, status: str) -> None:
    RUNTIME_RECONCILE.labels(status=status or "unknown").inc()


def observe_runtime_mode_request(*, mode: str) -> None:
    RUNTIME_MODE_REQUESTS.labels(mode=mode or "unknown").inc()


def observe_runtime_contract_probe(*, level: str, status: str) -> None:
    RUNTIME_CONTRACT_PROBE.labels(level=level or "unknown", status=status or "unknown").inc()


def observe_build_validation(*, index_type: str, status: str) -> None:
    BUILD_VALIDATION.labels(index_type=index_type or "unknown", status=status or "unknown").inc()


def observe_aggregate_security_fallback(*, reason: str) -> None:
    AGGREGATE_SECURITY_FALLBACK.labels(reason=reason or "unknown").inc()


def observe_application_readiness_failure(*, reason: str) -> None:
    APPLICATION_READINESS_FAILURE.labels(reason=reason or "unknown").inc()


def observe_worker_heartbeat(*, worker_role: str) -> None:
    import time

    role = worker_role or "unknown"
    now = time.time()
    _WORKER_HEARTBEAT_TS[role] = now
    WORKER_HEARTBEAT.labels(worker_role=role).set(now)


def worker_heartbeat_snapshot() -> dict[str, float | None]:
    roles = ("ingestion", "build", "maintenance", "connector", "translation")
    return {role: _WORKER_HEARTBEAT_TS.get(role) for role in roles}
