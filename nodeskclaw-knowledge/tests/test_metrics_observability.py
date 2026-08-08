"""Basic observability metrics import, registry, and /metrics endpoint tests."""

from fastapi.testclient import TestClient

from app.main import app
from app.services import metrics_service


def test_metrics_registry_exports_core_names():
    payload = metrics_service.render_metrics().decode("utf-8")
    for name in (
        "knowledge_http_requests_total",
        "knowledge_ragflow_requests_total",
        "knowledge_ragflow_request_duration_seconds",
        "knowledge_retrieval_total",
        "knowledge_retrieval_duration_seconds",
        "knowledge_retrieval_degraded_total",
        "knowledge_retrieval_failed_total",
        "knowledge_security_chunks_dropped_total",
        "knowledge_ingestion_jobs_total",
        "knowledge_ingestion_failed_total",
        "knowledge_ingestion_duration_seconds",
        "knowledge_llm_requests_total",
        "knowledge_llm_duration_seconds",
        "knowledge_llm_prompt_tokens_total",
        "knowledge_llm_completion_tokens_total",
    ):
        assert f"# HELP {name}" in payload or f"# TYPE {name}" in payload or name in payload


def test_metrics_endpoint_text_plain_prometheus():
    with TestClient(app) as client:
        resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "text/plain" in resp.headers.get("content-type", "")
    body = resp.text
    assert "# HELP" in body or "# TYPE" in body or body.lstrip().startswith("#")
    assert "knowledge_http_requests_total" in body
    assert resp.headers.get("X-Request-Id") or resp.headers.get("x-request-id")


def test_observe_helpers_increment():
    metrics_service.observe_http_request(method="GET", path="/api/v1/knowledge-sets/abc", status=200)
    metrics_service.observe_ragflow_request(method="POST", path="/api/v1/retrieval", status="ok", duration_seconds=0.1)
    metrics_service.observe_retrieval(status="degraded", duration_seconds=0.2)
    metrics_service.observe_security_chunk_drop(reason="unauthorized")
    metrics_service.observe_ingestion_job(status="failed", duration_seconds=1.5)
    metrics_service.observe_llm_request(
        status="ok",
        duration_seconds=0.5,
        prompt_tokens=10,
        completion_tokens=3,
    )
    payload = metrics_service.render_metrics().decode("utf-8")
    assert "knowledge_retrieval_degraded_total" in payload
    assert 'reason="unauthorized"' in payload
    assert "knowledge_llm_prompt_tokens_total" in payload


def test_normalize_http_path_redacts_uuid():
    path = metrics_service.normalize_http_path("/api/v1/citations/550e8400-e29b-41d4-a716-446655440000")
    assert path == "/api/v1/citations/:id"
