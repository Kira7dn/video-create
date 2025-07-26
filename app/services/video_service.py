"""
Refactored video creation service with improved architecture
"""

# Standard library imports
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Dict

# Third-party imports
# (none currently)

# Local application imports
from app.config.settings import settings
from app.core.exceptions import (
    DownloadError,
    ProcessingError,
    VideoCreationError,
)
from app.services.pipelines import create_video_creation_pipeline
from app.services.pipelines.context.default import PipelineContext
from utils.resource_manager import (
    cleanup_old_temp_directories,
    managed_temp_directory,
)

logger = logging.getLogger(__name__)


class VideoCreationService:
    """
    Coordinates the video creation process using a pipeline architecture.

    This service orchestrates the video creation process by coordinating between
    different processors and services.
    """

    def __init__(self):
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

    async def _process_video_creation_pipeline(
        self, json_data: Dict, temp_dir: str, video_id: str
    ) -> Dict:
        """
        Process video creation using pipeline pattern.

        Args:
            json_data: Input JSON data containing video configuration
            temp_dir: Temporary directory for processing files
            video_id: Unique identifier for the video being processed

        Returns:
            Dict containing paths to the created video and its S3 URL

        Raises:
            VideoCreationError: If video creation or upload fails
        """
        # Create pipeline context
        context_data = {
            "json_data": json_data,
            "segments": json_data.get("segments", []),
            "transitions": json_data.get("transitions", []),
            "background_music": json_data.get("background_music"),
            "keywords": json_data.get("keywords", []),
        }
        context = PipelineContext(
            data=context_data,
            temp_dir=temp_dir,
            video_id=video_id,
            metadata={"start_time": time.time()},
        )

        # Create and execute pipeline
        pipeline = create_video_creation_pipeline()
        result = await pipeline.execute(context)
        context: PipelineContext = result.get("context")

        # Validate and return results
        final_video_path = context.get("final_video_path")
        s3_url = context.get("final_video_url")

        if not final_video_path or not os.path.exists(final_video_path):
            raise VideoCreationError("Final video was not created successfully")
        if not s3_url:
            raise VideoCreationError("S3 upload failed or S3 URL not found")

        return {"video_path": final_video_path, "s3_url": s3_url}


# Create service instance
video_service = VideoCreationService()
