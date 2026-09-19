"""RagflowClient chunk page + available PATCH tests."""

from __future__ import annotations

import json

import httpx
import pytest

from app.integrations.ragflow.client import RagflowClient, RagflowChunkPage
from app.integrations.ragflow.exceptions import RagflowError


@pytest.mark.asyncio
async def test_list_document_chunks_page_preserves_total():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/chunks")
        assert request.url.params.get("page") == "1"
        assert request.url.params.get("page_size") == "10"
        assert request.url.params.get("keywords") == "LiteLLM"
        return httpx.Response(
            200,
            json={
                "code": 0,
                "data": {
                    "chunks": [{"id": "c1", "content": "a", "available": True}],
                    "total": 137,
                    "page": 1,
                    "page_size": 10,
                },
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://ragflow.example.com") as http:
        client = RagflowClient(base_url="http://ragflow.example.com", api_key="k", http_client=http)
        page = await client.list_document_chunks_page(
            "ds",
            "doc",
            page=1,
            page_size=10,
            keywords="LiteLLM",
        )

    assert isinstance(page, RagflowChunkPage)
    assert page.total == 137
    assert len(page.chunks) == 1
    assert page.chunks[0]["id"] == "c1"


@pytest.mark.asyncio
async def test_list_document_chunks_page_missing_total_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"code": 0, "data": {"chunks": [{"id": "c1"}]}},
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://ragflow.example.com") as http:
        client = RagflowClient(base_url="http://ragflow.example.com", api_key="k", http_client=http)
        with pytest.raises(RagflowError) as ei:
            await client.list_document_chunks_page("ds", "doc")
    assert ei.value.message_key == "errors.knowledge.chunk_contract_invalid"


@pytest.mark.asyncio
async def test_list_document_chunks_compat_still_returns_list():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"code": 0, "data": {"chunks": [{"id": "c1"}], "total": 1}},
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://ragflow.example.com") as http:
        client = RagflowClient(base_url="http://ragflow.example.com", api_key="k", http_client=http)
        items = await client.list_document_chunks("ds", "doc")
    assert isinstance(items, list)
    assert items[0]["id"] == "c1"


@pytest.mark.asyncio
async def test_set_document_chunk_available_uses_patch_and_exact_body():
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(200, json={"code": 0, "data": True})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://ragflow.example.com") as http:
        client = RagflowClient(base_url="http://ragflow.example.com", api_key="k", http_client=http)
        await client.set_document_chunk_available("ds", "doc", "c1", False)

    assert seen["method"] == "PATCH"
    assert seen["path"] == "/api/v1/datasets/ds/documents/doc/chunks/c1"
    assert seen["body"] == {"available": False}


@pytest.mark.asyncio
async def test_list_document_chunks_page_passes_id_and_echoes_request_page():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params.get("id") == "chunk-42"
        assert request.url.params.get("page") == "2"
        assert request.url.params.get("page_size") == "10"
        return httpx.Response(
            200,
            json={
                "code": 0,
                "data": {
                    "chunks": [{"id": "chunk-42", "content": "x"}],
                    "total": 1,
                    "page": 99,
                    "page_size": 999,
                },
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://ragflow.example.com") as http:
        client = RagflowClient(base_url="http://ragflow.example.com", api_key="k", http_client=http)
        page = await client.list_document_chunks_page(
            "ds",
            "doc",
            page=2,
            page_size=10,
            id="chunk-42",
        )

    assert page.page == 2
    assert page.page_size == 10
    assert page.total == 1


@pytest.mark.asyncio
async def test_get_document_image_success():
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/documents/images/img-1"
        assert request.method == "GET"
        return httpx.Response(
            200,
            content=png,
            headers={"Content-Type": "image/png", "Content-Length": str(len(png))},
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://ragflow.example.com") as http:
        client = RagflowClient(base_url="http://ragflow.example.com", api_key="k", http_client=http)
        image = await client.get_document_image("img-1")

    assert image.content == png
    assert image.content_type == "image/png"


@pytest.mark.asyncio
async def test_get_document_image_rejects_oversize_content_length():
    from app.core.exceptions import AppException

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"x",
            headers={"Content-Type": "image/png", "Content-Length": str(20971521)},
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://ragflow.example.com") as http:
        client = RagflowClient(base_url="http://ragflow.example.com", api_key="k", http_client=http)
        with pytest.raises(AppException) as ei:
            await client.get_document_image("img-1")
    assert ei.value.status_code == 413
    assert ei.value.message_key == "errors.knowledge.chunk_image_too_large"


@pytest.mark.asyncio
async def test_get_document_image_rejects_svg():
    from app.core.exceptions import AppException

    def handler(request: httpx.Request) -> httpx.Response:
        body = b"<svg xmlns='http://www.w3.org/2000/svg'></svg>"
        return httpx.Response(
            200,
            content=body,
            headers={"Content-Type": "image/svg+xml", "Content-Length": str(len(body))},
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://ragflow.example.com") as http:
        client = RagflowClient(base_url="http://ragflow.example.com", api_key="k", http_client=http)
        with pytest.raises(AppException) as ei:
            await client.get_document_image("img-1")
    assert ei.value.status_code == 415


@pytest.mark.asyncio
async def test_get_document_image_rejects_redirect():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"Location": "http://evil.example.com/x"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://ragflow.example.com") as http:
        client = RagflowClient(base_url="http://ragflow.example.com", api_key="k", http_client=http)
        with pytest.raises(RagflowError) as ei:
            await client.get_document_image("img-1")
    assert ei.value.message_key == "errors.knowledge.chunk_provider_unavailable"


@pytest.mark.asyncio
async def test_get_document_image_stream_abort_without_content_length():
    from app.core.exceptions import AppException

    oversized = b"x" * (20 * 1024 * 1024 + 1)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=oversized,
            headers={"Content-Type": "image/png"},
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://ragflow.example.com") as http:
        client = RagflowClient(base_url="http://ragflow.example.com", api_key="k", http_client=http)
        with pytest.raises(AppException) as ei:
            await client.get_document_image("img-1")
    assert ei.value.status_code == 413
