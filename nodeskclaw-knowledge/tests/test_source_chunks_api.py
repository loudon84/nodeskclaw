"""SourceFile Chunk HTTP API tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api import source_files as source_files_api
from app.core.deps import get_db, get_member_context, get_runtime_adapter
from app.core.exceptions import ConflictError, ForbiddenError
from app.main import app
from app.schemas.knowledge import (
    SourceFileChunkAvailabilityResult,
    SourceFileChunkOut,
    SourceFileChunkPageOut,
)
from app.schemas.principal import KnowledgePrincipal


def _member() -> KnowledgePrincipal:
    return KnowledgePrincipal(
        user_id="u1",
        member_id="m1",
        org_id="o1",
        member_role="member",
        is_super_admin=False,
    )


@pytest.fixture
def client():
    async def _member_dep():
        return _member()

    async def _db_dep():
        return AsyncMock()

    async def _ragflow_dep():
        return AsyncMock()

    app.dependency_overrides[get_member_context] = _member_dep
    app.dependency_overrides[get_db] = _db_dep
    app.dependency_overrides[get_runtime_adapter] = _ragflow_dep
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_chunk_routes_registered():
    paths = {getattr(r, "path", "") for r in source_files_api.router.routes}
    assert "/source-files/{source_file_id}/chunks" in paths
    assert "/source-files/{source_file_id}/chunks/{chunk_id}" in paths
    assert "/source-files/{source_file_id}/chunks/{chunk_id}/image" in paths


def test_list_chunks_default_and_hides_provider_ids(client: TestClient):
    page = SourceFileChunkPageOut(
        source_file_id="sf1",
        file_version_id="v1",
        items=[SourceFileChunkOut(id="c1", content="hello", available=True, has_image=False)],
        total=1,
        page=1,
        page_size=50,
    )
    with patch(
        "app.api.source_files.source_chunk_service.list_source_file_chunks",
        new=AsyncMock(return_value=page),
    ) as mocked:
        resp = client.get("/api/v1/source-files/sf1/chunks")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["total"] == 1
    assert data["file_version_id"] == "v1"
    assert data["items"][0]["has_image"] is False
    assert "dataset_id" not in data
    assert "document_id" not in data
    assert "available_int" not in data["items"][0]
    assert "image_id" not in data["items"][0]
    mocked.assert_awaited_once()
    kwargs = mocked.await_args.kwargs
    assert kwargs["page"] == 1
    assert kwargs["page_size"] == 50


def test_list_chunks_page_size_over_max_422(client: TestClient):
    resp = client.get("/api/v1/source-files/sf1/chunks", params={"page_size": 101})
    assert resp.status_code == 422


def test_patch_chunk_forbidden(client: TestClient):
    with patch(
        "app.api.source_files.source_chunk_service.set_source_file_chunk_available",
        new=AsyncMock(side_effect=ForbiddenError()),
    ):
        resp = client.patch(
            "/api/v1/source-files/sf1/chunks/c1",
            json={"file_version_id": "v1", "available": False},
        )
    assert resp.status_code == 403


def test_patch_chunk_version_conflict(client: TestClient):
    with patch(
        "app.api.source_files.source_chunk_service.set_source_file_chunk_available",
        new=AsyncMock(
            side_effect=ConflictError(
                message="stale",
                message_key="errors.knowledge.chunk_version_conflict",
            )
        ),
    ):
        resp = client.patch(
            "/api/v1/source-files/sf1/chunks/c1",
            json={"file_version_id": "v0", "available": True},
        )
    assert resp.status_code == 409
    assert resp.json()["message_key"] == "errors.knowledge.chunk_version_conflict"


def test_patch_chunk_success(client: TestClient):
    result = SourceFileChunkAvailabilityResult(
        source_file_id="sf1",
        file_version_id="v1",
        chunk_id="c1",
        available=False,
    )
    with patch(
        "app.api.source_files.source_chunk_service.set_source_file_chunk_available",
        new=AsyncMock(return_value=result),
    ):
        resp = client.patch(
            "/api/v1/source-files/sf1/chunks/c1",
            json={"file_version_id": "v1", "available": False},
        )
    assert resp.status_code == 200
    assert resp.json()["data"]["available"] is False
    assert resp.json()["data"]["chunk_id"] == "c1"


def test_get_chunk_image_success_binary(client: TestClient):
    from app.services.source_chunk_service import SourceFileChunkImage

    image = SourceFileChunkImage(content=b"\x89PNG", content_type="image/png")
    with patch(
        "app.api.source_files.source_chunk_service.get_source_file_chunk_image",
        new=AsyncMock(return_value=image),
    ) as mocked:
        resp = client.get(
            "/api/v1/source-files/sf1/chunks/c1/image",
            params={"file_version_id": "v1"},
        )
    assert resp.status_code == 200
    assert resp.content == b"\x89PNG"
    assert resp.headers["content-type"].startswith("image/png")
    assert resp.headers["cache-control"] == "private, max-age=300"
    assert "content-disposition" not in {k.lower() for k in resp.headers.keys()}
    mocked.assert_awaited_once()
    assert mocked.await_args.kwargs["file_version_id"] == "v1"


def test_get_chunk_image_version_conflict(client: TestClient):
    with patch(
        "app.api.source_files.source_chunk_service.get_source_file_chunk_image",
        new=AsyncMock(
            side_effect=ConflictError(
                message="stale",
                message_key="errors.knowledge.chunk_version_conflict",
            )
        ),
    ):
        resp = client.get(
            "/api/v1/source-files/sf1/chunks/c1/image",
            params={"file_version_id": "v0"},
        )
    assert resp.status_code == 409
    assert resp.json()["message_key"] == "errors.knowledge.chunk_version_conflict"


def test_get_chunk_image_forbidden(client: TestClient):
    with patch(
        "app.api.source_files.source_chunk_service.get_source_file_chunk_image",
        new=AsyncMock(side_effect=ForbiddenError()),
    ):
        resp = client.get(
            "/api/v1/source-files/sf1/chunks/c1/image",
            params={"file_version_id": "v1"},
        )
    assert resp.status_code == 403
