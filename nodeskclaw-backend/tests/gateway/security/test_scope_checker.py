from app.services.gateway.security.scope_checker import ScopeChecker


class TestScopeChecker:
    def test_no_scope_skipped(self):
        result = ScopeChecker.check_scope(None, "tools/list")
        assert result.is_allowed is True
        assert result.check_status == "skipped"

    def test_sufficient_scope(self):
        result = ScopeChecker.check_scope(["mcp:tools:read", "mcp:tools:execute"], "tools/call")
        assert result.is_allowed is True

    def test_insufficient_scope(self):
        result = ScopeChecker.check_scope(["mcp:tools:read"], "tools/call")
        assert result.is_allowed is False
        assert result.required_scope == "mcp:tools:execute"

    def test_unknown_method_allowed(self):
        result = ScopeChecker.check_scope(["mcp:tools:read"], "custom/method")
        assert result.is_allowed is True
        assert result.check_status == "no_mapping"
