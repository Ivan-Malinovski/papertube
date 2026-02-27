import aiosqlite
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Any, List, Dict

from .db_manager import get_db_pool
from .config import get_database_path

DB_PATH = Path(__file__).parent.parent / get_database_path()

PROMPT_PRESETS = {
    "brief": "Provide a brief 2-3 sentence summary of this YouTube video transcript.",
    "detailed": "Provide a detailed summary of this YouTube video transcript, covering the main points and key takeaways.",
    "key_points": "Extract the key points from this YouTube video transcript as a bullet list.",
    "chapters": "Break down this YouTube video transcript into logical chapters with timestamps and summaries for each section."
}

DEFAULT_SETTINGS = {
    "api_endpoint": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "api_token": "sk-your-api-token-here",
    "default_model": "gemini-2.0-flash",
    "dark_mode": "false",
    "prompt_presets": json.dumps(PROMPT_PRESETS)
}


async def init_db() -> None:
    """Initialize the database with tables and default settings."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(str(DB_PATH)) as db:
        # Users table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT,
                is_admin BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Summaries table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                video_id TEXT,
                video_title TEXT,
                video_url TEXT,
                channel_name TEXT,
                duration TEXT,
                thumbnail_url TEXT,
                transcript TEXT,
                summary TEXT,
                prompt_preset TEXT,
                model TEXT,
                api_endpoint TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_read BOOLEAN DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        # Migration Check: Add columns if they don't exist
        for col, col_type in [
            ("channel_name", "TEXT"), 
            ("duration", "TEXT"), 
            ("thumbnail_url", "TEXT"),
            ("user_id", "INTEGER"),
            ("is_read", "BOOLEAN DEFAULT 0")
        ]:
            try:
                await db.execute(f"ALTER TABLE summaries ADD COLUMN {col} {col_type}")
            except aiosqlite.OperationalError:
                pass

        # Settings table (Global settings)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        # Video cache table (shared across users)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS video_cache (
                video_id TEXT PRIMARY KEY,
                title TEXT,
                channel TEXT,
                duration TEXT,
                thumbnail_url TEXT,
                transcript TEXT,
                cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.commit()

        # Initialize default settings if empty
        cursor = await db.execute("SELECT COUNT(*) FROM settings")
        count_row = await cursor.fetchone()
        if count_row and count_row[0] == 0:
            for key, value in DEFAULT_SETTINGS.items():
                if key == "prompt_presets" and isinstance(value, str):
                    try: value = json.loads(value)
                    except: pass
                await update_setting(key, value)


async def get_user_count() -> int:
    """Return the total number of users."""
    count = 0
    pool = await get_db_pool(str(DB_PATH))
    async with pool.get_connection() as db:
        cursor = await db.execute("SELECT COUNT(*) FROM users")
        row = await cursor.fetchone()
        count = row[0] if row else 0
    return count


async def create_user(username: str, password_hash: str, full_name: str = "", is_admin: bool = False) -> int:
    """Create a new user."""
    pool = await get_db_pool(str(DB_PATH))
    async with pool.get_connection() as db:
        cursor = await db.execute(
            "INSERT INTO users (username, password_hash, full_name, is_admin) VALUES (?, ?, ?, ?)",
            (username, password_hash, full_name, 1 if is_admin else 0)
        )
        await db.commit()
        return int(cursor.lastrowid or 0)
    return 0


async def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    """Fetch user by username."""
    pool = await get_db_pool(str(DB_PATH))
    async with pool.get_connection() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE username = ?", (username,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Fetch user by ID."""
    pool = await get_db_pool(str(DB_PATH))
    async with pool.get_connection() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_users() -> List[Dict[str, Any]]:
    """Get all users with summary counts."""
    pool = await get_db_pool(str(DB_PATH))
    async with pool.get_connection() as db:
        db.row_factory = aiosqlite.Row
        query = """
            SELECT u.*, COUNT(s.id) as summary_count 
            FROM users u 
            LEFT JOIN summaries s ON u.id = s.user_id 
            GROUP BY u.id
            ORDER BY u.created_at DESC
        """
        async with db.execute(query) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    return []


async def delete_user(user_id: int) -> bool:
    """Delete a user and their associated summaries."""
    pool = await get_db_pool(str(DB_PATH))
    async with pool.get_connection() as db:
        await db.execute("DELETE FROM summaries WHERE user_id = ?", (user_id,))
        await db.execute("DELETE FROM users WHERE id = ?", (user_id,))
        await db.commit()
        return True
    return False


async def update_user_role(user_id: int, is_admin: bool) -> bool:
    """Update a user's admin status."""
    pool = await get_db_pool(str(DB_PATH))
    async with pool.get_connection() as db:
        await db.execute("UPDATE users SET is_admin = ? WHERE id = ?", (1 if is_admin else 0, user_id))
        await db.commit()
    return True


async def update_user_profile(user_id: int, full_name: str) -> bool:
    """Update a user's profile details."""
    pool = await get_db_pool(str(DB_PATH))
    async with pool.get_connection() as db:
        await db.execute("UPDATE users SET full_name = ? WHERE id = ?", (full_name, user_id))
        await db.commit()
    return True


async def update_user_password(user_id: int, password_hash: str) -> bool:
    """Update a user's password."""
    pool = await get_db_pool(str(DB_PATH))
    async with pool.get_connection() as db:
        await db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id))
        await db.commit()
    return True


async def save_summary(
    user_id: int,
    video_id: str,
    video_title: str,
    video_url: str,
    channel_name: str,
    duration: str,
    thumbnail_url: str,
    transcript: str,
    summary: str,
    prompt_preset: str,
    model: str,
    api_endpoint: str
) -> int:
    """Save a summary for a specific user."""
    summary_id = 0
    pool = await get_db_pool(str(DB_PATH))
    async with pool.get_connection() as db:
        cursor = await db.execute("""
            INSERT INTO summaries
            (user_id, video_id, video_title, video_url, channel_name, duration, thumbnail_url, transcript, summary, prompt_preset, model, api_endpoint)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, video_id, video_title, video_url, channel_name, duration, thumbnail_url, transcript, summary, prompt_preset, model, api_endpoint))
        await db.commit()
        if cursor.lastrowid is not None:
            summary_id = int(cursor.lastrowid)
    return summary_id


async def get_summaries(user_id: int, search: Optional[str] = None, limit: int = 100, unread_only: bool = False) -> List[Dict[str, Any]]:
    """Get summaries for a specific user."""
    rows = []
    pool = await get_db_pool(str(DB_PATH))
    async with pool.get_connection() as db:
        db.row_factory = aiosqlite.Row
        
        where_clauses = ["user_id = ?"]
        params: List[Any] = [user_id]
        
        if unread_only:
            where_clauses.append("is_read = 0")
            
        if search:
            where_clauses.append("(video_title LIKE ? OR summary LIKE ? OR channel_name LIKE ?)")
            search_param = f"%{search}%"
            params.extend([search_param, search_param, search_param])
            
        where_sql = " AND ".join(where_clauses)
        query = f"SELECT * FROM summaries WHERE {where_sql} ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
    
    return [dict(row) for row in rows]


async def get_summary(summary_id: int) -> Optional[Dict[str, Any]]:
    """Fetch a single summary (anyone can fetch for now, will keep basic for simplified logic)."""
    pool = await get_db_pool(str(DB_PATH))
    async with pool.get_connection() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM summaries WHERE id = ?", (summary_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def delete_summary(summary_id: int, user_id: int) -> bool:
    """Delete a summary if it belongs to the user."""
    pool = await get_db_pool(str(DB_PATH))
    async with pool.get_connection() as db:
        await db.execute("DELETE FROM summaries WHERE id = ? AND user_id = ?", (summary_id, user_id))
        await db.commit()
    return True


async def get_settings() -> Dict[str, Any]:
    """Get global settings."""
    settings = {}
    pool = await get_db_pool(str(DB_PATH))
    async with pool.get_connection() as db:
        cursor = await db.execute("SELECT key, value FROM settings")
        rows = await cursor.fetchall()
        settings = {row[0]: row[1] for row in rows}
        
        if "dark_mode" not in settings:
            settings["dark_mode"] = "false"
            
        raw_presets = settings.get("prompt_presets")
        if raw_presets:
            try:
                parsed_presets = json.loads(raw_presets)
                settings["prompt_presets"] = parsed_presets
            except (json.JSONDecodeError, TypeError):
                settings["prompt_presets"] = PROMPT_PRESETS
        else:
            settings["prompt_presets"] = PROMPT_PRESETS
            
        settings["prompt_presets_json"] = json.dumps(settings["prompt_presets"], indent=4)
        
    return settings


async def update_setting(key: str, value: Any) -> bool:
    """Update global setting."""
    if isinstance(value, (dict, list)):
        serialized_value = json.dumps(value)
    else:
        serialized_value = str(value)

    pool = await get_db_pool(str(DB_PATH))
    async with pool.get_connection() as db:
        await db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, serialized_value)
        )
        await db.commit()
    return True


async def mark_summary_read(summary_id: int, user_id: int, is_read: bool = True) -> bool:
    """Mark a summary as read if it belongs to the user."""
    pool = await get_db_pool(str(DB_PATH))
    async with pool.get_connection() as db:
        await db.execute(
            "UPDATE summaries SET is_read = ? WHERE id = ? AND user_id = ?",
            (1 if is_read else 0, summary_id, user_id)
        )
        await db.commit()
    return True


async def get_adjacent_summaries(user_id: int, current_id: int) -> Dict[str, Optional[Dict[str, Any]]]:
    """Get the next (older) and previous (newer) summaries for navigation."""
    result = {"next": None, "prev": None}

    pool = await get_db_pool(str(DB_PATH))
    async with pool.get_connection() as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("SELECT created_at FROM summaries WHERE id = ? AND user_id = ?", (current_id, user_id))
        row = await cursor.fetchone()
        if not row:
            return result

        current_created = row["created_at"]

        cursor = await db.execute(
            "SELECT id, video_title FROM summaries WHERE user_id = ? AND created_at < ? ORDER BY created_at DESC LIMIT 1",
            (user_id, current_created)
        )
        next_row = await cursor.fetchone()
        if next_row:
            result["next"] = {"id": next_row["id"], "video_title": next_row["video_title"]}

        cursor = await db.execute(
            "SELECT id, video_title FROM summaries WHERE user_id = ? AND created_at > ? ORDER BY created_at ASC LIMIT 1",
            (user_id, current_created)
        )
        prev_row = await cursor.fetchone()
        if prev_row:
            result["prev"] = {"id": prev_row["id"], "video_title": prev_row["video_title"]}

    return result


async def get_video_cache(video_id: str, ttl_days: int = 14) -> Optional[Dict[str, Any]]:
    """
    Get cached video metadata and transcript if not expired.
    
    Args:
        video_id: YouTube video ID
        ttl_days: Cache TTL in days (default 14)
    
    Returns:
        Cached data dict or None if expired/not found
    """
    from datetime import timedelta
    
    pool = await get_db_pool(str(DB_PATH))
    async with pool.get_connection() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT * FROM video_cache 
               WHERE video_id = ? 
               AND cached_at > datetime('now', ?)
            """,
            (video_id, f"-{ttl_days} days")
        )
        row = await cursor.fetchone()
        if row:
            return dict(row)
    return None


async def save_video_cache(
    video_id: str,
    title: str,
    channel: str,
    duration: str,
    thumbnail_url: str,
    transcript: str
) -> bool:
    """
    Save video metadata and transcript to cache.
    
    Args:
        video_id: YouTube video ID
        title: Video title
        channel: Channel name
        duration: Video duration
        thumbnail_url: Thumbnail URL
        transcript: Video transcript
    
    Returns:
        True if saved successfully
    """
    pool = await get_db_pool(str(DB_PATH))
    async with pool.get_connection() as db:
        await db.execute(
            """INSERT OR REPLACE INTO video_cache 
               (video_id, title, channel, duration, thumbnail_url, transcript, cached_at)
               VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (video_id, title, channel, duration, thumbnail_url, transcript)
        )
        await db.commit()
    return True
