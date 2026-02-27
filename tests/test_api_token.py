"""
Tests for API token validation.
"""
import pytest


class TestApiTokenValidation:
    """Tests for API token validation."""
    
    def test_valid_token(self):
        """Test valid token passes."""
        from app.main import check_api_token_configured
        
        result = check_api_token_configured("sk-valid-token-12345678")
        assert result is True
    
    def test_placeholder_token_rejected(self):
        """Test placeholder token is rejected."""
        from app.main import check_api_token_configured
        
        result = check_api_token_configured("sk-your-api-token-here")
        assert result is False
    
    def test_empty_token_rejected(self):
        """Test empty token is rejected."""
        from app.main import check_api_token_configured
        
        result = check_api_token_configured("")
        assert result is False
    
    def test_none_token_rejected(self):
        """Test None token is rejected."""
        from app.main import check_api_token_configured
        
        result = check_api_token_configured(None)
        assert result is False
    
    def test_token_too_short(self):
        """Test token that's too short is rejected."""
        from app.main import check_api_token_configured
        
        result = check_api_token_configured("sk-short")
        assert result is False
    
    def test_only_spaces_rejected(self):
        """Test token with only spaces is rejected."""
        from app.main import check_api_token_configured
        
        result = check_api_token_configured("   ")
        assert result is False


class TestApiTokenFormat:
    """Tests for detailed API token format validation."""
    
    def test_validate_token_format_valid(self):
        """Test valid token format passes."""
        from app.main import validate_api_token_format
        
        is_valid, error = validate_api_token_format("sk-test-token-12345678")
        
        assert is_valid is True
        assert error == ""
    
    def test_validate_token_format_empty(self):
        """Test empty token fails."""
        from app.main import validate_api_token_format
        
        is_valid, error = validate_api_token_format("")
        
        assert is_valid is False
        assert "required" in error.lower()
    
    def test_validate_token_format_too_short(self):
        """Test token too short fails."""
        from app.main import validate_api_token_format
        
        is_valid, error = validate_api_token_format("sk-ab")
        
        assert is_valid is False
        assert "at least" in error.lower()
    
    def test_validate_token_format_invalid_chars(self):
        """Test invalid characters fail."""
        from app.main import validate_api_token_format
        
        is_valid, error = validate_api_token_format("sk-token@#$%")
        
        assert is_valid is False
