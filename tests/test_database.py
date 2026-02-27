"""
Tests for database operations.
"""
import pytest


class TestUserOperations:
    """Tests for user CRUD operations."""
    
    @pytest.mark.asyncio
    async def test_create_user(self, initialized_db):
        """Test user creation."""
        from app.database import create_user, get_user_by_username
        from app.auth import get_password_hash
        
        user_id = await create_user(
            username="newuser",
            password_hash=get_password_hash("password123"),
            full_name="New User",
            is_admin=False
        )
        
        assert user_id > 0
        
        user = await get_user_by_username("newuser")
        assert user is not None
        assert user["username"] == "newuser"
        assert user["is_admin"] == 0
    
    @pytest.mark.asyncio
    async def test_create_duplicate_user_fails(self, initialized_db):
        """Test creating duplicate username fails."""
        from app.database import create_user
        from app.auth import get_password_hash
        
        await create_user(
            username="duplicate",
            password_hash=get_password_hash("pass"),
            full_name="User One",
            is_admin=False
        )
        
        with pytest.raises(Exception):
            await create_user(
                username="duplicate",
                password_hash=get_password_hash("pass"),
                full_name="User Two",
                is_admin=False
            )
    
    @pytest.mark.asyncio
    async def test_get_user_by_id(self, db_with_user):
        """Test getting user by ID."""
        from app.database import get_user_by_id
        
        user = await get_user_by_id(db_with_user["user_id"])
        
        assert user is not None
        assert user["id"] == db_with_user["user_id"]
        assert user["username"] == "testuser"
    
    @pytest.mark.asyncio
    async def test_update_user_role(self, initialized_db):
        """Test updating user role."""
        from app.database import create_user, update_user_role, get_user_by_id
        from app.auth import get_password_hash
        
        user_id = await create_user(
            username="roleuser",
            password_hash=get_password_hash("pass"),
            full_name="Role User",
            is_admin=False
        )
        
        await update_user_role(user_id, True)
        user = await get_user_by_id(user_id)
        assert user["is_admin"] == 1
        
        await update_user_role(user_id, False)
        user = await get_user_by_id(user_id)
        assert user["is_admin"] == 0
    
    @pytest.mark.asyncio
    async def test_delete_user(self, initialized_db):
        """Test deleting user."""
        from app.database import create_user, delete_user, get_user_by_id
        from app.auth import get_password_hash
        
        user_id = await create_user(
            username="deleteuser",
            password_hash=get_password_hash("pass"),
            full_name="Delete User",
            is_admin=False
        )
        
        result = await delete_user(user_id)
        assert result is True
        
        user = await get_user_by_id(user_id)
        assert user is None


class TestSummaryOperations:
    """Tests for summary CRUD operations."""
    
    @pytest.mark.asyncio
    async def test_save_and_get_summary(self, db_with_user):
        """Test saving and retrieving a summary."""
        from app.database import save_summary, get_summary
        
        summary_id = await save_summary(
            user_id=db_with_user["user_id"],
            video_id="testvideo123",
            video_title="Test Video Title",
            video_url="https://youtube.com/watch?v=testvideo123",
            channel_name="Test Channel",
            duration="10:00",
            thumbnail_url="https://example.com/thumb.jpg",
            transcript="Test transcript content",
            summary="Test summary content",
            prompt_preset="detailed",
            model="gemini-2.0-flash",
            api_endpoint="https://api.test.com"
        )
        
        assert summary_id > 0
        
        summary = await get_summary(summary_id)
        assert summary is not None
        assert summary["video_title"] == "Test Video Title"
        assert summary["user_id"] == db_with_user["user_id"]
    
    @pytest.mark.asyncio
    async def test_get_summaries(self, db_with_user):
        """Test getting user summaries."""
        from app.database import save_summary, get_summaries
        
        for i in range(3):
            await save_summary(
                user_id=db_with_user["user_id"],
                video_id=f"video{i}",
                video_title=f"Video {i}",
                video_url=f"https://youtube.com/watch?v=video{i}",
                channel_name="Test Channel",
                duration="10:00",
                thumbnail_url="https://example.com/thumb.jpg",
                transcript="transcript",
                summary=f"summary {i}",
                prompt_preset="detailed",
                model="test-model",
                api_endpoint="https://api.test.com"
            )
        
        summaries = await get_summaries(db_with_user["user_id"])
        
        assert len(summaries) >= 3
    
    @pytest.mark.asyncio
    async def test_search_summaries(self, db_with_user):
        """Test searching summaries by title."""
        from app.database import save_summary, get_summaries
        
        await save_summary(
            user_id=db_with_user["user_id"],
            video_id="searchtest",
            video_title="Unique Search Title 12345",
            video_url="https://youtube.com/watch?v=searchtest",
            channel_name="Test Channel",
            duration="10:00",
            thumbnail_url="https://example.com/thumb.jpg",
            transcript="transcript",
            summary="summary",
            prompt_preset="detailed",
            model="test-model",
            api_endpoint="https://api.test.com"
        )
        
        results = await get_summaries(db_with_user["user_id"], search="Unique")
        assert len(results) >= 1
        assert "Unique" in results[0]["video_title"]
    
    @pytest.mark.asyncio
    async def test_delete_summary(self, db_with_user):
        """Test deleting a summary."""
        from app.database import save_summary, delete_summary, get_summary
        
        summary_id = await save_summary(
            user_id=db_with_user["user_id"],
            video_id="deletetest",
            video_title="Delete Test",
            video_url="https://youtube.com/watch?v=deletetest",
            channel_name="Test Channel",
            duration="10:00",
            thumbnail_url="https://example.com/thumb.jpg",
            transcript="transcript",
            summary="summary",
            prompt_preset="detailed",
            model="test-model",
            api_endpoint="https://api.test.com"
        )
        
        await delete_summary(summary_id, db_with_user["user_id"])
        
        summary = await get_summary(summary_id)
        if summary:
            assert summary["user_id"] != db_with_user["user_id"]
    
    @pytest.mark.asyncio
    async def test_mark_summary_read(self, db_with_user):
        """Test marking summary as read."""
        from app.database import save_summary, mark_summary_read, get_summary
        
        summary_id = await save_summary(
            user_id=db_with_user["user_id"],
            video_id="readtest",
            video_title="Read Test",
            video_url="https://youtube.com/watch?v=readtest",
            channel_name="Test Channel",
            duration="10:00",
            thumbnail_url="https://example.com/thumb.jpg",
            transcript="transcript",
            summary="summary",
            prompt_preset="detailed",
            model="test-model",
            api_endpoint="https://api.test.com"
        )
        
        await mark_summary_read(summary_id, db_with_user["user_id"], True)
        
        summary = await get_summary(summary_id)
        assert summary["is_read"] == 1


class TestSettings:
    """Tests for settings operations."""
    
    @pytest.mark.asyncio
    async def test_get_settings(self, initialized_db):
        """Test getting settings."""
        from app.database import get_settings
        
        settings = await get_settings()
        
        assert settings is not None
        assert "api_endpoint" in settings
        assert "default_model" in settings
    
    @pytest.mark.asyncio
    async def test_update_setting(self, initialized_db):
        """Test updating a setting."""
        from app.database import update_setting, get_settings
        
        await update_setting("test_key", "test_value")
        
        settings = await get_settings()
        assert "test_key" in settings
    
    @pytest.mark.asyncio
    async def test_prompt_presets_parsing(self, initialized_db):
        """Test prompt presets are parsed correctly."""
        from app.database import get_settings
        
        settings = await get_settings()
        
        assert "prompt_presets" in settings
        assert isinstance(settings["prompt_presets"], dict)
