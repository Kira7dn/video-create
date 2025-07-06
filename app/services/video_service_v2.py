"""
Refactored video creation service with improved architecture
"""

import os
import uuid
import logging
import shutil
from typing import List, Dict, Any, Optional

from app.core.exceptions import VideoCreationError
from app.services.config.video_config import video_config
from app.services.resource_manager import (
    managed_resources,
    managed_temp_directory,
    cleanup_old_temp_directories,
)
from app.services.download_service import DownloadService
from app.services.video_processing_service import VideoProcessingService

logger = logging.getLogger(__name__)


class VideoCreationServiceV2:
    """
    Refactored video creation service with improved separation of concerns
    """

    def __init__(self):
        # Clean up old temporary directories on startup
        try:
            cleanup_old_temp_directories()
        except Exception as e:
            logger.warning(f"Failed to cleanup old temp directories on startup: {e}")

    async def create_video_from_json(self, json_data: Dict) -> str:
        """
        Create a video from JSON data with improved resource management
        """
        video_id = uuid.uuid4().hex

        # Use async context manager for temporary directory
        async with managed_temp_directory() as temp_dir:
            try:
                return await self._process_video_creation(json_data, temp_dir, video_id)
            except Exception as e:
                logger.error(f"Video creation failed: {e}", exc_info=True)
                raise VideoCreationError(f"Video creation failed: {e}") from e

    async def _process_video_creation(
        self, json_data: Dict, temp_dir: str, video_id: str
    ) -> str:
        """Internal method for video creation process"""
        # Phase 1: Download assets (segments + background_music riêng)
        async with DownloadService() as download_service:
            segment_results, background_music_result = await download_service.batch_download_segments(
                json_data, temp_dir
            )

        # Phase 2: Update segments with downloaded paths and process clips
        segments = json_data.get("segments", [])
        transitions = json_data.get("transitions", [])
        processed_segments = self._merge_segments_with_downloads(
            segments, segment_results
        )

        with managed_resources() as resource_manager:
            video_processor = VideoProcessingService(resource_manager)

            # Create individual segment clips and get file paths
            clip_paths = video_processor.create_multiple_segment_clips(
                processed_segments, temp_dir
            )
            # Phase 3: Concatenate clips với background_music
            output_path = os.path.join("data", "output", f"final_video_{video_id}.mp4")
            final_clip_path = video_processor.concatenate_clips(
                clip_paths, output_path, temp_dir=temp_dir, background_music=background_music_result, transitions=transitions
            )
            if os.path.exists(final_clip_path):
                logger.info(f"✅ Created video: {final_clip_path}")
                return final_clip_path
            else:
                raise VideoCreationError(f"Output video not found: {output_path}")

    def _merge_segments_with_downloads(
        self, original_segments: List[Dict], segment_results: List[Dict[str, dict]]
    ) -> List[Dict]:
        """Merge original segments with download results (không bao gồm background_music global)"""
        processed_segments = []

        for segment, download_result in zip(original_segments, segment_results):
            # Tạo bản sao segment gốc
            processed_segment = segment.copy()
            
            # Gộp từng asset object vào segment (image, video, voice_over, background_music segment-level)
            for asset_type, asset_obj in download_result.items():
                processed_segment[asset_type] = asset_obj

            processed_segments.append(processed_segment)

        return processed_segments


# Create service instance
video_service_v2 = VideoCreationServiceV2()
