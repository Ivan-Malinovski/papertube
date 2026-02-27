import os
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Union, Any
from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from .database import get_user_by_username

# Security configuration
SECRET_KEY = os.getenv("SECRET_KEY") or secrets.token_hex(32)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 365  # 1 year (stay logged in until manual logout)

# Use PBKDF2 with HMAC-SHA256 for maximum reliability and security.
# This algorithm is built-in and does NOT have the 72-character limit that caused errors.
pwd_context = CryptContext(
    schemes=["pbkdf2_sha256"], 
    deprecated="auto"
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login", auto_error=False)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against its hashed version."""
    # Note: No need for pre-hashing here as pbkdf2_sha256 has no length issues.
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hashes a password for secure storage."""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Generates a secure JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(request: Request):
    """
    Get the current user from either a Cookie (web) or Authorization header (API/Extension).
    """
    token = None
    
    # 1. Try to get token from Authorization header (Extension/API)
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    
    # 2. Try to get token from Cookies (Web UI)
    if not token:
        auth_cookie = request.cookies.get("access_token")
        if auth_cookie and auth_cookie.startswith("Bearer "):
            token = auth_cookie.split(" ")[1]

    if not token:
        return None

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
    except JWTError:
        return None

    user = await get_user_by_username(username)
    return user

async def require_user(request: Request, user = Depends(get_current_user)):
    if not user:
        # Redirect to login with 'next' parameter if it's a browser request
        if "text/html" in request.headers.get("accept", ""):
            path = request.url.path
            query = request.url.query
            full_path = f"{path}?{query}" if query else path
            raise HTTPException(
                status_code=status.HTTP_307_TEMPORARY_REDIRECT,
                headers={"Location": f"/login?next={full_path}"}
            )
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
