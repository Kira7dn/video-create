"""
Download service for handling file downloads
"""

import asyncio
import logging
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.parse import urlparse

import aiofiles
import aiohttp

from app.core.exceptions import VideoCreationError
from app.interfaces import IDownloader
from app.config.settings import settings

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


class DownloadService(IDownloader):
    """Service for handling file downloads"""

    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
        self._session_lock = asyncio.Lock()

    @property
    async def session(self) -> aiohttp.ClientSession:
        """Lazy initialization of the aiohttp session"""
        async with self._session_lock:
            if self._session is None or self._session.closed:  # Double-checked locking
                timeout = aiohttp.ClientTimeout(total=settings.download_timeout)
                self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self):
        """Close the underlying session"""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()

    async def download(self, url: str, destination: Union[str, Path], **kwargs) -> str:
        """Download a resource from URL to destination

        Args:
            url: Source URL to download from
            destination: Local path or directory to save the downloaded file
            **kwargs: Additional download options
                - overwrite: bool - Whether to overwrite existing file (default: False)

        Returns:
            Path to the downloaded file

        Raises:
            VideoCreationError: If download fails
        """
        # If destination is a directory, generate a filename
        if os.path.isdir(str(destination)):
            filename = (
                os.path.basename(urlparse(url).path) or f"download_{uuid.uuid4().hex}"
            )
            dest_path = os.path.join(str(destination), filename)
        else:
            dest_path = str(destination)

        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)

        # Check if file exists and overwrite is False
        if not kwargs.get("overwrite", False) and os.path.exists(dest_path):
            logger.debug("File already exists, skipping download: %s", dest_path)
            return dest_path

        result = await self.download_file(url, dest_path)
        if not result.success:
            raise VideoCreationError(f"Failed to download {url}: {result.error}")
        return dest_path

    async def batch_download(
        self, resources: List[Dict[str, Any]], destination_dir: Union[str, Path]
    ) -> List[Dict[str, Any]]:
        """Download multiple resources in batch

        Args:
            resources: List of resource dictionaries containing at least 'url' key
            destination_dir: Directory to save downloaded files

        Returns:
            List of download results with status and file paths
        """
        destination_dir = Path(destination_dir)
        os.makedirs(destination_dir, exist_ok=True)

        results = []
        for resource in resources:
            try:
                url = resource.get("url")
                if not url:
                    raise ValueError("Resource missing 'url' key")

                dest_path = await self.download(
                    url=url, destination=destination_dir, **resource.get("options", {})
                )

                results.append(
                    {
                        "success": True,
                        "url": url,
                        "local_path": str(dest_path),
                        "resource": resource,
                    }
                )

            except (aiohttp.ClientError, OSError, IOError, ValueError) as e:
                logger.error("Failed to download %s: %s", resource.get("url"), str(e))
                results.append(
                    {
                        "success": False,
                        "url": resource.get("url"),
                        "error": str(e),
                        "resource": resource,
                    }
                )

        return results

    async def download_file(self, url: str, dest_path: str) -> DownloadResult:
        """Download a single file"""
        try:
            session = await self.session
            async with session.get(url) as response:
                response.raise_for_status()

                # Create directory if it doesn't exist
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)

                # Stream large files to avoid memory issues
                async with aiofiles.open(dest_path, "wb") as f:
                    async for chunk in response.content.iter_chunked(8192):
                        await f.write(chunk)

                logger.debug("✅ Downloaded %s to %s", url, dest_path)
                return DownloadResult(success=True, local_path=dest_path)

        except aiohttp.ClientError as e:
            logger.error("Failed to download %s: %s", url, str(e))
            return DownloadResult(success=False, error=f"Failed to download {url}: {e}")
        except (OSError, IOError) as e:
            logger.error("File operation error downloading %s: %s", url, str(e))
            return DownloadResult(
                success=False, error=f"File operation error downloading {url}: {e}"
            )

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
            tasks.append(DownloadTask(bg_image_url, dest_path, segment_id, "image"))
        # Background video
        bg_video_url = segment.get("video", {}).get("url")
        if bg_video_url:
            dest_path = self._generate_download_path(bg_video_url, temp_dir, "video")
            tasks.append(DownloadTask(bg_video_url, dest_path, segment_id, "video"))
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
        """Download all assets for a segment and
        return asset objects with local_path,
        url, start_delay, end_delay (nếu có)"""
        segment_id = segment.get("id")
        if not segment_id:
            raise VideoCreationError(
                "Segment missing 'id' field. Please provide a unique id for each segment."
            )
        download_tasks = self._extract_download_tasks(segment, temp_dir, segment_id)

        if not download_tasks:
            return {}

        # Execute downloads concurrently
        results = await asyncio.gather(
            *[self.download_file(task.url, task.dest_path) for task in download_tasks],
            return_exceptions=False,
        )

        asset_result = dict(segment)  # Trả về copy của segment gốc
        for task, result in zip(download_tasks, results):
            if not result.success:
                # Nếu là image thì chỉ warning, không throw error
                if task.asset_type == "image":
                    logger.warning(
                        "Download failed for %s: %s (will be replaced in next step)",
                        task.asset_type,
                        result.error,
                    )
                    continue
                else:
                    logger.error(
                        "Download failed for %s: %s", task.asset_type, result.error
                    )
                    raise VideoCreationError(
                        f"Failed to download {task.asset_type}: {result.error}"
                    )
            asset_info = asset_result.get(task.asset_type, {})
            if isinstance(asset_info, dict):
                asset_info["local_path"] = (
                    result.local_path
                )  # Chỉ chèn local_path vào dict gốc
        return asset_result

    async def batch_download_segments(
        self, json_data: dict, temp_dir: str
    ) -> Tuple[List[Dict[str, dict]], Optional[Dict[str, dict]]]:
        """Download assets for multiple segments and background music separately"""
        segments = json_data.get("segments", [])
        background_music = json_data.get("background_music", {})

        # Download segment assets
        segment_tasks = [
            self.download_segment_assets(segment, temp_dir) for segment in segments
        ]

        # Download background music riêng (nếu có)
        background_music_result = None
        if background_music.get("url"):
            # Tạo fake segment chứa background_music
            fake_segment = {
                "id": "global_background_music",
                "background_music": background_music,
            }
            bg_music_download = await self.download_segment_assets(
                fake_segment, temp_dir
            )
            background_music_result = bg_music_download.get("background_music")

        # Limit concurrent downloads to prevent overwhelming the server
        semaphore = asyncio.Semaphore(settings.download_max_concurrent)

        async def bounded_download(task):
            async with semaphore:
                return await task

        segment_results = await asyncio.gather(
            *[bounded_download(task) for task in segment_tasks]
        )

        return segment_results, background_music_result
