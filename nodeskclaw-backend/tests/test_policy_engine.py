import time
import unittest.mock
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.gateway.policy_engine import PolicyEngine
from app.services.gateway.types import PolicyDenyReason


class TestPolicyEngine:
    def test_rate_limit_allows_within_limit(self):
        engine = PolicyEngine()
        key = "org1:inst1:_all"
        assert engine._check_rate_limit(key, 5) is True
        assert engine._check_rate_limit(key, 5) is True

    def test_rate_limit_blocks_over_limit(self):
        engine = PolicyEngine()
        key = "org1:inst1:_all"
        for _ in range(3):
            engine._check_rate_limit(key, 3)
        assert engine._check_rate_limit(key, 3) is False

    def test_rate_limit_window_expiry(self):
        engine = PolicyEngine()
        key = "org1:inst1:_all"
        for _ in range(3):
            engine._check_rate_limit(key, 3)
        old_entries = engine._rate_limit_counters[key]
        while old_entries:
            old_entries.popleft()
        old_entries.append(time.time())
        assert engine._check_rate_limit(key, 3) is True

    @pytest.mark.asyncio
    async def test_sensitive_tool_denied(self):
        engine = PolicyEngine()
        policy = MagicMock()
        policy.id = "p1"
        policy.sensitive_tools = ["file_write"]
        policy.rate_limit_rpm = None
        policy.timeout_seconds = 30
        policy.retry_count = 0
        policy.max_connections = None

        db = AsyncMock()
        with unittest.mock.patch.object(
            engine, "_find_policy", new_callable=AsyncMock, return_value=policy
        ):
            result = await engine.evaluate(db, "org1", "inst1", "file_write", "user1")
            assert result.is_allowed is False
            assert result.deny_reason == PolicyDenyReason.SENSITIVE_TOOL_DENIED

    @pytest.mark.asyncio
    async def test_default_policy_when_no_match(self):
        engine = PolicyEngine()
        db = AsyncMock()
        with unittest.mock.patch.object(
            engine, "_find_policy", new_callable=AsyncMock, return_value=None
        ):
            result = await engine.evaluate(db, "org1", "inst1", None, "user1")
            assert result.is_allowed is True
            assert result.is_default_policy is True
            assert result.timeout_seconds == 30
