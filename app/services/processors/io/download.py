"""
Processor for downloading assets in the video creation pipeline.
"""

import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Tuple

import aiohttp

from app.core.exceptions import DownloadError
from app.services.download_service import DownloadService
from app.services.processors.core.base_processor import BaseProcessor

logger = logging.getLogger(__name__)


class DownloadProcessor(BaseProcessor):
    """
    Processor for downloading assets required for video creation.

    Downloads all assets (images, videos, audio) specified in the context
    to the temporary directory.
    """

    def __init__(self, metrics_collector=None):
        super().__init__(metrics_collector)
        self.download_service = DownloadService()

    async def _process_async(
        self, input_data: Dict, **kwargs
    ) -> Tuple[List[str], List[str]]:
        """
        Download all assets to the temporary directory.

        Args:
            input_data: Dictionary containing 'json_data' and 'temp_dir'

        Returns:
            Tuple of (downloaded_files, failed_downloads)

        Raises:
            DownloadError: If required parameters are missing or download fails
        """
        context = kwargs.get("context")
        if not context:
            raise DownloadError("Context is required for downloading assets")

        json_data = input_data.get("json_data")
        temp_dir = input_data.get("temp_dir")

        if not json_data or not temp_dir:
            raise DownloadError("json_data and temp_dir are required in input_data")

        # Create temp directory if it doesn't exist
        temp_path = Path(temp_dir)
        temp_path.mkdir(parents=True, exist_ok=True)

        # Extract assets from JSON data
        assets = self._extract_assets(json_data)

        # Download assets
        downloaded_files = []
        failed_downloads = []

        for asset_type, asset_url in assets:
            try:
                # Generate destination path
                dest_filename = f"{asset_type}_{Path(asset_url).name}"
                dest_path = str(temp_path / dest_filename)

                # Download using the download service
                file_path = await self.download_service.download(
                    asset_url, destination=dest_path, overwrite=True
                )

                downloaded_files.append(str(file_path))
                self.logger.info("Downloaded %s: %s", asset_type, file_path)

            except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as e:
                # More specific exception handling
                error_msg = f"Failed to download {asset_url}: {str(e)}"
                failed_downloads.append(asset_url)
                self.logger.error(error_msg)

                # Record failed download in metrics if available
                if hasattr(self, "metrics_collector"):
                    await self.metrics_collector.increment_counter(
                        "asset_download_failed",
                        tags={"asset_type": asset_type, "error": str(e)[:100]},
                    )

            except (ValueError, RuntimeError, asyncio.CancelledError) as e:
                # Catch other specific exceptions that might occur
                error_type = type(e).__name__
                error_msg = f"{error_type} while downloading {asset_url}: {str(e)}"
                failed_downloads.append(asset_url)
                self.logger.error(error_msg, exc_info=True)

                if hasattr(self, "metrics_collector"):
                    await self.metrics_collector.increment_counter(
                        "asset_download_error",
                        tags={
                            "asset_type": asset_type,
                            "error": error_type.lower(),
                            "source": "processor",
                        },
                    )

        # Update context
        context.downloaded_files = downloaded_files
        context.failed_downloads = failed_downloads

        # Record metrics
        if hasattr(self, "metrics_collector"):
            await self.metrics_collector.record_metric(
                "assets_downloaded", len(downloaded_files), tags={"status": "success"}
            )
            if failed_downloads:
                await self.metrics_collector.record_metric(
                    "assets_downloaded",
                    len(failed_downloads),
                    tags={"status": "failed"},
                )

        return downloaded_files, failed_downloads

    def _extract_assets(self, json_data: Dict) -> List[Tuple[str, str]]:
        """
        Extract asset URLs from JSON data.

        Args:
            json_data: The input JSON data

        Returns:
            List of tuples (asset_type, asset_url)
        """
        assets = []

        # Extract background images
        if "background" in json_data and "url" in json_data["background"]:
            assets.append(("background", json_data["background"]["url"]))

        # Extract overlay images
        if "overlays" in json_data:
            for overlay in json_data["overlays"]:
                if "url" in overlay:
                    assets.append(("overlay", overlay["url"]))

        # Extract audio tracks
        if "audio" in json_data:
            if (
                "background_music" in json_data["audio"]
                and "url" in json_data["audio"]["background_music"]
            ):
                assets.append(("audio", json_data["audio"]["background_music"]["url"]))
            if (
                "voice_over" in json_data["audio"]
                and "url" in json_data["audio"]["voice_over"]
            ):
                assets.append(("audio", json_data["audio"]["voice_over"]["url"]))

        return assets
