"""
Pytest configuration and shared fixtures.
Robust version with proper test isolation.
"""
import asyncio
import os
import pytest
import tempfile
import shutil
import sys
from pathlib import Path
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

os.environ["PAPERTUBE_TESTING"] = "1"


@pytest.fixture(scope="session")
def temp_dir() -> Generator[str, None, None]:
    """Create a temporary directory for test session."""
    tmpdir = tempfile.mkdtemp(prefix="papertube_test_")
    yield tmpdir
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def temp_db_path(temp_dir: str) -> str:
    """Create a unique temporary database file for each test."""
    import uuid
    db_name = f"test_{uuid.uuid4().hex}.db"
    db_path = os.path.join(temp_dir, db_name)
    yield db_path
    try:
        os.unlink(db_path)
    except FileNotFoundError:
        pass


@pytest.fixture(autouse=True)
def reset_app_state():
    """Reset global state before each test for isolation."""
    import app.ratelimit as ratelimit_module
    import app.main as main_module
    import app.db_manager as db_manager_module
    
    ratelimit_module._request_log.clear() if hasattr(ratelimit_module, '_request_log') else None
    main_module.LOGIN_ATTEMPTS.clear() if hasattr(main_module, 'LOGIN_ATTEMPTS') else None
    
    original_pool = db_manager_module._db_pool
    db_manager_module._db_pool = None
    
    yield
    
    if hasattr(ratelimit_module, '_request_log'):
        ratelimit_module._request_log.clear()
    if hasattr(main_module, 'LOGIN_ATTEMPTS'):
        main_module.LOGIN_ATTEMPTS.clear()
    db_manager_module._db_pool = original_pool


@pytest.fixture
async def initialized_db(temp_db_path: str) -> AsyncGenerator[str, None]:
    """Create and initialize a test database with schema."""
    from app.database import init_db
    import app.database
    import app.db_manager as db_manager
    
    original_path = app.database.DB_PATH
    app.database.DB_PATH = Path(temp_db_path)
    
    await init_db()
    
    yield temp_db_path
    
    if db_manager._db_pool:
        await db_manager._db_pool.close_all()
        db_manager._db_pool = None
    app.database.DB_PATH = original_path


@pytest.fixture
async def db_with_user(initialized_db: str) -> AsyncGenerator[dict, None]:
    """Create database with a test user."""
    from app.database import create_user, get_user_by_username
    from app.auth import get_password_hash
    
    user_id = await create_user(
        username="testuser",
        password_hash=get_password_hash("testpassword123"),
        full_name="Test User",
        is_admin=False
    )
    
    user = await get_user_by_username("testuser")
    
    yield {
        "db_path": initialized_db,
        "user": user,
        "user_id": user_id
    }


@pytest.fixture
def test_user() -> dict:
    """Provide a test user dictionary (not in DB)."""
    return {
        "id": 1,
        "username": "testuser",
        "password": "testpassword123",
        "password_hash": "$pbkdf2-sha256$29000$test$testhash",
        "full_name": "Test User",
        "is_admin": True
    }


@pytest.fixture
def test_settings() -> dict:
    """Provide mock settings for testing."""
    return {
        "api_endpoint": "https://api.test.com/v1",
        "api_token": "sk-test-token-12345678",
        "default_model": "test-model",
        "dark_mode": "false",
        "prompt_presets": {
            "brief": "Brief test summary.",
            "detailed": "Detailed test summary.",
            "key_points": "Key points test.",
            "chapters": "Chapters test."
        }
    }


@pytest.fixture
def mock_httpx() -> Generator[MagicMock, None, None]:
    """Provide a mock for httpx.AsyncClient."""
    with patch('httpx.AsyncClient') as mock:
        yield mock


@pytest.fixture
def app_client():
    """Provide a test client for the FastAPI app."""
    from fastapi.testclient import TestClient
    from app.main import app
    
    with TestClient(app) as client:
        yield client


class MockResponse:
    """Simple mock response for httpx."""
    
    def __init__(self, status: int = 200, json_data: dict = None, text: str = ""):
        self.status_code = status
        self._json_data = json_data or {}
        self.text = text
    
    def json(self):
        return self._json_data
    
    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


@pytest.fixture
def mock_llm_response() -> MockResponse:
    """Provide a mock LLM API response."""
    return MockResponse(
        status=200,
        json_data={
            "choices": [
                {"message": {"content": "This is a test summary."}}
            ]
        }
    )


@pytest.fixture
def create_mock_httpx(mock_httpx) -> callable:
    """Factory to create mocked HTTP clients."""
    def _create(response: MockResponse = None):
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=response or MockResponse())
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_httpx.return_value = mock_client
        return mock_client
    return _create


@pytest.fixture
def sample_transcript() -> str:
    """Provide a sample transcript for testing."""
    return """
    Welcome to this video about Python testing.
    Today we're going to discuss pytest and how to write effective tests.
    First, let's talk about why testing is important.
    Testing helps us catch bugs early and maintain confidence in our code.
    There are many testing frameworks available, but pytest is one of the most popular.
    Thank you for watching this video.
    """


@pytest.fixture
def sample_youtube_urls() -> list:
    """Provide sample YouTube URLs for testing."""
    return [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ",
        "https://www.youtube.com/shorts/dQw4w9WgXcQ",
        "https://www.youtube.com/v/dQw4w9WgXcQ",
        "dQw4w9WgXcQ",
    ]


@pytest.fixture
def invalid_urls() -> list:
    """Provide invalid URLs for testing."""
    return [
        "https://example.com/video",
        "not a url",
        "",
        "https://vimeo.com/123456",
        "https://youtube.com/watch?v=",
    ]
