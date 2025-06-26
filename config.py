"""
Application configuration using Pydantic Settings
"""

from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    """Application settings with environment variable support"""

    # API Settings
    api_title: str = "Video Creation API"
    api_description: str = "Professional video creation service with batch processing"
    api_version: str = "1.0.0"

    # Server Settings
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # File Upload Settings
    max_file_size: int = 100 * 1024 * 1024  # 100MB
    allowed_extensions: list = [".json"]
    upload_timeout: int = 300  # 5 minutes

    # Temporary Directory Settings
    temp_dir_prefix: str = "tmp_create_"
    cleanup_temp_files: bool = True

    # CORS Settings
    cors_origins: list = ["http://localhost:3000", "http://localhost:8080"]
    cors_allow_credentials: bool = True
    cors_allow_methods: list = ["GET", "POST"]
    cors_allow_headers: list = ["*"]

    # Logging Settings
    log_level: str = "INFO"
    log_format: str = "[%(asctime)s] %(levelname)s %(name)s: %(message)s"
    log_date_format: str = "%Y-%m-%d %H:%M:%S"

    # Video Processing Settings
    default_video_fps: int = 24
    default_video_codec: str = "libx264"
    default_audio_codec: str = "aac"
    default_resolution: tuple = (1280, 720)

    # Security Settings
    request_timeout: int = 300  # 5 minutes
    max_concurrent_requests: int = 10

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()
