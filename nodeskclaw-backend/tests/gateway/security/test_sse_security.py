from app.services.gateway.security.sse_security import SSESecurity


class TestSSESecurity:
    def test_strict_no_origin_rejects(self):
        assert SSESecurity.check_origin(None, ["https://app.example.com"], "strict") is False

    def test_strict_valid_origin(self):
        assert SSESecurity.check_origin("https://app.example.com", ["https://app.example.com"], "strict") is True

    def test_strict_invalid_origin(self):
        assert SSESecurity.check_origin("https://evil.com", ["https://app.example.com"], "strict") is False

    def test_relaxed_no_origin_allows(self):
        assert SSESecurity.check_origin(None, ["https://app.example.com"], "relaxed") is True

    def test_connection_limit_global(self):
        allowed, reason = SSESecurity.check_connection_limit(500, 10, max_global=500)
        assert allowed is False
        assert reason == "global"

    def test_connection_limit_instance(self):
        allowed, reason = SSESecurity.check_connection_limit(10, 100, max_global=500, max_per_instance=100)
        assert allowed is False
        assert reason == "instance"

    def test_connection_limit_ok(self):
        allowed, reason = SSESecurity.check_connection_limit(10, 5, max_global=500, max_per_instance=100)
        assert allowed is True
        assert reason is None
