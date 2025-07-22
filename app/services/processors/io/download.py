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

        # Add segment downloads - Preserve original structure, add local_path to assets
        for i, segment in enumerate(segments):
            if not isinstance(segment, dict):
                raise DownloadError(f"Segment must be a dictionary, got {type(segment)}")
            
            segment_id = segment.get("id", f"segment_{i}")
            result_segment = segment.copy()

            # Get supported segment asset types from settings
            asset_types = settings.segment_asset_types

            for asset_type, prefix in asset_types.items():
                if asset_type in segment and isinstance(segment[asset_type], dict) and segment[asset_type].get("url"):
                    asset_data = segment[asset_type]
                    asset_url = asset_data["url"]

                    # Generate destination path
                    dest_filename = f"{segment_id}_{prefix}_{Path(asset_url).name}"
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

        # Add background music download
        if not isinstance(background_music, dict) or "url" not in background_music:
            raise DownloadError("background_music must be an object with 'url' field")

        bg_dest_path = str(
            Path(temp_dir) / f"bg_music_{Path(background_music['url']).name}"
        )
        download_tasks.append(
            self._download_asset(
                url=background_music["url"],
                dest_path=bg_dest_path,
                asset_type="background_music",
                segment_id="bg_music",
            )
        )

        # Store background music info in context
        context.background_music = {
            "url": background_music["url"],
            "local_path": bg_dest_path,
            "volume": background_music.get("volume", 0.2),
            "start_delay": background_music.get("start_delay", 0),
            "end_delay": background_music.get("end_delay", 0),
            "fade_in": background_music.get("fade_in", 0.0),
            "fade_out": background_music.get("fade_out", 0.0),
        }

        # Execute all downloads concurrently
        download_results = await asyncio.gather(*download_tasks, return_exceptions=True)

        # Check for any failed downloads
        failed_downloads = [
            r
            for r in download_results
            if isinstance(r, Exception)
            or (isinstance(r, dict) and not r.get("success"))
        ]

        if failed_downloads:
            error_details = "\n".join(
                str(error) for error in failed_downloads[:5]  # Limit error details
            )
            raise DownloadError(
                f"Failed to download {len(failed_downloads)} assets. First few errors:\n{error_details}"
            )

        return results

    async def _download_asset(
        self, url: str, dest_path: str, asset_type: str, segment_id: str
    ) -> Dict[str, Any]:
        """Helper method to download a single asset"""
        try:
            file_path = await download_file(url, destination=dest_path, overwrite=True)
            self.logger.debug(
                "Downloaded %s asset from %s to %s", asset_type, url, file_path
            )
            return {"success": True, "path": str(file_path)}

        except Exception as e:
            error_msg = f"Failed to download {asset_type} from {url}: {str(e)}"
            self.logger.error(error_msg, exc_info=True)

            if hasattr(self, "metrics_collector"):
                await self.metrics_collector.increment_counter(
                    "asset_download_failed",
                    tags={
                        "asset_type": asset_type,
                        "error": str(e)[:100],
                        "segment_id": segment_id,
                    },
                )
            raise
