"""
Tests for configuration.
"""
import os
import pytest
from unittest.mock import patch


class TestSettingsDefaults:
    """Test default configuration values."""
    
    def test_server_defaults(self):
        """Test server defaults."""
        from app.config import Settings
        
        settings = Settings()
        
        assert settings.host == "0.0.0.0"
        assert settings.port == 8080
    
    def test_rate_limit_defaults(self):
        """Test rate limit defaults."""
        from app.config import Settings
        
        settings = Settings()
        
        assert settings.login_max_attempts == 5
        assert settings.login_lockout_window == 900
    
    def test_llm_defaults(self):
        """Test LLM defaults."""
        from app.config import Settings
        
        settings = Settings()
        
        assert "google" in settings.default_api_endpoint.lower()
        assert settings.default_model == "gemini-2.5-flash"
    
    def test_secret_key_generated(self):
        """Test secret key is generated if not provided."""
        from app.config import get_secret_key
        
        key = get_secret_key()
        
        assert key is not None
        assert len(key) > 0


class TestConfigFunctions:
    """Test config helper functions."""
    
    def test_get_settings(self):
        """Test getting settings object."""
        from app.config import get_settings
        
        settings = get_settings()
        
        assert settings is not None
        assert hasattr(settings, 'host')
        assert hasattr(settings, 'port')
    
    def test_get_login_max_attempts(self):
        """Test login max attempts helper."""
        from app.config import get_login_max_attempts
        
        max_attempts = get_login_max_attempts()
        
        assert isinstance(max_attempts, int)
        assert max_attempts > 0
