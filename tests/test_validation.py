"""
Tests for input validation.
"""
import pytest
from pydantic import ValidationError


class TestLoginRequest:
    """Tests for LoginRequest schema."""
    
    def test_valid_login(self):
        """Test valid login request passes validation."""
        from app.schemas import LoginRequest
        
        request = LoginRequest(username="testuser", password="password123")
        assert request.username == "testuser"
    
    def test_username_too_short(self):
        """Test username too short fails validation via validators, not schema."""
        from app.validators import validate_username
        
        is_valid, error = validate_username("ab")
        assert is_valid is False
        assert "at least" in error.lower()
    
    def test_username_too_long(self):
        """Test username too long fails validation."""
        from app.schemas import LoginRequest
        
        with pytest.raises(ValidationError):
            LoginRequest(username="a" * 51, password="password123")
    
    def test_username_invalid_chars(self):
        """Test invalid characters in username fail."""
        from app.schemas import LoginRequest
        
        with pytest.raises(ValidationError):
            LoginRequest(username="user@name!", password="password123")
    
    def test_username_valid_chars(self):
        """Test valid username characters pass."""
        from app.schemas import LoginRequest
        
        request = LoginRequest(username="user_123-abc", password="password123")
        assert request.username == "user_123-abc"


class TestRegisterRequest:
    """Tests for RegisterRequest schema."""
    
    def test_valid_registration(self):
        """Test valid registration passes."""
        from app.schemas import RegisterRequest
        
        request = RegisterRequest(
            username="newuser",
            password="password123",
            full_name="New User"
        )
        assert request.username == "newuser"
    
    def test_password_too_short(self):
        """Test password too short fails."""
        from app.schemas import RegisterRequest
        
        with pytest.raises(ValidationError):
            RegisterRequest(username="user", password="short", full_name="User")
    
    def test_password_too_long(self):
        """Test password too long fails."""
        from app.schemas import RegisterRequest
        
        with pytest.raises(ValidationError):
            RegisterRequest(username="user", password="a" * 129, full_name="User")


class TestSummaryRequest:
    """Tests for SummaryRequest schema."""
    
    def test_valid_youtube_url(self):
        """Test valid YouTube URL passes."""
        from app.schemas import SummaryRequest
        
        request = SummaryRequest(url="https://youtube.com/watch?v=abc123")
        assert request.url == "https://youtube.com/watch?v=abc123"
    
    def test_valid_short_url(self):
        """Test valid YouTube short URL passes."""
        from app.schemas import SummaryRequest
        
        request = SummaryRequest(url="https://youtu.be/abc123")
        assert request.url == "https://youtu.be/abc123"
    
    def test_invalid_url(self):
        """Test invalid URL fails."""
        from app.schemas import SummaryRequest
        
        with pytest.raises(ValidationError):
            SummaryRequest(url="not-a-youtube-url")
    
    def test_invalid_preset(self):
        """Test invalid preset fails."""
        from app.schemas import SummaryRequest
        
        with pytest.raises(ValidationError):
            SummaryRequest(url="abc123", preset="invalid")
    
    @pytest.mark.parametrize("preset", ["brief", "detailed", "key_points", "chapters"])
    def test_valid_presets(self, preset):
        """Test all valid presets pass."""
        from app.schemas import SummaryRequest
        
        request = SummaryRequest(url="https://youtube.com/watch?v=abc123", preset=preset)
        assert request.preset == preset


class TestValidators:
    """Tests for validator functions."""
    
    def test_validate_youtube_url_valid(self):
        """Test valid YouTube URLs."""
        from app.validators import validate_youtube_url
        
        valid_urls = [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ",
            "https://www.youtube.com/shorts/dQw4w9WgXcQ",
            "dQw4w9WgXcQ",
        ]
        
        for url in valid_urls:
            assert validate_youtube_url(url) is True
    
    def test_validate_youtube_url_invalid(self, invalid_urls):
        """Test invalid URLs."""
        from app.validators import validate_youtube_url
        
        for url in invalid_urls:
            assert validate_youtube_url(url) is False
    
    def test_validate_username_valid(self):
        """Test valid usernames."""
        from app.validators import validate_username
        
        valid_names = ["user", "user123", "user_name", "user-name", "User123"]
        for name in valid_names:
            is_valid, _ = validate_username(name)
            assert is_valid is True
    
    def test_validate_username_invalid(self):
        """Test invalid usernames."""
        from app.validators import validate_username
        
        invalid_names = ["ab", "a" * 33, "user@name", "user name"]
        for name in invalid_names:
            is_valid, _ = validate_username(name)
            assert is_valid is False
    
    def test_validate_password_valid(self):
        """Test valid passwords."""
        from app.validators import validate_password
        
        is_valid, _ = validate_password("password123")
        assert is_valid is True
    
    def test_validate_password_too_short(self):
        """Test password too short."""
        from app.validators import validate_password
        
        is_valid, error = validate_password("short")
        assert is_valid is False
        assert "at least" in error.lower()
    
    def test_sanitize_input(self):
        """Test input sanitization."""
        from app.validators import sanitize_input
        
        result = sanitize_input("  test  \0  ")
        assert result == "test"
        assert "\0" not in result
