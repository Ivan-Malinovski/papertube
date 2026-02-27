"""
Centralized configuration management for Papertube.
Uses Pydantic Settings with environment variable support.
Maintains backward compatibility with existing configuration.
"""
import os
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8080, description="Server port")
    
    secret_key: str = Field(
        default="",
        description="JWT secret key. If empty, generates random key on startup (not recommended for production)"
    )
    algorithm: str = Field(default="HS256", description="JWT algorithm")
    access_token_expire_minutes: int = Field(
        default=525600,
        description="JWT token expiration in minutes"
    )
    
    login_max_attempts: int = Field(
        default=5,
        description="Maximum login attempts before lockout"
    )
    login_lockout_window: int = Field(
        default=900,
        description="Login lockout duration in seconds"
    )
    api_rate_limit_max_requests: int = Field(
        default=10,
        description="Maximum API requests per window"
    )
    api_rate_limit_window_seconds: int = Field(
        default=60,
        description="API rate limit window in seconds"
    )
    
    default_api_endpoint: str = Field(
        default="https://generativelanguage.googleapis.com/v1beta/openai/",
        description="Default LLM API endpoint"
    )
    default_model: str = Field(
        default="gemini-2.0-flash",
        description="Default LLM model"
    )
    
    database_path: str = Field(
        default="data/summaries.db",
        description="SQLite database file path"
    )
    
    dark_mode: bool = Field(default=False, description="Default dark mode")
    
    class Config:
        env_prefix = "PAPERTUBE_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get the global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def init_settings(**overrides) -> Settings:
    """
    Initialize settings with optional overrides.
    Useful for testing or runtime configuration.
    """
    global _settings
    _settings = Settings(**overrides)
    return _settings


def get_secret_key() -> str:
    """Get JWT secret key."""
    settings = get_settings()
    if not settings.secret_key:
        import secrets
        return secrets.token_hex(32)
    return settings.secret_key


def get_algorithm() -> str:
    """Get JWT algorithm."""
    return get_settings().algorithm


def get_access_token_expire_minutes() -> int:
    """Get JWT token expiration in minutes."""
    return get_settings().access_token_expire_minutes


def get_login_max_attempts() -> int:
    """Get maximum login attempts before lockout."""
    return get_settings().login_max_attempts


def get_login_lockout_window() -> int:
    """Get login lockout window in seconds."""
    return get_settings().login_lockout_window


def get_api_rate_limit_max_requests() -> int:
    """Get maximum API requests per rate limit window."""
    return get_settings().api_rate_limit_max_requests


def get_api_rate_limit_window_seconds() -> int:
    """Get API rate limit window in seconds."""
    return get_settings().api_rate_limit_window_seconds


def get_default_api_endpoint() -> str:
    """Get default LLM API endpoint."""
    return get_settings().default_api_endpoint


def get_default_model() -> str:
    """Get default LLM model."""
    return get_settings().default_model


def get_database_path() -> str:
    """Get database file path."""
    return get_settings().database_path
