"""
Concatenation processor for combining video segments
"""

import logging
import os
from typing import List, Dict, Optional
import asyncio

from app.core.exceptions import ProcessingError
from app.interfaces.pipeline.context import IPipelineContext
from app.services.processors.core.base_processor import (
    AsyncProcessor,
    ProcessingStage,
)
from utils.video_utils import ffmpeg_concat_videos

logger = logging.getLogger(__name__)


class ConcatenationProcessor(AsyncProcessor):
    """Handles video concatenation with transitions and background music"""

    # No need to override __init__ if just calling parent's __init__

    async def process(self, input_data: List[Dict[str, str]], **kwargs) -> str:
        """Process concatenation request asynchronously

        This method is maintained for backward compatibility.

        Args:
            input_data: List of clip paths
            **kwargs: Additional processing parameters

        Returns:
            Path to the concatenated video
        """
        video_segments = input_data
        context: IPipelineContext = kwargs.get("context", {})
        background_music = context.get("background_music")
        temp_dir = context.temp_dir
        filename = f"final_video_{context.video_id}.mp4"
        output_path = os.path.join("data", "output", filename)
        context.set("final_video_path", output_path)
        return await self.concatenate_clips(
            video_segments, output_path, temp_dir, background_music
        )

    async def concatenate_clips(
        self,
        video_segments: List[Dict[str, str]],
        output_path: str,
        temp_dir: str,
        background_music: Optional[Dict] = None,
    ) -> str:
        """
        Concatenate video clips using ffmpeg with transitions and background music

        Args:
            video_segments: List of video segment info dicts with 'id' and 'path'
            output_path: Path for the final output video
            temp_dir: Temporary directory for processing
            background_music: Background music configuration

        Returns:
            Path to the final concatenated video

        Raises:
            ProcessingError: If concatenation fails
        """
        metric = self._start_processing(ProcessingStage.CONCATENATION)

        try:

            # Log concatenation start
            self.logger.info(
                "Starting concatenation of %s segments", len(video_segments)
            )
            self.logger.info("Output path: %s", output_path)

            # Run ffmpeg in a thread since it's a blocking I/O operation
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,  # Use default thread pool
                lambda: ffmpeg_concat_videos(
                    video_segments=video_segments,
                    output_path=output_path,
                    temp_dir=temp_dir,
                    background_music=background_music,
                    logger=self.logger,
                ),
            )

            # Verify output exists
            if not os.path.exists(output_path):
                raise ProcessingError(
                    f"Concatenation completed but output file not found: {output_path}"
                )

            # Get file size for metrics
            file_size = os.path.getsize(output_path)

            self.logger.info("✅ Video concatenation completed successfully")
            self.logger.info("   Output: %s", output_path)
            self.logger.info("   Size: %.2f MB", file_size / (1024 * 1024))

            self._end_processing(
                metric, success=True, items_processed=len(video_segments)
            )
            return output_path

        except Exception as e:
            error_msg = "Failed to concatenate video clips: %s", e
            self.logger.error(error_msg, exc_info=True)
            self._end_processing(metric, success=False, error_message=error_msg)
            raise ProcessingError(error_msg) from e
