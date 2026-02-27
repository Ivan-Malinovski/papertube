"""
Tests for authentication functionality.
"""
import pytest
from unittest.mock import Mock, AsyncMock


class TestPasswordHashing:
    """Tests for password hashing."""
    
    def test_hash_password(self):
        """Test password hashing produces different hashes."""
        from app.auth import get_password_hash, verify_password
        
        password = "testpassword123"
        hashed = get_password_hash(password)
        
        assert hashed != password
        assert verify_password(password, hashed) is True
        assert verify_password("wrongpassword", hashed) is False
    
    def test_different_hashes_same_password(self):
        """Test same password produces different hashes (salt)."""
        from app.auth import get_password_hash
        
        password = "testpassword123"
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)
        
        assert hash1 != hash2
        assert hash1 != password
        assert hash2 != password
    
    def test_hash_unicode_password(self):
        """Test hashing works with unicode passwords."""
        from app.auth import get_password_hash, verify_password
        
        password = "пароль123中文"
        hashed = get_password_hash(password)
        
        assert verify_password(password, hashed) is True


class TestJWT:
    """Tests for JWT token handling."""
    
    def test_create_access_token(self):
        """Test JWT token creation."""
        from app.auth import create_access_token
        
        token = create_access_token(data={"sub": "testuser"})
        
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0
    
    def test_token_is_jwt_format(self):
        """Test token is valid JWT format."""
        from app.auth import create_access_token
        
        token = create_access_token(data={"sub": "testuser"})
        
        parts = token.split('.')
        assert len(parts) == 3


class TestRequireUser:
    """Tests for user requirement in endpoints."""
    
    @pytest.mark.asyncio
    async def test_require_user_no_token(self):
        """Test require_user returns 401 without token."""
        from app.auth import require_user
        from fastapi import HTTPException
        from unittest.mock import AsyncMock
        
        request = AsyncMock()
        request.headers = {"accept": "application/json"}
        request.url.path = "/test"
        request.url.query = ""
        
        with pytest.raises(HTTPException) as exc_info:
            await require_user(request, user=None)
        
        assert exc_info.value.status_code == 401
    
    @pytest.mark.asyncio
    async def test_require_user_with_valid_user(self):
        """Test require_user passes with valid user."""
        from app.auth import require_user
        
        request = AsyncMock()
        user = {"id": 1, "username": "testuser"}
        
        result = await require_user(request, user=user)
        
        assert result == user


class TestLoginAttempts:
    """Tests for login attempt tracking."""
    
    def test_record_failed_login(self):
        """Test recording failed login attempts."""
        from app.main import record_failed_login, LOGIN_ATTEMPTS
        
        ip = "192.168.1.100"
        record_failed_login(ip)
        
        assert ip in LOGIN_ATTEMPTS
        assert len(LOGIN_ATTEMPTS[ip]) == 1
    
    def test_login_rate_limit_accumulates(self):
        """Test multiple failed logins accumulate."""
        from app.main import record_failed_login, check_login_rate_limit, LOGIN_ATTEMPTS
        
        ip = "192.168.1.101"
        
        for _ in range(4):
            record_failed_login(ip)
        
        allowed, _ = check_login_rate_limit(ip)
        assert allowed is True
        
        record_failed_login(ip)
        
        allowed, error = check_login_rate_limit(ip)
        assert allowed is False
        assert "too many" in error.lower()
    
    def test_login_allowed_after_cleanup(self):
        """Test login allowed after lockout cleanup."""
        from app.main import record_failed_login, check_login_rate_limit, LOGIN_ATTEMPTS
        
        ip = "192.168.1.102"
        
        for _ in range(5):
            record_failed_login(ip)
        
        allowed, _ = check_login_rate_limit(ip)
        assert allowed is False
        
        LOGIN_ATTEMPTS.pop(ip, None)
        
        allowed, _ = check_login_rate_limit(ip)
        assert allowed is True
