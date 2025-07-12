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
from app.config.settings import settings

logger = logging.getLogger(__name__)


class ResourceManager:
    """Manages file resources and cleanup operations"""

    def __init__(self):
        self.tracked_files: List[str] = []

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
        self.cleanup_files()

        if settings.performance_gc_enabled:
            gc.collect()

    def _schedule_delayed_cleanup(
        self, path: str, delay_seconds: Optional[float] = None
    ):
        """Schedule delayed cleanup for a file or directory"""
        if delay_seconds is None:
            delay_seconds = settings.temp_delayed_cleanup_delay

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
        prefix = os.path.join("data", settings.temp_dir_prefix)

    temp_dir = f"{prefix}{uuid.uuid4().hex}"
    os.makedirs(temp_dir, exist_ok=True)

    try:
        yield temp_dir
    finally:
        await _cleanup_temp_directory_async(temp_dir)


async def _cleanup_temp_directory_async(temp_dir: str):
    """Async cleanup for temporary directories with retries"""
    import asyncio

    try:
        if not os.path.exists(temp_dir):
            return

        # Force garbage collection
        if settings.performance_gc_enabled:
            gc.collect()
            await asyncio.sleep(settings.performance_file_handle_delay)

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
        base_pattern = settings.temp_dir_prefix
    if max_age_hours is None:
        max_age_hours = settings.temp_cleanup_age_hours

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

