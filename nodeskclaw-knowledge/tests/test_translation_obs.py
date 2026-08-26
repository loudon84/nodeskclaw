"""Translation / artifact / metrics tests."""

from pathlib import Path

from app.services import artifact_store, metrics_service


def test_artifact_store_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.artifact_store.settings.ARTIFACT_LOCAL_ROOT", str(tmp_path))
    uri = artifact_store.write_bytes("demo/a.txt", b"hello")
    assert uri.startswith("local://")
    assert artifact_store.read_bytes(uri) == b"hello"
    signed = artifact_store.signed_url(uri, ttl_seconds=60)
    assert "sig=" in signed
    assert "expires=" in signed


def test_signed_url_verify(tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.artifact_store.settings.ARTIFACT_LOCAL_ROOT", str(tmp_path))
    uri = artifact_store.write_bytes("demo/b.txt", b"x")
    signed = artifact_store.signed_url(uri, ttl_seconds=60)
    # parse query
    from urllib.parse import parse_qs, urlparse

    qs = parse_qs(urlparse(signed).query)
    assert artifact_store.verify_signed_url(
        uri=qs["uri"][0], expires=int(qs["expires"][0]), sig=qs["sig"][0]
    )


def test_new_metrics_labels_are_low_cardinality():
    metrics_service.observe_binding_drift(reason="dataset_missing")
    metrics_service.observe_index_drift(index_type="graph")
    metrics_service.observe_translation_drift(reason="artifact_missing")
    metrics_service.observe_evidence_returned(evidence_type="chunk")
    body = metrics_service.render_metrics().decode("utf-8")
    assert "knowledge_binding_drift_total" in body
    assert "knowledge_index_drift_total" in body
    assert "knowledge_translation_drift_total" in body
