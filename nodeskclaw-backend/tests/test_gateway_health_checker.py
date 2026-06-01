import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

import pytest

from app.services.gateway.health_checker import GatewayHealthChecker
from app.services.gateway.types import UpstreamHealthState


class TestGatewayHealthChecker:
    def test_is_available_default_true(self):
        checker = GatewayHealthChecker(MagicMock())
        assert checker.is_available("unknown-server") is True

    def test_state_after_failures(self):
        checker = GatewayHealthChecker(MagicMock())
        checker._states["s1"] = UpstreamHealthState(
            mcp_server_id="s1",
            is_available=True,
            consecutive_failures=3,
        )
        assert checker.is_available("s1") is True
        checker._states["s1"].is_available = False
        assert checker.is_available("s1") is False

    def test_get_all_states(self):
        checker = GatewayHealthChecker(MagicMock())
        checker._states["s1"] = UpstreamHealthState(mcp_server_id="s1", is_available=True)
        checker._states["s2"] = UpstreamHealthState(mcp_server_id="s2", is_available=False)
        states = checker.get_all_states()
        assert len(states) == 2
        assert states["s1"].is_available is True
        assert states["s2"].is_available is False

    @pytest.mark.asyncio
    async def test_probe_no_url_returns_true(self):
        checker = GatewayHealthChecker(MagicMock())
        server = MagicMock()
        server.url = None
        result = await checker._probe(server, 5)
        assert result is True
