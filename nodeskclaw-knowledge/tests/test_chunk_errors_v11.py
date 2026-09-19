"""Chunk Gateway v1.1 error key factories."""

from __future__ import annotations

from app.services import chunk_errors


def test_chunk_not_found_includes_error_code():
    err = chunk_errors.chunk_not_found()
    assert err.status_code == 404
    assert err.message_key == "errors.knowledge.chunk_not_found"
    assert err.details == {"error_code": "KNOWLEDGE_CHUNK_NOT_FOUND"}


def test_chunk_image_not_found():
    err = chunk_errors.chunk_image_not_found()
    assert err.status_code == 404
    assert err.message_key == "errors.knowledge.chunk_image_not_found"
    assert err.details == {"error_code": "KNOWLEDGE_CHUNK_IMAGE_NOT_FOUND"}


def test_chunk_image_type_unsupported():
    err = chunk_errors.chunk_image_type_unsupported()
    assert err.status_code == 415
    assert err.message_key == "errors.knowledge.chunk_image_type_unsupported"
    assert err.details == {"error_code": "KNOWLEDGE_CHUNK_IMAGE_TYPE_UNSUPPORTED"}


def test_chunk_image_too_large():
    err = chunk_errors.chunk_image_too_large()
    assert err.status_code == 413
    assert err.message_key == "errors.knowledge.chunk_image_too_large"
    assert err.details == {"error_code": "KNOWLEDGE_CHUNK_IMAGE_TOO_LARGE"}
