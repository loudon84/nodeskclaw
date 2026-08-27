"""Translation / artifact / metrics tests."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import artifact_store, metrics_service, translation_service
from app.services.translation_engine import (
    TranslationEngineError,
    TranslationPageRequest,
    TranslationPageResult,
    get_translation_engine,
)


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


def test_translation_engine_registry_default():
    engine = get_translation_engine("docutranslate")
    assert engine is not None


def test_translation_engine_unknown_raises():
    with pytest.raises(TranslationEngineError):
        get_translation_engine("not-a-real-engine")


@pytest.mark.asyncio
async def test_process_translation_job_success(tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.artifact_store.settings.ARTIFACT_LOCAL_ROOT", str(tmp_path))

    page = SimpleNamespace(
        id="p1",
        document_id="d1",
        page_no=1,
        current_revision=0,
        status="pending",
        artifact_uri=None,
        last_error=None,
    )
    doc = SimpleNamespace(id="d1", deleted_at=None, source_file_id="sf1", file_version_id="fv1", target_lang="en")
    job = SimpleNamespace(
        page_id="p1",
        document_id="d1",
        status="running",
        error_message=None,
        finished_at=None,
    )

    db = AsyncMock()
    db.get = AsyncMock(side_effect=lambda _model, oid: {"p1": page, "d1": doc}.get(oid))
    db.add = MagicMock()
    db.flush = AsyncMock()

    class _StubEngine:
        async def translate_page(self, request: TranslationPageRequest) -> TranslationPageResult:
            assert request.page_no == 1
            return TranslationPageResult(content="translated text", meta={"engine": "stub"})

        async def translate_document(self, request: TranslationPageRequest) -> TranslationPageResult:
            return await self.translate_page(request)

        async def get_progress(self, document_id: str):
            return SimpleNamespace(status="completed", progress=100, message=None)

        async def cancel(self, document_id: str) -> None:
            return None

        async def aclose(self) -> None:
            return None

    with (
        patch("app.services.translation_service.get_translation_engine", return_value=_StubEngine()),
        patch.object(translation_service, "list_pages", AsyncMock(return_value=[page])),
    ):
        await translation_service.process_translation_job(db, job)

    assert job.status == "completed"
    assert page.status == "completed"
    assert page.current_revision == 1
    assert page.artifact_uri.startswith("local://")
    db.add.assert_called()


@pytest.mark.asyncio
async def test_process_translation_job_engine_failure_is_honest():
    page = SimpleNamespace(
        id="p1",
        document_id="d1",
        page_no=1,
        current_revision=0,
        status="pending",
        last_error=None,
    )
    doc = SimpleNamespace(id="d1", deleted_at=None, source_file_id="sf1", file_version_id="fv1", target_lang="en")
    job = SimpleNamespace(
        page_id="p1",
        document_id="d1",
        status="running",
        error_message=None,
        finished_at=None,
    )
    db = AsyncMock()
    db.get = AsyncMock(side_effect=lambda _model, oid: {"p1": page, "d1": doc}.get(oid))
    db.flush = AsyncMock()

    class _FailingEngine:
        async def translate_page(self, request: TranslationPageRequest) -> TranslationPageResult:
            raise TranslationEngineError("translation_unavailable")

        async def translate_document(self, request: TranslationPageRequest) -> TranslationPageResult:
            raise TranslationEngineError("translation_unavailable")

        async def get_progress(self, document_id: str):
            return SimpleNamespace(status="failed", progress=0, message="down")

        async def cancel(self, document_id: str) -> None:
            return None

        async def aclose(self) -> None:
            return None

    with patch("app.services.translation_service.get_translation_engine", return_value=_FailingEngine()):
        await translation_service.process_translation_job(db, job)

    assert job.status == "failed"
    assert "translation_unavailable" in job.error_message
    assert page.status == "failed"
    assert page.current_revision == 0

