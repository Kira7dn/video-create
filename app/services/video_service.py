"""
Refactored video creation service with improved architecture
"""

import os
import uuid
import logging
import time
from typing import List, Dict, Optional
from pathlib import Path
import asyncio

from app.core.exceptions import VideoCreationError, DownloadError, ProcessingError
from app.config.settings import settings
from app.services.resource_manager import (
    managed_temp_directory,
    cleanup_old_temp_directories,
)
from app.services.interfaces import IDownloader
from app.services.download_service import DownloadService
from app.services.processors.s3_upload_processor import S3UploadProcessor

# Import new processors
from app.services.processors.base_processor import MetricsCollector
from app.services.processors.validation_processor import create_video_request_validator
from app.services.interfaces import IVideoProcessor
from app.services.processors.pipeline import VideoPipeline, PipelineContext
from app.services.processors.pydantic_ai_validator import PydanticAIValidator
from app.services.processors.image_auto_processor import ImageAutoProcessor
from app.services.processors.transcript_processor import TranscriptProcessor
from app.services.video_processing_service import VideoProcessingService

logger = logging.getLogger(__name__)


class VideoCreationService:
    """
    Coordinates the video creation process using a pipeline architecture.

    This service orchestrates the video creation process by coordinating between
    different processors and services. It uses dependency injection for the
    video processor to allow for easier testing and flexibility.

    Args:
        video_processor: An implementation of IVideoProcessor to handle video processing.
                        If not provided, a default VideoProcessingService will be used.
    """

    def __init__(
        self,
        video_processor: Optional[IVideoProcessor] = None,
        downloader: Optional[IDownloader] = None,
    ):
        self.metrics_collector = MetricsCollector()
        self.validator = create_video_request_validator(self.metrics_collector)

        # Initialize with dependency injection
        if video_processor is None:
            # Initialize VideoProcessingService with default processors
            self.video_processor = VideoProcessingService()
        else:
            self.video_processor = video_processor

        self.downloader = downloader or DownloadService()
        self._ensure_output_directory()
        self._cleanup_old_directories()

    def _ensure_output_directory(self):
        """Ensure output directory exists"""
        output_dir = Path(settings.output_directory)
        output_dir.mkdir(parents=True, exist_ok=True)

    def _cleanup_old_directories(self):
        """Clean up old temporary directories on startup"""
        try:
            cleanup_old_temp_directories()
        except (OSError, PermissionError) as e:
            logger.warning(
                "Failed to cleanup old temp directories on startup: %s",
                e,
                exc_info=True,
            )
        except Exception as e:
            logger.error(
                "Unexpected error during temp directory cleanup: %s", e, exc_info=True
            )
            # Vẫn ném lại exception để không che giấu lỗi nghiêm trọng
            raise

    async def create_video_from_json(self, json_data: Dict) -> Dict:
        """
        Create a video from JSON data with improved resource management and pipeline processing
        """
        # Reset metrics for new request
        self.metrics_collector = MetricsCollector()

        # Validate input data first - note: validate() is synchronous
        validation_result = self.validator.validate(json_data)
        if not validation_result.is_valid:
            error_msg = f"Validation failed: {'; '.join(validation_result.errors)}"
            logger.error(error_msg)
            raise VideoCreationError(error_msg)

        video_id = uuid.uuid4().hex

        # Use async context manager for temporary directory
        async with managed_temp_directory() as temp_dir:
            try:
                return await self._process_video_creation_pipeline(
                    json_data, temp_dir, video_id
                )
            except DownloadError as e:
                logger.error("Asset download failed: %s", e, exc_info=True)
                raise VideoCreationError(f"Asset download failed: {e}") from e
            except ProcessingError as e:
                logger.error("Video processing failed: %s", e, exc_info=True)
                raise VideoCreationError(f"Video processing failed: {e}") from e
            except Exception as e:
                logger.error("Unexpected error in video creation: %s", e, exc_info=True)
                raise VideoCreationError(f"Video creation failed: {e}") from e
            finally:
                # Log processing summary
                self._log_processing_summary()

    def _log_processing_summary(self):
        """Log processing metrics summary"""
        try:
            summary = self.metrics_collector.get_summary()
            logger.info("🎬 Video Creation Summary:")
            logger.info("   Total Duration: %s", summary["total_duration"])
            logger.info("   Total Items Processed: %s", summary["total_items"])

            if summary["failed_stages"]:
                logger.warning(
                    "   Failed Stages: %s", ", ".join(summary["failed_stages"])
                )

            for stage in summary["stages"]:
                status_emoji = "✅" if stage["success"] else "❌"
                logger.info(
                    "   %s %s: %s (%s items)",
                    status_emoji,
                    stage["stage"],
                    stage["duration"],
                    stage["items_processed"],
                )
        except (KeyError, AttributeError, TypeError, ValueError) as e:
            logger.warning(
                "Failed to log processing summary due to data issue: %s",
                e,
                exc_info=True,
            )
        except Exception as e:
            logger.error(
                "Unexpected error in log processing summary: %s", e, exc_info=True
            )
            # Không bắt lại exception ở đây để cho phép lỗi nghiêm trọng được bắt ở tầng cao hơn
            raise

    async def _process_video_creation_pipeline(
        self, json_data: Dict, temp_dir: str, video_id: str
    ) -> Dict:
        """Process video creation using pipeline pattern"""
        # Create pipeline context
        context_data = {
            "json_data": json_data,
            "segments": json_data.get("segments", []),
            "transitions": json_data.get("transitions", []),
            "background_music": json_data.get("background_music"),
            "keywords": json_data.get("keywords", []),  # Add keywords to context
        }
        context = PipelineContext(
            data=context_data,
            temp_dir=temp_dir,
            video_id=video_id,
            metadata={"start_time": time.time()},
        )

        # Build and execute pipeline
        pipeline = self._build_video_pipeline()
        result_context = await pipeline.execute(context)

        # Return final video path & S3 URL
        final_video_path = result_context.get("final_video_path")
        s3_url = result_context.get("s3_upload_result")
        if not final_video_path or not os.path.exists(final_video_path):
            raise VideoCreationError("Final video was not created successfully")
        if not s3_url:
            raise VideoCreationError("S3 upload failed or S3 URL not found")
        return {"video_path": final_video_path, "s3_url": s3_url}

    def _build_video_pipeline(self) -> VideoPipeline:
        """Build the video processing pipeline"""
        pipeline = VideoPipeline(self.metrics_collector)

        # Stage 1: AI schema validation stage
        pipeline.add_processor_stage(
            name="ai_schema_validation",
            processor=PydanticAIValidator(),
            input_key="json_data",
            output_key="json_data",
        )

        # Stage 2: Download assets
        pipeline.add_function_stage(
            name="download_assets",
            func=self._download_assets_stage,
            output_key="download_results",
            required_inputs=["json_data"],
        )

        # Stage 3: Image auto processing
        pipeline.add_processor_stage(
            name="image_auto",
            processor=ImageAutoProcessor(),
            input_key="download_results",
            output_key="processed_segments",
        )

        # Stage 4: Text overlay alignment
        pipeline.add_processor_stage(
            name="text_overlay_alignment",
            processor=TranscriptProcessor(),
            input_key="processed_segments",
            output_key="processed_segments",
            required_inputs=["processed_segments"],
        )

        # Stage 5: Create segment clips
        pipeline.add_function_stage(
            name="create_segment_clips",
            func=self._create_segment_clips_stage,
            output_key="clip_paths",
            required_inputs=["processed_segments"],
        )

        # Stage 6: Concatenate final video
        pipeline.add_function_stage(
            name="concatenate_video",
            func=self._concatenate_video_stage,
            output_key="final_video_path",
            required_inputs=["clip_paths", "transitions", "background_music"],
        )

        # Stage 7: Upload final video to S3

        pipeline.add_processor_stage(
            name="s3_upload",
            processor=S3UploadProcessor(metrics_collector=self.metrics_collector),
            input_key="final_video_path",
            output_key="s3_upload_result",
        )

        return pipeline

    async def _download_assets_stage(self, context: PipelineContext) -> tuple:
        """Pipeline stage for downloading assets

        Args:
            context: The pipeline context containing JSON data and temp directory

        Returns:
            tuple: (segment_results, background_music_result)
                - segment_results: List of segments with downloaded assets (maintains original segment structure)
                - background_music_result: Global background music info if available

        Raises:
            DownloadError: If there's an error downloading assets
        """
        json_data = context.get("json_data")
        try:
            # Initialize resources list for batch download
            resources = []

            # Keep track of which segments have assets
            segment_assets = {}

            # Process each segment to collect download resources
            for segment in json_data.get("segments", []):
                segment_id = segment.get("id", str(len(segment_assets)))
                segment_assets[segment_id] = {
                    "segment": segment.copy(),  # Preserve original segment data
                    "assets": [],
                }

                # Add background image
                if "image" in segment and "url" in segment["image"]:
                    resources.append(
                        {
                            "url": segment["image"]["url"],
                            "options": {
                                "asset_type": "image",
                                "segment_id": segment_id,
                            },
                        }
                    )

                # Add background video
                if "video" in segment and "url" in segment["video"]:
                    resources.append(
                        {
                            "url": segment["video"]["url"],
                            "options": {
                                "asset_type": "video",
                                "segment_id": segment_id,
                            },
                        }
                    )

                # Add background music
                if (
                    "background_music" in segment
                    and "url" in segment["background_music"]
                ):
                    resources.append(
                        {
                            "url": segment["background_music"]["url"],
                            "options": {
                                "asset_type": "background_music",
                                "segment_id": segment_id,
                                "is_segment_music": True,  # Mark as segment-specific music
                            },
                        }
                    )

                # Add voice over
                if "voice_over" in segment and "url" in segment["voice_over"]:
                    resources.append(
                        {
                            "url": segment["voice_over"]["url"],
                            "options": {
                                "asset_type": "voice_over",
                                "segment_id": segment_id,
                            },
                        }
                    )

            # Add global background music if present
            if (
                "background_music" in json_data
                and "url" in json_data["background_music"]
            ):
                resources.append(
                    {
                        "url": json_data["background_music"]["url"],
                        "options": {
                            "asset_type": "background_music",
                            "is_global": True,
                        },
                    }
                )

            # Download all resources
            download_results = await self.downloader.batch_download(
                resources=resources, destination_dir=context.temp_dir
            )

            # Process download results
            background_music_result = None

            # First, update the segment assets with download results
            for result in download_results:
                if not result["success"]:
                    logger.warning(
                        "Failed to download asset: %s - %s",
                        result.get("url"),
                        result.get("error", "Unknown error"),
                    )
                    continue

                resource = result.get("resource", {})
                options = resource.get("options", {})
                asset_type = options.get("asset_type")
                segment_id = options.get("segment_id")
                is_global = options.get("is_global", False)
                is_segment_music = options.get("is_segment_music", False)

                # Handle global background music
                if asset_type == "background_music" and is_global:
                    background_music_result = {
                        "url": resource["url"],
                        "local_path": result["local_path"],
                    }
                # Handle segment assets
                elif segment_id in segment_assets:
                    asset_info = {
                        "url": resource["url"],
                        "local_path": result["local_path"],
                    }

                    # Special handling for segment background music
                    if asset_type == "background_music" and is_segment_music:
                        segment_assets[segment_id]["segment"][
                            "background_music"
                        ] = asset_info
                    else:
                        segment_assets[segment_id]["segment"][asset_type] = asset_info

            # Build the final segment results list, maintaining original order
            segment_results = [
                data["segment"]
                for _, data in sorted(
                    segment_assets.items(),
                    key=lambda x: int(x[0]) if x[0].isdigit() else float("inf"),
                )
            ]

            return segment_results, background_music_result

        except Exception as e:
            logger.error("Error in _download_assets_stage: %s", str(e), exc_info=True)
            raise DownloadError(f"Failed to download assets: {e}") from e

    async def _create_segment_clips_stage(
        self, context: PipelineContext
    ) -> List[Dict[str, str]]:
        """Pipeline stage for creating individual segment clips

        Args:
            context: The pipeline context containing segments to process

        Returns:
            List[Dict[str, str]]: List of dictionaries containing clip information

        Raises:
            ProcessingError: If no segments are found or processing fails
        """
        processed_segments = context.get("processed_segments")
        if not processed_segments:
            raise ProcessingError("No segments found to process")

        clip_paths = []
        for segment in processed_segments:
            try:
                # Use the video_processor to process the segment
                # create_segment_clip returns the path directly as a string
                clip_path = await self.video_processor.create_segment_clip(
                    segment=segment, temp_dir=context.temp_dir
                )
                clip_info = {
                    "id": segment.get("id", str(len(clip_paths))),
                    "path": clip_path,  # Use the path string directly
                }
                
                # Add background music if it exists in the segment
                if isinstance(segment, dict) and segment.get("background_music", {}).get("url"):
                    clip_info["background_music"] = segment["background_music"]
                    
                clip_paths.append(clip_info)
                
            except Exception as e:
                segment_id = segment.get("id", "unknown")
                logger.error(
                    "Failed to process segment %s: %s",
                    segment_id,
                    str(e),
                    exc_info=True,
                )
                # Re-raise the exception to fail the entire process with proper exception chaining
                raise ProcessingError(
                    f"Failed to process segment {segment_id}: {str(e)}"
                ) from e
                
        return clip_paths

    def _get_output_path(self, video_id: str) -> str:
        """Generate output path for video"""
        filename = f"final_video_{video_id}.mp4"
        return os.path.join(settings.output_directory, filename)

    async def _concatenate_video_stage(self, context: PipelineContext) -> str:
        """Pipeline stage for concatenating final video

        Args:
            context: The pipeline context containing clip paths and other data

        Returns:
            str: Path to the concatenated video file

        Raises:
            ProcessingError: If there are no valid segments to concatenate
        """
        clip_paths = context.get("clip_paths")
        transitions = context.get("transitions")
        background_music = context.get("background_music")

        if not clip_paths:
            raise ProcessingError("No valid video segments to concatenate")

        # Generate output path
        filename = f"final_video_{context.video_id}.mp4"
        output_path = os.path.join(context.temp_dir, filename)

        # Convert clip_paths to the expected format if needed
        video_segments = []
        for clip in clip_paths:
            if isinstance(clip, dict) and "path" in clip:
                video_segments.append(
                    {
                        "id": clip.get("id", str(len(video_segments))),
                        "path": clip["path"],
                    }
                )
            elif isinstance(clip, str):
                video_segments.append({"id": str(len(video_segments)), "path": clip})

        # Concatenate clips using the injected video processor
        try:
            # Get the result from the coroutine
            result = self.video_processor.concatenate_clips(
                video_segments=video_segments,
                output_path=output_path,
                temp_dir=context.temp_dir,
                background_music=background_music,
                transitions=transitions,
            )

            # If the result is a coroutine, await it
            if asyncio.iscoroutine(result):
                final_clip_path = await result
            else:
                final_clip_path = result

            logger.info("✅ Created video: %s", final_clip_path)
            return final_clip_path

        except Exception as e:
            logger.error("Failed to concatenate video segments: %s", e, exc_info=True)
            raise ProcessingError(f"Failed to concatenate video segments: {e}") from e


# Create service instance
video_service = VideoCreationService()
