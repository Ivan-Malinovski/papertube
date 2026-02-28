"""
Tests for API endpoints.
"""
import pytest


class TestApiPing:
    """Tests for /api/ping endpoint."""
    
    def test_ping_no_auth(self, app_client):
        """Test ping works without authentication."""
        response = app_client.get("/api/ping")
        
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["database"] == "connected"
    
    def test_ping_returns_json(self, app_client):
        """Test ping returns JSON."""
        response = app_client.get("/api/ping")
        
        assert "application/json" in response.headers.get("content-type", "")


class TestApiLogin:
    """Tests for /api/login endpoint."""
    
    @pytest.mark.asyncio
    async def test_login_success(self, initialized_db, app_client):
        """Test successful API login."""
        from app.database import create_user
        from app.auth import get_password_hash
        
        await create_user(
            username="apitest",
            password_hash=get_password_hash("password123"),
            full_name="API Test",
            is_admin=False
        )
        
        response = app_client.post("/api/login", json={
            "username": "apitest",
            "password": "password123"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
    
    @pytest.mark.asyncio
    async def test_login_invalid_credentials(self, initialized_db, app_client):
        """Test login with invalid credentials fails."""
        response = app_client.post("/api/login", json={
            "username": "nonexistent",
            "password": "wrong"
        })
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_login_missing_fields(self, initialized_db, app_client):
        """Test login with missing fields fails."""
        response = app_client.post("/api/login", json={
            "username": "test"
        })
        
        assert response.status_code in [401, 422]


class TestApiSummarize:
    """Tests for /api/summarize endpoint."""
    
    def test_summarize_requires_auth(self, app_client):
        """Test summarize requires authentication."""
        response = app_client.post("/api/summarize", json={
            "url": "https://youtube.com/watch?v=test"
        })
        
        assert response.status_code in [401, 403]
    
    @pytest.mark.asyncio
    async def test_summarize_with_auth(self, db_with_user, app_client):
        """Test summarize with valid auth."""
        from app.auth import create_access_token
        
        token = create_access_token(data={"sub": "testuser"})
        
        response = app_client.post(
            "/api/summarize",
            json={"url": "https://youtube.com/watch?v=test"},
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code in [200, 400, 500]


class TestWebRoutes:
    """Tests for web routes."""
    
    def test_index_page(self, app_client):
        """Test index page loads."""
        response = app_client.get("/")
        
        assert response.status_code == 200
    
    def test_login_page(self, app_client):
        """Test login page loads."""
        response = app_client.get("/login")
        
        assert response.status_code == 200
    
    def test_register_page(self, app_client):
        """Test register page loads."""
        response = app_client.get("/register")
        
        assert response.status_code == 200
