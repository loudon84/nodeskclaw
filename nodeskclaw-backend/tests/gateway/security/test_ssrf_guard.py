from app.services.gateway.security.ssrf_guard import SSRFGuard


class TestSSRFGuard:
    def test_private_network_10(self):
        assert SSRFGuard.check_url("http://10.0.0.1/health") is False

    def test_private_network_172(self):
        assert SSRFGuard.check_url("http://172.16.0.1/health") is False

    def test_private_network_192(self):
        assert SSRFGuard.check_url("http://192.168.1.1/health") is False

    def test_localhost(self):
        assert SSRFGuard.check_url("http://localhost/health") is False

    def test_127_0_0_1(self):
        assert SSRFGuard.check_url("http://127.0.0.1/health") is False

    def test_0_0_0_0(self):
        assert SSRFGuard.check_url("http://0.0.0.0/health") is False

    def test_public_url_allowed(self):
        assert SSRFGuard.check_url("https://api.example.com/mcp") is True

    def test_host_whitelist_match(self):
        assert SSRFGuard.check_url("http://internal.corp.com/mcp", ["*.corp.com"]) is True

    def test_host_whitelist_no_match(self):
        assert SSRFGuard.check_url("http://10.0.0.1/mcp", ["*.example.com"]) is False
