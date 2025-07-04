"""
Download service for handling file downloads
"""

import os
import uuid
import logging
import asyncio
import aiohttp
import aiofiles
from typing import List, Dict, Optional, Tuple
from urllib.parse import urlparse
from dataclasses import dataclass

from app.core.exceptions import VideoCreationError
from app.services.config.video_config import video_config

logger = logging.getLogger(__name__)


@dataclass
class DownloadTask:
    """Represents a single download task"""

    url: str
    dest_path: str
    segment_id: str
    asset_type: str  # 'image','video','background_music', 'voice_over'


@dataclass
class DownloadResult:
    """Result of a download operation"""

    success: bool
    local_path: Optional[str] = None
    error: Optional[str] = None


class DownloadService:
    """Service for handling file downloads"""

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Async context manager entry"""
        timeout = aiohttp.ClientTimeout(total=video_config.download_timeout)
        self.session = aiohttp.ClientSession(timeout=timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()

    async def download_file(self, url: str, dest_path: str) -> DownloadResult:
        """Download a single file"""
        try:
            if not self.session:
                raise VideoCreationError("DownloadService not properly initialized")

            async with self.session.get(url) as response:
                response.raise_for_status()

                # Create directory if it doesn't exist
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)

                async with aiofiles.open(dest_path, "wb") as f:
                    await f.write(await response.read())

                logger.debug(f"✅ Downloaded {url} to {dest_path}")
                return DownloadResult(success=True, local_path=dest_path)

        except aiohttp.ClientError as e:
            error_msg = f"Failed to download {url}: {e}"
            logger.error(error_msg)
            return DownloadResult(success=False, error=error_msg)
        except Exception as e:
            error_msg = f"Unexpected error downloading {url}: {e}"
            logger.error(error_msg)
            return DownloadResult(success=False, error=error_msg)

    def _generate_download_path(self, url: str, temp_dir: str, asset_type: str) -> str:
        """Generate a local path for downloaded file"""
        parsed_url = urlparse(url)
        ext = os.path.splitext(parsed_url.path)[1] or ".tmp"
        filename = f"{asset_type}_{uuid.uuid4().hex}{ext}"
        return os.path.join(temp_dir, filename)

    def _extract_download_tasks(
        self, segment: dict, temp_dir: str, segment_id: str
    ) -> List[DownloadTask]:
        """Extract download tasks from a segment (trực tiếp lấy .get('url'))"""
        tasks = []

        # Background image
        bg_image_url = segment.get("image", {}).get("url")
        if bg_image_url:
            dest_path = self._generate_download_path(bg_image_url, temp_dir, "bg_image")
            tasks.append(
                DownloadTask(bg_image_url, dest_path, segment_id, "image")
            )
        # Background video
        bg_video_url = segment.get("video", {}).get("url")
        if bg_video_url:
            dest_path = self._generate_download_path(bg_video_url, temp_dir, "video")
            tasks.append(
                DownloadTask(bg_video_url, dest_path, segment_id, "video")
            )
        # Background music
        bg_music_url = segment.get("background_music", {}).get("url")
        if bg_music_url:
            dest_path = self._generate_download_path(bg_music_url, temp_dir, "bg_music")
            tasks.append(
                DownloadTask(bg_music_url, dest_path, segment_id, "background_music")
            )
        # Voice over
        voice_over_url = segment.get("voice_over", {}).get("url")
        if voice_over_url:
            dest_path = self._generate_download_path(
                voice_over_url, temp_dir, "voice_over"
            )
            tasks.append(
                DownloadTask(voice_over_url, dest_path, segment_id, "voice_over")
            )

        return tasks

    async def download_segment_assets(
        self, segment: dict, temp_dir: str
    ) -> Dict[str, dict]:
        """Download all assets for a segment and return asset objects with local_path, url, start_delay, end_delay (nếu có)"""
        segment_id = segment.get("id", str(uuid.uuid4()))
        download_tasks = self._extract_download_tasks(segment, temp_dir, segment_id)

        if not download_tasks:
            return {}

        # Execute downloads concurrently
        results = await asyncio.gather(
            *[self.download_file(task.url, task.dest_path) for task in download_tasks],
            return_exceptions=False,
        )

        asset_result = {}
        for task, result in zip(download_tasks, results):
            if not result.success:
                logger.error(f"Download failed for {task.asset_type}: {result.error}")
                raise VideoCreationError(
                    f"Failed to download {task.asset_type}: {result.error}"
                )
            # Copy object gốc, chỉ bổ sung local_path
            asset_obj = segment.get(task.asset_type, {})
            asset_info = dict(asset_obj) if isinstance(asset_obj, dict) else {}
            asset_info["url"] = task.url  # Đảm bảo luôn có url
            asset_info["local_path"] = result.local_path
            asset_result[task.asset_type] = asset_info

        return asset_result

    async def batch_download_segments(
        self, segments: List[dict], temp_dir: str
    ) -> List[Dict[str, str]]:
        """Download assets for multiple segments concurrently"""
        download_tasks = []

        for segment in segments:
            download_tasks.append(self.download_segment_assets(segment, temp_dir))

        # Limit concurrent downloads to prevent overwhelming the server
        semaphore = asyncio.Semaphore(video_config.max_concurrent_downloads)

        async def bounded_download(task):
            async with semaphore:
                return await task

        results = await asyncio.gather(
            *[bounded_download(task) for task in download_tasks]
        )

        return results
