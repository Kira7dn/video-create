"""
Resource management utilities for video processing
"""

import os
import gc
import time
import logging
import shutil
import threading
from contextlib import contextmanager, asynccontextmanager
from typing import List, Optional, Union, AsyncIterator
from pathlib import Path

from moviepy import VideoFileClip, AudioFileClip, ImageClip
from app.services.config.video_config import video_config

logger = logging.getLogger(__name__)


class ResourceManager:
    """Manages file resources and cleanup operations"""

    def __init__(self):
        self.tracked_files: List[str] = []
        self.tracked_clips: List[Union[VideoFileClip, AudioFileClip, ImageClip]] = []

    def track_file(self, file_path: str) -> str:
        """Track a file for automatic cleanup"""
        self.tracked_files.append(file_path)
        return file_path

    def track_clip(self, clip: Union[VideoFileClip, AudioFileClip, ImageClip]):
        """Track a clip for automatic cleanup"""
        self.tracked_clips.append(clip)
        return clip

    def cleanup_clips(self):
        """Clean up all tracked clips"""
        for clip in self.tracked_clips:
            try:
                clip.close()
                logger.debug(f"✅ Closed clip: {type(clip).__name__}")
            except Exception as e:
                logger.warning(f"Failed to close clip {type(clip).__name__}: {e}")
        self.tracked_clips.clear()

    def cleanup_files(self):
        """Clean up all tracked files"""
        for file_path in self.tracked_files:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.debug(f"✅ Removed file: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to remove file {file_path}: {e}")
                # Schedule delayed cleanup
                self._schedule_delayed_cleanup(file_path)
        self.tracked_files.clear()

    def cleanup_all(self):
        """Clean up all tracked resources"""
        self.cleanup_clips()
        self.cleanup_files()

        if video_config.gc_collection_enabled:
            gc.collect()

    def _schedule_delayed_cleanup(
        self, path: str, delay_seconds: Optional[float] = None
    ):
        """Schedule delayed cleanup for a file or directory"""
        if delay_seconds is None:
            delay_seconds = video_config.delayed_cleanup_delay

        def delayed_cleanup():
            try:
                time.sleep(delay_seconds)
                if os.path.exists(path):
                    if os.path.isfile(path):
                        os.remove(path)
                        logger.info(f"🕒 Delayed cleanup: Removed file {path}")
                    elif os.path.isdir(path):
                        shutil.rmtree(path, ignore_errors=True)
                        logger.info(f"🕒 Delayed cleanup: Removed directory {path}")
            except Exception as e:
                logger.warning(f"🕒 Delayed cleanup failed for {path}: {e}")

        cleanup_thread = threading.Thread(target=delayed_cleanup, daemon=True)
        cleanup_thread.start()
        logger.info(f"🕒 Scheduled delayed cleanup for {path} in {delay_seconds}s")


@contextmanager
def managed_resources():
    """Context manager for automatic resource cleanup"""
    manager = ResourceManager()
    try:
        yield manager
    finally:
        manager.cleanup_all()


@asynccontextmanager
async def managed_temp_directory(prefix: Optional[str] = None) -> AsyncIterator[str]:
    """Async context manager for temporary directory with automatic cleanup"""
    import tempfile
    import uuid

    if prefix is None:
        prefix = video_config.temp_dir_prefix

    temp_dir = f"{prefix}{uuid.uuid4().hex}"
    os.makedirs(temp_dir, exist_ok=True)

    try:
        yield temp_dir
    finally:
        await _cleanup_temp_directory_async(temp_dir)


async def _cleanup_temp_directory_async(temp_dir: str):
    """Async cleanup for temporary directories with retries"""
    import asyncio
    import platform

    try:
        if not os.path.exists(temp_dir):
            return

        # Force garbage collection
        if video_config.gc_collection_enabled:
            gc.collect()
            await asyncio.sleep(video_config.file_handle_release_delay)

        # Windows-specific handling with retries
        if platform.system() == "Windows":
            for attempt in range(video_config.cleanup_retry_attempts):
                try:
                    shutil.rmtree(temp_dir)
                    logger.info(f"✅ Cleaned up temporary directory: {temp_dir}")
                    return
                except PermissionError as e:
                    if attempt < video_config.cleanup_retry_attempts - 1:
                        logger.warning(
                            f"⚠️ Temp directory cleanup attempt {attempt + 1} failed, retrying: {e}"
                        )
                        await asyncio.sleep(video_config.cleanup_retry_delay)
                        gc.collect()
                    else:
                        logger.warning(
                            f"❌ Failed to cleanup temp directory {temp_dir} after {video_config.cleanup_retry_attempts} attempts"
                        )
                        # Schedule delayed cleanup as fallback
                        ResourceManager()._schedule_delayed_cleanup(
                            temp_dir, delay_seconds=60.0
                        )
        else:
            # Non-Windows systems
            shutil.rmtree(temp_dir, ignore_errors=True)
            logger.info(f"✅ Cleaned up temporary directory: {temp_dir}")

    except Exception as e:
        logger.warning(f"❌ Failed to clean up temp directory {temp_dir}: {e}")


def cleanup_old_temp_directories(
    base_pattern: Optional[str] = None, max_age_hours: Optional[float] = None
):
    """Clean up old temporary directories"""
    if base_pattern is None:
        base_pattern = video_config.temp_dir_prefix
    if max_age_hours is None:
        max_age_hours = video_config.old_temp_cleanup_age_hours

    try:
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600

        for item in os.listdir("."):
            if os.path.isdir(item) and item.startswith(base_pattern):
                try:
                    dir_mtime = os.path.getmtime(item)
                    age_seconds = current_time - dir_mtime

                    if age_seconds > max_age_seconds:
                        logger.info(
                            f"🧹 Cleaning up old temp directory: {item} (age: {age_seconds/3600:.1f}h)"
                        )
                        shutil.rmtree(item, ignore_errors=True)
                        if not os.path.exists(item):
                            logger.info(
                                f"✅ Successfully removed old temp directory: {item}"
                            )
                        else:
                            ResourceManager()._schedule_delayed_cleanup(
                                item, delay_seconds=60.0
                            )
                except Exception as e:
                    logger.warning(f"Failed to process temp directory {item}: {e}")
    except Exception as e:
        logger.warning(f"Failed to cleanup old temp directories: {e}")


def close_moviepy_clips_globally():
    """Close all MoviePy clips in global namespace"""
    try:
        from moviepy.tools import close_all_clips

        close_all_clips(objects="globals", types=("audio", "video", "image"))
        logger.info("✅ Closed all clips using MoviePy's close_all_clips")
    except Exception as e:
        logger.warning(f"Failed to close clips globally: {e}")
