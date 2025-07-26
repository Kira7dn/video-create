"""
Processor for downloading assets in the video creation pipeline.
"""

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, List

from app.core.exceptions import DownloadError
from app.services.processors.core.base_processor import AsyncProcessor
from app.config.settings import settings
from utils.download_utils import download_file

logger = logging.getLogger(__name__)


class DownloadProcessor(AsyncProcessor):
    """
    Processor for downloading assets required for video creation.

    Downloads all assets (images, videos, audio) specified in the context
    to the temporary directory.
    """

    async def process(self, input_data: Dict, **kwargs) -> List[Dict[str, str]]:
        """
        Download all assets to the temporary directory.

        Args:
            input_data: Dictionary containing 'segments' and 'background_music'

        Returns:
            List of dict for segments with local_path each segment (add background_music to context)

        Raises:
            DownloadError: If required parameters are missing or download fails
        """
        context = kwargs.get("context")
        if not context:
            raise DownloadError("Context is required for downloading assets")

        segments = input_data.get("segments")
        background_music = input_data.get("background_music")
        temp_dir = context.temp_dir

        if not isinstance(segments, list):
            raise DownloadError("Segments must be a list of dictionaries")
        if not segments:
            raise DownloadError("Segments list cannot be empty")

        # Prepare tasks for all downloads
        download_tasks = []
        results = []
        result_background_music = {}

        # Add segment downloads - Preserve original structure, add local_path to assets
        for i, segment in enumerate(segments):
            if not isinstance(segment, dict):
                raise DownloadError(
                    f"Segment must be a dictionary, got {type(segment)}"
                )

            segment_id = segment.get("id", f"segment_{i}")
            result_segment = segment.copy()
            result_background_music = background_music.copy()

            # Get supported segment asset types from settings
            asset_types = settings.segment_asset_types

            for asset_type, prefix in asset_types.items():
                if (
                    asset_type in segment
                    and isinstance(segment[asset_type], dict)
                    and segment[asset_type].get("url")
                ):
                    asset_data = segment[asset_type]
                    asset_url = asset_data["url"]

                    # Generate destination path - remove query parameters from URL
                    clean_url = asset_url.split('?')[0]  # Remove query parameters
                    dest_filename = f"{segment_id}_{prefix}_{Path(clean_url).name}"
                    dest_path = str(Path(temp_dir) / dest_filename)

                    # Add download task
                    download_tasks.append(
                        self._download_asset(
                            url=asset_url,
                            dest_path=dest_path,
                            asset_type=asset_type,
                            segment_id=segment_id,
                        )
                    )

                    # Add local_path to the original asset structure
                    result_segment[asset_type] = asset_data.copy()
                    result_segment[asset_type]["local_path"] = dest_path

            # Always add segment to results (preserve structure even if no assets)
            results.append(result_segment)

        # Handle background music if provided
        if background_music is not None:
            if not isinstance(background_music, dict) or "url" not in background_music:
                raise DownloadError("background_music must be an object with 'url' field")

            # Clean up the background music URL by removing query parameters
            bg_url = background_music['url'].split('?')[0]
            bg_dest_path = str(
                Path(temp_dir) / f"bg_music_{Path(bg_url).name}"
            )
            download_tasks.append(
                self._download_asset(
                    url=background_music["url"],
                    dest_path=bg_dest_path,
                    asset_type="background_music",
                    segment_id="bg_music",
                )
            )
            result_background_music = background_music.copy()
            result_background_music["local_path"] = bg_dest_path

            # Store background music info in context
            context.set("background_music", result_background_music)
        else:
            # If no background music, set it to None in the context
            context.set("background_music", None)

        # Execute all downloads concurrently
        download_results = await asyncio.gather(*download_tasks, return_exceptions=False)

        # Process results and collect errors
        failed_downloads = []
        for result in download_results:
            if isinstance(result, dict) and not result.get("success", True):
                failed_downloads.append(result)
            elif isinstance(result, Exception):
                failed_downloads.append({"error": str(result)})

        if failed_downloads:
            # Format error details
            error_details = []
            for error in failed_downloads[:5]:  # Limit to first 5 errors
                if isinstance(error, dict):
                    error_msg = error.get("error", "Unknown error")
                    asset_type = error.get("asset_type", "unknown")
                    segment_id = error.get("segment_id", "unknown")
                    url = error.get("url", "unknown")
                    error_details.append(f"{asset_type} for segment {segment_id} ({url}): {error_msg}")
                else:
                    error_details.append(str(error))
            
            error_message = f"Failed to download {len(failed_downloads)} assets. First few errors:\n"
            error_message += "\n".join(error_details)
            raise DownloadError(error_message)

        return results

    async def _download_asset(
        self, url: str, dest_path: str, asset_type: str, segment_id: str
    ) -> Dict[str, Any]:
        """Helper method to download a single asset"""
        try:
            if not url or not isinstance(url, str):
                raise ValueError(f"Invalid URL: {url}")
                
            file_path = await download_file(url, destination=dest_path, overwrite=True)
            
            if not file_path or not Path(file_path).exists():
                raise FileNotFoundError(f"Downloaded file not found at {file_path}")
                
            self.logger.debug(
                "Downloaded %s asset from %s to %s", asset_type, url, file_path
            )
            return {"success": True, "path": str(file_path)}

        except Exception as e:
            error_msg = f"Failed to download {asset_type} from {url}: {str(e)}"
            self.logger.error(error_msg, exc_info=True)

            if hasattr(self, "metrics_collector") and self.metrics_collector is not None:
                try:
                    await self.metrics_collector.increment_counter("asset_download_failed")
                except Exception as metrics_error:
                    self.logger.error(
                        "Failed to record metrics: %s", str(metrics_error), exc_info=True
                    )
                
            # Log additional context
            self.logger.warning(
                "Failed to download %s for segment %s: %s",
                asset_type,
                segment_id,
                str(e)[:100]
            )
            # Return a dict with error information instead of raising
            return {
                "success": False,
                "error": str(e),
                "asset_type": asset_type,
                "segment_id": segment_id,
                "url": url
            }
