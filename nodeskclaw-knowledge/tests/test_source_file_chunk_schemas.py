"""Unit tests for SourceFile Chunk public DTOs."""

from __future__ import annotations

from app.schemas.knowledge import (
    SourceFileChunkAvailabilityPatch,
    SourceFileChunkAvailabilityResult,
    SourceFileChunkOut,
    SourceFileChunkPageOut,
)


def test_chunk_out_excludes_provider_runtime_ids():
    chunk = SourceFileChunkOut(
        id="c1",
        content="hello",
        available=True,
        important_keywords=["a"],
        questions=[],
    )
    payload = chunk.model_dump()
    assert set(payload) == {
        "id",
        "content",
        "available",
        "has_image",
        "positions",
        "important_keywords",
        "questions",
    }
    assert payload["has_image"] is False
    assert "dataset_id" not in payload
    assert "document_id" not in payload
    assert "available_int" not in payload
    assert "ragflow_document_id" not in payload
    assert "image_id" not in payload
    assert "img_id" not in payload


def test_chunk_out_has_image_default_false():
    chunk = SourceFileChunkOut(id="c1", content="")
    assert chunk.has_image is False
    assert chunk.model_dump()["has_image"] is False


def test_chunk_out_available_may_be_null():
    chunk = SourceFileChunkOut(id="c1", content="")
    assert chunk.available is None
    assert chunk.model_dump()["available"] is None


def test_chunk_page_out_shape():
    page = SourceFileChunkPageOut(
        source_file_id="sf1",
        file_version_id="v1",
        items=[SourceFileChunkOut(id="c1", content="x", available=False)],
        total=137,
        page=1,
        page_size=10,
    )
    dumped = page.model_dump()
    assert dumped["total"] == 137
    assert len(dumped["items"]) == 1
    assert "dataset_id" not in dumped


def test_availability_patch_and_result():
    patch = SourceFileChunkAvailabilityPatch(file_version_id="v1", available=False)
    assert patch.available is False
    result = SourceFileChunkAvailabilityResult(
        source_file_id="sf1",
        file_version_id="v1",
        chunk_id="c1",
        available=False,
    )
    assert result.chunk_id == "c1"
