"""Simple in-memory rate limiting for API endpoints."""
import time
from collections import defaultdict
from functools import wraps
from typing import Optional, Dict, List

from .config import get_api_rate_limit_max_requests, get_api_rate_limit_window_seconds

# Store: user_id -> list of timestamps
_request_log: Dict[int, List[float]] = defaultdict(list)

# Cleanup threshold - clean up entries older than this (in seconds)
_CLEANUP_THRESHOLD = 3600  # 1 hour

def _cleanup_old_entries():
    """Remove old entries from rate limit storage to prevent memory leak."""
    now = time.time()
    expired_keys = [
        uid for uid, timestamps in _request_log.items()
        if not timestamps or (now - max(timestamps)) > _CLEANUP_THRESHOLD
    ]
    for uid in expired_keys:
        del _request_log[uid]

def cleanup_rate_limits():
    """Manually cleanup all rate limit storage. Call periodically or on shutdown."""
    _cleanup_old_entries()

def rate_limit(max_requests: Optional[int] = None, window_seconds: Optional[int] = None):
    """
    Rate limiting decorator. Limit requests per user per time window.
    
    Args:
        max_requests: Maximum number of requests allowed in the window (default from config)
        window_seconds: Time window in seconds (default from config)
    """
    # Periodic cleanup (every 100 requests to reduce overhead)
    if len(_request_log) > 0 and sum(len(v) for v in _request_log.values()) % 100 == 0:
        _cleanup_old_entries()
    
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            effective_max_requests = max_requests if max_requests is not None else get_api_rate_limit_max_requests()
            effective_window_seconds = window_seconds if window_seconds is not None else get_api_rate_limit_window_seconds()
            
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
                if now - timestamp <= effective_window_seconds
            ]
            
            # Check if user exceeded limit
            if len(_request_log[user_id]) >= effective_max_requests:
                from fastapi import HTTPException
                oldest_request = min(_request_log[user_id])
                retry_after = int(effective_window_seconds - (now - oldest_request))
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded. Maximum {effective_max_requests} requests per {effective_window_seconds} seconds.",
                    headers={"Retry-After": str(max(1, retry_after))}
                )
            
            # Log this request
            _request_log[user_id].append(now)
            
            # Call the actual function
            return await func(*args, **kwargs)
        return wrapper
    return decorator
