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
