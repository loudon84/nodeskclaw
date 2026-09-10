"""RAGFlow version transport prefers /v2/system/version."""

from __future__ import annotations

import httpx
import pytest

from app.integrations.ragflow.client import RagflowClient


def _version_payload(version: str) -> dict[str, object]:
    return {"code": 0, "data": {"version": version}}


@pytest.mark.asyncio
async def test_get_system_version_tries_v2_first_and_stops():
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path == "/v2/system/version":
            return httpx.Response(200, json=_version_payload("v0.27.0"))
        return httpx.Response(200, json=_version_payload("v1-should-not-win"))

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://ragflow.example.com") as http:
        client = RagflowClient(base_url="http://ragflow.example.com", api_key="k", http_client=http)
        version = await client.get_system_version()

    assert version == "v0.27.0"
    assert paths == ["/v2/system/version"]


@pytest.mark.asyncio
async def test_get_system_version_falls_back_to_v1_when_v2_fails():
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path == "/v2/system/version":
            return httpx.Response(404, json={"code": 100, "message": "not found"})
        if request.url.path == "/api/v1/system/version":
            return httpx.Response(200, json=_version_payload("v0.21.0"))
        return httpx.Response(500, json={})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://ragflow.example.com") as http:
        client = RagflowClient(base_url="http://ragflow.example.com", api_key="k", http_client=http)
        version = await client.get_system_version()

    assert version == "v0.21.0"
    assert paths[0] == "/v2/system/version"
    assert "/api/v1/system/version" in paths
    assert "/v1/system/version" not in paths


@pytest.mark.asyncio
async def test_get_system_version_returns_none_when_all_paths_fail():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"code": 100})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://ragflow.example.com") as http:
        client = RagflowClient(base_url="http://ragflow.example.com", api_key="k", http_client=http)
        version = await client.get_system_version()

    assert version is None


@pytest.mark.asyncio
async def test_get_system_version_does_not_infer_capability_from_payload():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"code": 0, "data": {"version": "v0.27.0", "graph": False, "raptor": False}},
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://ragflow.example.com") as http:
        client = RagflowClient(base_url="http://ragflow.example.com", api_key="k", http_client=http)
        version = await client.get_system_version()

    assert version == "v0.27.0"
    assert not hasattr(version, "graph")
