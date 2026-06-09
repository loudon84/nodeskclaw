import pytest
import httpx

from app.services.registry_service import (
    _parse_registry,
    normalize_image_registry,
    list_image_tags,
)


@pytest.mark.parametrize(
    "raw, normalized, api_base, repo",
    [
        (
            "192.168.102.247:9900/hermes-webui-expert",
            "192.168.102.247:9900/hermes-webui-expert",
            "http://192.168.102.247:9900",
            "hermes-webui-expert",
        ),
        (
            "http://192.168.102.247:9900/hermes-webui-expert",
            "192.168.102.247:9900/hermes-webui-expert",
            "http://192.168.102.247:9900",
            "hermes-webui-expert",
        ),
        (
            "https://192.168.102.247:9900/hermes-webui-expert",
            "192.168.102.247:9900/hermes-webui-expert",
            "https://192.168.102.247:9900",
            "hermes-webui-expert",
        ),
        (
            "nodesk-center-cn-beijing.cr.volces.com/public/deskclaw-openclaw",
            "nodesk-center-cn-beijing.cr.volces.com/public/deskclaw-openclaw",
            "https://nodesk-center-cn-beijing.cr.volces.com",
            "public/deskclaw-openclaw",
        ),
        (
            "https://cr.example.com/ns/repo",
            "cr.example.com/ns/repo",
            "https://cr.example.com",
            "ns/repo",
        ),
        (
            "http://10.0.0.5:5000/my-app",
            "10.0.0.5:5000/my-app",
            "http://10.0.0.5:5000",
            "my-app",
        ),
    ],
)
def test_parse_registry(raw, normalized, api_base, repo):
    got_norm, got_api, got_repo = _parse_registry(raw)
    assert got_norm == normalized
    assert got_api == api_base
    assert got_repo == repo


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("http://192.168.102.247:9900/hermes-webui-expert", "192.168.102.247:9900/hermes-webui-expert"),
        ("https://cr.example.com/ns/repo/", "cr.example.com/ns/repo"),
        ("192.168.1.1:5000/app", "192.168.1.1:5000/app"),
    ],
)
def test_normalize_image_registry(raw, expected):
    assert normalize_image_registry(raw) == expected


@pytest.mark.asyncio
async def test_list_image_tags_uses_http_for_private_registry(monkeypatch):
    captured: dict[str, str] = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"tags": ["v2026.3.13", "latest"]}

        def raise_for_status(self):
            return None

        @property
        def headers(self):
            return {}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, **kwargs):
            captured["url"] = url
            return FakeResponse()

    async def fake_auth(_db):
        return None

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: FakeClient())
    monkeypatch.setattr(
        "app.services.registry_service._get_registry_auth",
        fake_auth,
    )

    tags = await list_image_tags(
        db=None,
        registry_url="192.168.102.247:9900/hermes-webui-expert",
    )

    assert captured["url"] == (
        "http://192.168.102.247:9900/v2/hermes-webui-expert/tags/list"
    )
    assert [t["tag"] for t in tags] == ["latest", "v2026.3.13"]
