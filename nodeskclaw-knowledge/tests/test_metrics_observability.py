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
        "knowledge_connector_sync_total",
        "knowledge_connector_sync_duration_seconds",
        "knowledge_connector_objects_discovered_total",
        "knowledge_connector_objects_changed_total",
        "knowledge_connector_fetch_total",
        "knowledge_connector_fetch_duration_seconds",
        "knowledge_connector_fetch_failed_total",
        "knowledge_connector_sync_lag_seconds",
        "knowledge_connector_auth_error_total",
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
    metrics_service.observe_connector_sync(
        connector_type="filesystem",
        status="completed",
        duration_seconds=1.2,
        objects_discovered=3,
        objects_changed=1,
    )
    metrics_service.observe_connector_fetch(connector_type="s3_compatible", status="failed", duration_seconds=0.3)
    metrics_service.observe_connector_auth_error(connector_type="http_manifest")
    metrics_service.observe_capability_plan(reason_code="rule_default_chunk")
    metrics_service.observe_evidence_returned(evidence_type="chunk")
    metrics_service.observe_build_job(status="completed")
    metrics_service.observe_binding_drift(reason="version_mismatch")
    metrics_service.observe_index_drift(index_type="graph")
    payload = metrics_service.render_metrics().decode("utf-8")
    assert "knowledge_retrieval_degraded_total" in payload
    assert "knowledge_capability_plans_total" in payload
    assert "knowledge_evidence_returned_total" in payload
    assert "knowledge_build_jobs_total" in payload
    assert 'reason="unauthorized"' in payload
    assert "knowledge_llm_prompt_tokens_total" in payload
    assert 'connector_type="filesystem"' in payload
    assert "connector_id=" not in payload
    assert "external_object_id" not in payload
    assert "source_uri" not in payload


def test_normalize_http_path_redacts_uuid():
    path = metrics_service.normalize_http_path("/api/v1/citations/550e8400-e29b-41d4-a716-446655440000")
    assert path == "/api/v1/citations/:id"
