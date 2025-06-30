"""
Video processing configuration
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class VideoConfig:
    """Configuration for video processing"""

    # Video settings
    default_fps: int = 24
    default_codec: str = "libx264"
    default_audio_codec: str = "aac"

    # Timing settings
    default_segment_duration: float = 5.0
    default_start_delay: float = 0.5
    default_end_delay: float = 0.5

    # Audio settings
    background_music_volume: float = 0.2
    default_audio_fps: int = 44100

    # Text settings
    default_font_size: int = 24
    default_text_color: str = "white"
    default_text_position: tuple = ("center", "center")

    # Cleanup settings
    cleanup_retry_attempts: int = 3
    cleanup_retry_delay: float = 2.0
    delayed_cleanup_delay: float = 30.0
    old_temp_cleanup_age_hours: float = 24.0

    # Download settings
    download_timeout: int = 30
    max_concurrent_downloads: int = 10

    # Temp directory settings
    temp_dir_prefix: str = "tmp_create_"
    batch_temp_dir: str = "tmp_pipeline"

    # Performance settings
    gc_collection_enabled: bool = True
    file_handle_release_delay: float = 1.0


# Global config instance
video_config = VideoConfig()
