import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from app.services.hermes_external.hermes_gateway_probe_service import HermesGatewayProbeService


@pytest.mark.asyncio
async def test_probe_url_online_on_health_path():
    response = MagicMock()
    response.status_code = 200

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url):
            if url.endswith("/health"):
                return response
            raise httpx.ConnectError("fail")

    with patch("app.services.hermes_external.hermes_gateway_probe_service.httpx.AsyncClient", return_value=FakeClient()):
        result = await HermesGatewayProbeService().probe_url("http://127.0.0.1:18900")
    assert result.gateway_status == "online"
    assert result.probe_path == "/health"


@pytest.mark.asyncio
async def test_probe_url_unauthorized():
    response = MagicMock()
    response.status_code = 401

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url):
            return response

    with patch("app.services.hermes_external.hermes_gateway_probe_service.httpx.AsyncClient", return_value=FakeClient()):
        result = await HermesGatewayProbeService().probe_url("http://127.0.0.1:18900")
    assert result.gateway_status == "unauthorized"


@pytest.mark.asyncio
async def test_probe_url_unconfigured_when_missing():
    result = await HermesGatewayProbeService().probe_url(None)
    assert result.gateway_status == "unconfigured"
