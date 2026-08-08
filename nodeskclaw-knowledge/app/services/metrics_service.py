"""Prometheus metrics for Knowledge observability (v1.2)."""

from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

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
