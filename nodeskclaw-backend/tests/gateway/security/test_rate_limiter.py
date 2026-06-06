from app.services.gateway.security.rate_limiter import RateLimiter


class TestRateLimiter:
    def test_global_allows_within_limit(self):
        limiter = RateLimiter()
        assert limiter.check_global(5) is True
        assert limiter.check_global(5) is True

    def test_global_blocks_over_limit(self):
        limiter = RateLimiter()
        for _ in range(3):
            limiter.check_global(3)
        assert limiter.check_global(3) is False

    def test_global_no_limit_when_none(self):
        limiter = RateLimiter()
        assert limiter.check_global(None) is True
        assert limiter.check_global(0) is True

    def test_per_key_allows(self):
        limiter = RateLimiter()
        assert limiter.check_per_key("key1", 5) is True

    def test_per_key_blocks_over_limit(self):
        limiter = RateLimiter()
        for _ in range(3):
            limiter.check_per_key("key1", 3)
        assert limiter.check_per_key("key1", 3) is False

    def test_per_key_independent_keys(self):
        limiter = RateLimiter()
        limiter.check_per_key("key1", 1)
        assert limiter.check_per_key("key2", 1) is True
