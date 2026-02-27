import re
from typing import Optional


def sanitize_input(text: str, max_length: Optional[int] = None) -> str:
    if not text:
        return ""
    
    text = text.replace('\0', '')
    text = text.strip()
    
    if max_length and len(text) > max_length:
        text = text[:max_length]
    
    return text


def validate_youtube_url(url: str) -> bool:
    if not url:
        return False
    
    url = url.strip()
    
    if re.match(r'^[a-zA-Z0-9_-]{11}$', url):
        return True
    
    patterns = [
        r'https?://(?:www\.)?youtube\.com/watch\?v=[a-zA-Z0-9_-]{11}',
        r'https?://(?:www\.)?youtu\.be/[a-zA-Z0-9_-]{11}',
        r'https?://(?:www\.)?youtube\.com/shorts/[a-zA-Z0-9_-]{11}',
        r'https?://(?:www\.)?youtube\.com/live/[a-zA-Z0-9_-]{11}',
    ]
    
    return any(re.match(pattern, url) for pattern in patterns)


def validate_username(username: str) -> tuple[bool, str]:
    if not username:
        return False, "Username is required"
    
    if len(username) < 3:
        return False, "Username must be at least 3 characters"
    
    if len(username) > 32:
        return False, "Username must be at most 32 characters"
    
    if not re.match(r'^[a-zA-Z0-9_-]+$', username):
        return False, "Username can only contain letters, numbers, underscores, and hyphens"
    
    return True, ""


def validate_password(password: str) -> tuple[bool, str]:
    if not password:
        return False, "Password is required"
    
    if len(password) < 8:
        return False, "Password must be at least 8 characters"
    
    if len(password) > 128:
        return False, "Password must be at most 128 characters"
    
    return True, ""
