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
from utils.video_utils import export_final_video_clip

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

    async def create_video_from_json(self, json_data: List[Dict]) -> str:
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
        self, json_data: List[Dict], temp_dir: str, video_id: str
    ) -> str:
        """Internal method for video creation process"""

        # Phase 1: Download assets
        async with DownloadService() as download_service:
            download_results = await download_service.batch_download_segments(
                json_data, temp_dir
            )

        # Phase 2: Update segments with downloaded paths and process clips
        processed_segments = self._merge_segments_with_downloads(
            json_data, download_results
        )

        with managed_resources() as resource_manager:
            video_processor = VideoProcessingService(resource_manager)

            # Create individual segment clips
            segment_clips = video_processor.create_multiple_segment_clips(
                processed_segments, temp_dir
            )

            # Extract clip paths and transitions
            clip_paths: List[str] = [
                clip.filename
                for clip in segment_clips
                if hasattr(clip, "filename") and clip.filename is not None
            ]
            transitions = [seg.get("transition") for seg in processed_segments]

            # Phase 3: Concatenate clips
            final_clip = video_processor.concatenate_clips_with_transitions(
                clip_paths, transitions
            )

            # Phase 4: Export final video
            output_path = os.path.join(temp_dir, f"final_video_{video_id}.mp4")
            export_final_video_clip(final_clip, output_path)

            # Copy to final output location
            final_output_path = f"final_video_{video_id}.mp4"
            if os.path.exists(output_path):
                shutil.copy2(output_path, final_output_path)
                logger.info(f"✅ Created video: {final_output_path}")
                return final_output_path
            else:
                raise VideoCreationError(f"Output video not found: {output_path}")

    def cleanup_temp_directory(self, temp_dir: str):
        """Clean up temporary directory - compatibility method for API"""
        try:
            if not os.path.exists(temp_dir):
                logger.info(f"⚠️ Temp directory not found for cleanup: {temp_dir}")
                return

            # Force garbage collection to release file handles
            import gc

            gc.collect()
            # Non-Windows systems
            shutil.rmtree(temp_dir, ignore_errors=True)
            logger.info(f"✅ Cleaned up temporary directory: {temp_dir}")

        except Exception as e:
            logger.warning(f"❌ Failed to clean up temp directory {temp_dir}: {e}")

    def _merge_segments_with_downloads(
        self, original_segments: List[Dict], download_results: List[Dict[str, str]]
    ) -> List[Dict]:
        """Merge original segments with download results"""
        processed_segments = []

        for segment, download_result in zip(original_segments, download_results):
            # Create a copy of the original segment
            processed_segment = segment.copy()

            # Add download paths
            processed_segment.update(download_result)

            # Determine duration if not already set
            if "duration" not in processed_segment:
                if voice_over_path := processed_segment.get("voice_over_path"):
                    try:
                        from moviepy import AudioFileClip

                        with AudioFileClip(voice_over_path) as voice_clip:
                            processed_segment["duration"] = voice_clip.duration
                        logger.info(
                            f"Set segment duration from voice_over: {processed_segment['duration']:.2f}s"
                        )
                    except Exception as e:
                        logger.warning(f"Failed to get duration from voice_over: {e}")
                        processed_segment["duration"] = (
                            video_config.default_segment_duration
                        )
                else:
                    processed_segment["duration"] = (
                        video_config.default_segment_duration
                    )
                    logger.info("No voice_over found, using default segment duration")

            processed_segments.append(processed_segment)

        return processed_segments


# Create service instance
video_service_v2 = VideoCreationServiceV2()
