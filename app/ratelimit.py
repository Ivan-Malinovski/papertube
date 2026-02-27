"""Simple in-memory rate limiting for API endpoints."""
import time
from collections import defaultdict
from functools import wraps
from typing import Optional, Dict, List

# Store: user_id -> list of timestamps
_request_log: Dict[int, List[float]] = defaultdict(list)

def rate_limit(max_requests: int = 10, window_seconds: int = 60):
    """
    Rate limiting decorator. Limit requests per user per time window.
    
    Args:
        max_requests: Maximum number of requests allowed in the window
        window_seconds: Time window in seconds (default: 60 seconds = 1 minute)
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get user from kwargs (FastAPI injects user via Depends)
            user = kwargs.get('user')
            if not user:
                # No user found, allow request (shouldn't happen with require_user)
                return await func(*args, **kwargs)
            
            user_id = user.get('id')
            if not user_id:
                # No user ID, allow request
                return await func(*args, **kwargs)
            
            now = time.time()
            
            # Clean old requests outside the window
            _request_log[user_id] = [
                timestamp for timestamp in _request_log[user_id]
                if now - timestamp < window_seconds
            ]
            
            # Check if user exceeded limit
            if len(_request_log[user_id]) >= max_requests:
                from fastapi import HTTPException
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded. Maximum {max_requests} requests per {window_seconds} seconds."
                )
            
            # Log this request
            _request_log[user_id].append(now)
            
            # Call the actual function
            return await func(*args, **kwargs)
        return wrapper
    return decorator
