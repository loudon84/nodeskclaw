import pytest

from app.core.config import settings


@pytest.mark.asyncio
async def test_system_info_includes_genehub_descriptor(client):
    resp = await client.get("/api/v1/system/info")
    assert resp.status_code == 200
    body = resp.json()
    assert "genehub" in body
    assert "mcp" in body

    genehub = body["genehub"]
    assert genehub["enabled"] is True
    assert genehub["name"] == settings.GENEHUB_REGISTRY_NAME
    assert genehub["apiPrefix"] == "/api/v1/desktop"
    assert genehub["healthEndpoint"] == "/api/v1/desktop/genehub/health"
    assert genehub["requiresAuth"] is True
    assert genehub["minServerVersion"] == settings.APP_VERSION


@pytest.mark.asyncio
async def test_system_info_genehub_disabled(client, monkeypatch):
    monkeypatch.setattr("app.services.genehub_service.settings.GENEHUB_DESKTOP_SYNC_ENABLED", False)
    resp = await client.get("/api/v1/system/info")
    assert resp.status_code == 200
    assert resp.json()["genehub"]["enabled"] is False
