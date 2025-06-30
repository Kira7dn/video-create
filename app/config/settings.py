"""
Application configuration using Pydantic Settings
"""

from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import Optional, List, Union
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
    cors_origins: Union[List[str], str] = [
        "http://localhost:3000",
        "http://localhost:8080",
    ]
    cors_allow_credentials: bool = True
    cors_allow_methods: list = ["GET", "POST"]
    cors_allow_headers: list = ["*"]

    @field_validator("cors_origins")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            if v == "*":
                return ["*"]
            return [origin.strip() for origin in v.split(",")]
        return v

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

    # Ngrok Settings
    ngrok_authtoken: str = ""
    ngrok_url: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()
