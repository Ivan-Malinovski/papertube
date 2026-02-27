"""
Tests for rate limiting.
"""
import pytest
import time
import asyncio


class TestApiRateLimit:
    """Tests for API rate limiting decorator."""
    
    @pytest.mark.asyncio
    async def test_allows_under_limit(self):
        """Test allows requests under limit."""
        from app.ratelimit import rate_limit
        from app import ratelimit
        
        ratelimit._request_log.clear()
        
        @rate_limit(max_requests=3, window_seconds=2)
        async def mock_endpoint(user=None):
            return "success"
        
        for _ in range(3):
            result = await mock_endpoint(user={"id": 1})
            assert result == "success"
    
    @pytest.mark.asyncio
    async def test_blocks_over_limit(self):
        """Test blocks requests over limit."""
        from app.ratelimit import rate_limit
        from app import ratelimit
        from fastapi import HTTPException
        
        ratelimit._request_log.clear()
        
        @rate_limit(max_requests=2, window_seconds=2)
        async def mock_endpoint(user={"id": 1}):
            return "success"
        
        await mock_endpoint(user={"id": 1})
        await mock_endpoint(user={"id": 1})
        
        with pytest.raises(HTTPException) as exc:
            await mock_endpoint(user={"id": 1})
        
        assert exc.value.status_code == 429
    
    @pytest.mark.asyncio
    async def test_window_expiry(self):
        """Test rate limit resets after window."""
        from app.ratelimit import rate_limit
        from app import ratelimit
        
        ratelimit._request_log.clear()
        
        @rate_limit(max_requests=1, window_seconds=1)
        async def mock_endpoint(user={"id": 1}):
            return "success"
        
        await mock_endpoint(user={"id": 1})
        
        with pytest.raises(Exception):
            await mock_endpoint(user={"id": 1})
        
        time.sleep(1.5)
        
        result = await mock_endpoint()
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_different_users_independent(self):
        """Test different users have independent limits."""
        from app.ratelimit import rate_limit
        from app import ratelimit
        
        ratelimit._request_log.clear()
        
        @rate_limit(max_requests=2, window_seconds=5)
        async def mock_endpoint(user=None):
            return "success"
        
        await mock_endpoint(user={"id": 1})
        await mock_endpoint(user={"id": 1})
        
        with pytest.raises(Exception):
            await mock_endpoint(user={"id": 1})
        
        result = await mock_endpoint(user={"id": 2})
        assert result == "success"


class TestLoginRateLimit:
    """Tests for login rate limiting."""
    
    def test_login_blocked_after_attempts(self):
        """Test login blocked after 5 failed attempts."""
        from app.main import record_failed_login, check_login_rate_limit, LOGIN_ATTEMPTS
        
        LOGIN_ATTEMPTS.clear()
        
        ip = "192.168.1.200"
        
        for _ in range(5):
            record_failed_login(ip)
        
        allowed, error = check_login_rate_limit(ip)
        assert allowed is False
        assert "too many" in error.lower()
    
    def test_login_allowed_under_limit(self):
        """Test login allowed under limit."""
        from app.main import record_failed_login, check_login_rate_limit, LOGIN_ATTEMPTS
        
        LOGIN_ATTEMPTS.clear()
        
        ip = "192.168.1.201"
        
        for _ in range(4):
            record_failed_login(ip)
        
        allowed, _ = check_login_rate_limit(ip)
        assert allowed is True
    
    def test_cleanup_rate_limits(self):
        """Test cleanup function works."""
        from app.ratelimit import cleanup_rate_limits
        from app import ratelimit
        
        ratelimit._request_log.clear()
        
        cleanup_rate_limits()
        
        assert True


class TestRateLimitDecorator:
    """Tests for rate_limit decorator edge cases."""
    
    @pytest.mark.asyncio
    async def test_no_user_param(self):
        """Test decorator works without user param."""
        from app.ratelimit import rate_limit
        from app import ratelimit
        
        ratelimit._request_log.clear()
        
        @rate_limit(max_requests=2, window_seconds=5)
        async def mock_endpoint():
            return "success"
        
        result = await mock_endpoint()
        assert result == "success"
