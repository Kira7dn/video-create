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

    async def process_batch_video_creation(
        self,
        data_array: List[Dict[Any, Any]],
        transitions: Optional[Any] = None,
        tmp_dir: str = "tmp_pipeline",
        batch_uuid: Optional[str] = None,
    ) -> tuple[str, List[Dict[str, Any]]]:
        """Process batch video creation with improved error handling"""

        os.makedirs(tmp_dir, exist_ok=True)
        cut_results = []

        try:
            # Phase 1: Download assets
            async with DownloadService() as download_service:
                download_results = await download_service.batch_download_segments(
                    data_array, tmp_dir
                )

            # Phase 2: Process segments
            processed_segments = self._merge_segments_with_downloads(
                data_array, download_results
            )

            with managed_resources() as resource_manager:
                video_processor = VideoProcessingService(resource_manager)

                # Create individual clips and track results
                segment_clips = []
                clip_paths = []

                for idx, segment in enumerate(processed_segments):
                    cut_id = segment.get("id", f"cut{idx+1}")
                    try:
                        clip = video_processor.create_segment_clip(segment, tmp_dir)
                        segment_clips.append(clip)
                        clip_paths.append(
                            clip.filename if hasattr(clip, "filename") else None
                        )

                        cut_results.append(
                            {
                                "id": cut_id,
                                "status": "success",
                                "video_path": (
                                    clip.filename if hasattr(clip, "filename") else None
                                ),
                                "error": None,
                            }
                        )
                    except Exception as e:
                        cut_results.append(
                            {
                                "id": cut_id,
                                "status": "error",
                                "video_path": None,
                                "error": str(e),
                            }
                        )
                        logger.error(f"Failed to create segment {cut_id}: {e}")

                # Filter out failed clips
                clip_paths = [p for p in clip_paths if p is not None]

                if not clip_paths:
                    raise VideoCreationError(
                        "No successful clips created for batch processing"
                    )

                # Phase 3: Concatenate clips
                if transitions is None:
                    transitions = [
                        obj.get("transition")
                        for obj in data_array
                        if "transition" in obj
                    ]

                final_clip = video_processor.concatenate_clips_with_transitions(
                    clip_paths, transitions
                )

                # Phase 4: Export final batch video
                output_filename = (
                    f"final_batch_video_{batch_uuid or uuid.uuid4().hex}.mp4"
                )
                output_path = os.path.join(tmp_dir, output_filename)

                export_final_video_clip(final_clip, output_path)

                if not os.path.exists(output_path):
                    raise VideoCreationError(
                        f"Batch output file not found: {output_path}"
                    )

                # Copy to final location
                final_output_path = output_filename
                shutil.copy2(output_path, final_output_path)
                logger.info(f"✅ Created batch video: {final_output_path}")

                return final_output_path, cut_results

        except Exception as e:
            logger.error(f"Batch video creation failed: {e}", exc_info=True)
            raise VideoCreationError(f"Batch video creation failed: {e}") from e
        finally:
            # Cleanup temp directory using the resource manager's cleanup
            try:
                if os.path.exists(tmp_dir):
                    shutil.rmtree(tmp_dir, ignore_errors=True)
                    logger.info(f"✅ Cleaned up batch temp directory: {tmp_dir}")
            except Exception as cleanup_error:
                logger.warning(
                    f"Failed to cleanup batch temp directory: {cleanup_error}"
                )

    def cleanup_temp_directory(self, temp_dir: str):
        """Clean up temporary directory - compatibility method for API"""
        import platform

        try:
            if not os.path.exists(temp_dir):
                logger.info(f"⚠️ Temp directory not found for cleanup: {temp_dir}")
                return

            # Force garbage collection to release file handles
            import gc

            gc.collect()

            # Windows-specific handling with retries
            if platform.system() == "Windows":
                cleanup_attempts = 3
                for attempt in range(cleanup_attempts):
                    try:
                        shutil.rmtree(temp_dir)
                        logger.info(f"✅ Cleaned up temporary directory: {temp_dir}")
                        return
                    except PermissionError as e:
                        if attempt < cleanup_attempts - 1:
                            logger.warning(
                                f"⚠️ Temp directory cleanup attempt {attempt + 1} failed, retrying in 2s: {e}"
                            )
                            import time

                            time.sleep(2.0)
                            gc.collect()
                        else:
                            logger.warning(
                                f"❌ Failed to cleanup temp directory {temp_dir} after {cleanup_attempts} attempts: {e}"
                            )
                    except Exception as e:
                        logger.warning(f"❌ Cleanup failed for {temp_dir}: {e}")
                        break
            else:
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
