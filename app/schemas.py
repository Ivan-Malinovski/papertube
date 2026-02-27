from pydantic import BaseModel, Field, field_validator
from typing import Optional
import re


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1)
    
    @field_validator('username')
    @classmethod
    def validate_username(cls, v: str) -> str:
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('Username can only contain letters, numbers, underscores, and hyphens')
        return v.strip()
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 1:
            raise ValueError('Password is required')
        return v


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=32)
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(default="", max_length=100)
    
    @field_validator('username')
    @classmethod
    def validate_username(cls, v: str) -> str:
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('Username can only contain letters, numbers, underscores, and hyphens')
        return v.strip()
    
    @field_validator('full_name')
    @classmethod
    def validate_full_name(cls, v: str) -> str:
        return v.strip() if v else ""


class SummaryRequest(BaseModel):
    url: str = Field(..., min_length=10, max_length=2048)
    preset: str = Field(default="detailed", max_length=50)
    
    @field_validator('url')
    @classmethod
    def validate_url(cls, v: str) -> str:
        v = v.strip()
        if re.match(r'^[a-zA-Z0-9_-]{11}$', v):
            return v
        if re.match(r'https?://[^\s]+', v):
            return v
        raise ValueError('Invalid YouTube URL format')
    
    @field_validator('preset')
    @classmethod
    def validate_preset(cls, v: str) -> str:
        allowed = ['brief', 'detailed', 'key_points', 'chapters']
        if v not in allowed:
            raise ValueError(f'Preset must be one of: {", ".join(allowed)}')
        return v


class ChatRequest(BaseModel):
    id: int = Field(..., gt=0)
    message: str = Field(..., min_length=1, max_length=10000)
    
    @field_validator('message')
    @classmethod
    def validate_message(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError('Message cannot be empty')
        return v


class AdminUserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=32)
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(default="", max_length=100)
    is_admin: bool = Field(default=False)
    
    @field_validator('username')
    @classmethod
    def validate_username(cls, v: str) -> str:
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('Username can only contain letters, numbers, underscores, and hyphens')
        return v.strip()


class SettingsUpdate(BaseModel):
    key: str = Field(..., max_length=100)
    value: str = Field(..., max_length=10000)
    
    @field_validator('key')
    @classmethod
    def validate_key(cls, v: str) -> str:
        allowed_keys = [
            'api_endpoint', 'api_token', 'default_model',
            'dark_mode', 'prompt_presets'
        ]
        if v not in allowed_keys:
            raise ValueError(f'Invalid setting key. Allowed: {", ".join(allowed_keys)}')
        return v
