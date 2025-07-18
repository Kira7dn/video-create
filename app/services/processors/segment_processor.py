"""
Segment Processor Module

This module provides functionality to create video segment clips from segment data.
It handles processing of both image and video segments, applying transitions,
and combining with audio to produce final video segments.
"""

import asyncio
import logging
import os
import subprocess
import uuid
from typing import Any, Dict

from app.config import settings
from app.core.exceptions import ProcessingError, VideoCreationError
from app.services.processors.audio_processor import AudioProcessor
from app.services.processors.base_processor import ProcessingStage
from app.services.processors.text_overlay_processor import TextOverlayProcessor
from app.services.processors.transition_processor import TransitionProcessor
from app.services.processors.base_processor import BaseProcessor
from app.services.processors.interfaces import ISegmentProcessor
from utils.subprocess_utils import safe_subprocess_run
from utils.image_utils import process_image

logger = logging.getLogger(__name__)


class SegmentProcessor(BaseProcessor, ISegmentProcessor):
    """Handles creation of a single video segment clip from a segment dict"""

    def __init__(self, metrics_collector=None):
        super().__init__(metrics_collector)
        # AudioProcessor is a static class and doesn't need metrics_collector
        self.audio_processor = AudioProcessor
        self.text_processor = TextOverlayProcessor()
        self.transition_processor = TransitionProcessor()

    async def _process_async(self, input_data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Process input data asynchronously by delegating to process_segment.

        This method implements the abstract method from BaseProcessor.

        Args:
            input_data: Dictionary containing segment information
            **kwargs: Additional processing parameters

        Returns:
            Dictionary containing processing results
        """
        return await self.process_segment(input_data, **kwargs)
        
    async def process(self, input_data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Process input data by delegating to _process_async.
        
        This method is maintained for backward compatibility.
        
        Args:
            input_data: Dictionary containing segment information
            **kwargs: Additional processing parameters
            
        Returns:
            Dictionary containing processing results
            
        Raises:
            ProcessingError: If processing fails
        """
        return await self._process_async(input_data, **kwargs)

    async def process_segment(
        self, segment: Dict[str, Any], temp_dir: str, **kwargs
    ) -> Dict[str, Any]:
        """
        Process a single video segment.

        This is the main entry point that implements the ISegmentProcessor interface.
        It wraps the existing create_segment_clip functionality with proper error handling
        and metrics collection.
        """
        try:
            metric = self._start_processing(ProcessingStage.SEGMENT_CREATION)
            segment_id = segment.get("id", "unknown")

            logger.debug("Processing segment %s", segment_id)
            output_path = await self._create_segment_clip_async(
                segment, temp_dir, **kwargs
            )

            self._end_processing(metric, success=True, items_processed=1)

            return {
                "id": segment_id,
                "path": output_path,
                "duration": self._get_duration(output_path),
            }

        except Exception as e:
            error_msg = (
                f"Failed to process segment {segment.get('id', 'unknown')}: {str(e)}"
            )
            if 'metric' in locals():
                self._end_processing(
                    metric, success=False, error_message=error_msg, items_processed=0
                )
            raise ProcessingError(error_msg) from e

    @staticmethod
    def _get_duration(video_path: str) -> float:
        """Get duration of a video file in seconds"""
        try:
            cmd = [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                video_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return float(result.stdout.strip())
        except (subprocess.CalledProcessError, ValueError) as e:
            logger.warning(
                "Could not determine duration for %s: %s", video_path, str(e)
            )
            return 0.0

    async def _create_segment_clip_async(
        self, segment: Dict[str, Any], temp_dir: str, **_
    ) -> str:
        """Async wrapper around the existing create_segment_clip method"""
        # For now, we'll run the sync version in a thread pool
        # This can be optimized later with native async FFmpeg
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, lambda: self.create_segment_clip(segment, temp_dir)
        )

    @classmethod
    def create_segment_clip(cls, segment: Dict, temp_dir: str) -> str:
        """Create a video segment clip from segment data.

        Args:
            segment (Dict): Dictionary containing segment information including
                image, video, transitions, and voice-over data.
            temp_dir (str): Path to the temporary directory for storing
                intermediate files.

        Returns:
            str: Path to the created segment video file.

        Raises:
            VideoCreationError: If required resources are missing or processing fails.
        """
        image_obj = segment.get("image", {})
        video_obj = segment.get("video", {})
        bg_image_path = image_obj.get("local_path")
        video_path = video_obj.get("local_path")

        # Ensure transition_in and transition_out are always dictionaries
        transition_in = segment.get("transition_in") or {}
        if not isinstance(transition_in, dict):
            logger.warning("transition_in is not a dictionary, using default values")
            transition_in = {}

        transition_out = segment.get("transition_out") or {}
        if not isinstance(transition_out, dict):
            logger.warning("transition_out is not a dictionary, using default values")
            transition_out = {}
        segment_id = segment.get("id", str(uuid.uuid4()))
        voice_over = segment.get("voice_over", {})
        segment_output_path = os.path.join(temp_dir, f"temp_segment_{segment_id}.mp4")

        if video_path and os.path.exists(video_path):
            input_type = "video"
            input_path = video_path
            try:
                probe_cmd = [
                    "ffprobe",
                    "-v",
                    "quiet",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "csv=p=0",
                    video_path,
                ]
                result = subprocess.run(
                    probe_cmd, capture_output=True, text=True, check=True
                )
                duration_str = result.stdout.strip()
                if not duration_str:
                    raise ValueError("Empty duration output from ffprobe")
                original_duration = float(duration_str)
            except (subprocess.CalledProcessError, FileNotFoundError, ValueError) as e:
                logger.warning(
                    "Could not get video duration for segment %s, "
                    "using default 4.0s. Error: %s\nCommand output: %s",
                    segment_id,
                    str(e),
                    getattr(e, "stderr", "No stderr"),
                )
                original_duration = 4.0
            audio_input_path = video_path
        else:
            input_type = "image"
            if not bg_image_path or not os.path.exists(bg_image_path):
                raise VideoCreationError("Background image not found for segment")
            processed_image_paths = process_image(
                image_paths=bg_image_path,
                target_size=(1920, 1080),
                smart_pad_color=True,
                pad_color_method="average_edge",
                auto_enhance=True,
                enhance_brightness=True,
                enhance_contrast=True,
                enhance_saturation=True,
                output_dir=temp_dir,
            )
            if not processed_image_paths:
                raise VideoCreationError("Failed to process background image")
            input_path = processed_image_paths[0]
            audio_path = AudioProcessor.create_audio_composition(segment, temp_dir)
            if not audio_path:
                raise VideoCreationError(
                    "Audio composition failed or missing for segment"
                )
            try:
                probe_cmd = [
                    "ffprobe",
                    "-v",
                    "quiet",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "csv=p=0",
                    audio_path,
                ]
                result = subprocess.run(
                    probe_cmd, capture_output=True, text=True, check=True
                )
                original_duration = float(result.stdout.strip())
            except subprocess.CalledProcessError as e:
                logger.warning(
                    "Could not get audio duration for segment %s: %s",
                    segment_id,
                    str(e),
                )
                original_duration = 4.0
            fade_in_duration = float(transition_in.get("duration", 0) or 0)
            fade_out_duration = float(transition_out.get("duration", 0) or 0)
            extended_audio_path = audio_path
            if fade_in_duration > 0 or fade_out_duration > 0:
                extended_audio_path = os.path.join(
                    temp_dir, f"extended_audio_{segment_id}.wav"
                )
                audio_inputs = []
                if fade_in_duration > 0:
                    audio_inputs.append(
                        f"-f lavfi -t {fade_in_duration} "
                        "-i anullsrc=channel_layout=stereo:sample_rate=44100"
                    )
                audio_inputs.append(f"-i {audio_path}")
                if fade_out_duration > 0:
                    audio_inputs.append(
                        f"-f lavfi -t {fade_out_duration} "
                        "-i anullsrc=channel_layout=stereo:sample_rate=44100"
                    )
                if fade_in_duration > 0 and fade_out_duration > 0:
                    filter_str = "[0:a][1:a][2:a]concat=n=3:v=0:a=1[aout]"
                elif fade_in_duration > 0 or fade_out_duration > 0:
                    filter_str = "[0:a][1:a]concat=n=2:v=0:a=1[aout]"
                else:
                    filter_str = "[0:a]acopy[aout]"
                extend_cmd = ["ffmpeg", "-y"]
                for inp in audio_inputs:
                    extend_cmd += inp.split()
                extend_cmd += [
                    "-filter_complex",
                    filter_str,
                    "-map",
                    "[aout]",
                    "-ac",
                    "2",
                    "-ar",
                    "44100",
                    extended_audio_path,
                ]
                safe_subprocess_run(
                    extend_cmd,
                    f"Create extended audio for segment {segment_id}",
                    logger,
                )
            audio_input_path = extended_audio_path

        video_filters = ["scale=1920:1080", "format=yuv420p"]
        audio_filters = ["volume=1.5"]
        fade_in_duration = float(transition_in.get("duration", 0) or 0)
        fade_out_duration = float(transition_out.get("duration", 0) or 0)
        fade_in_type = (
            transition_in.get("type", "fade").lower()
            if transition_in.get("type")
            else "fade"
        )
        fade_out_type = (
            transition_out.get("type", "fade").lower()
            if transition_out.get("type")
            else "fade"
        )
        if fade_in_duration > 0:
            if TransitionProcessor.is_preprocessing_supported(fade_in_type):
                TransitionProcessor.apply_transition_in_filter(
                    video_filters, audio_filters, fade_in_type, fade_in_duration
                )
                transition_type = "overlay" if input_type == "video" else "additive"
                logger.debug(
                    "Applied %s transition-in: %ss (%s)",
                    fade_in_type,
                    fade_in_duration,
                    transition_type,
                )
            else:
                logger.warning(
                    "Transition-in type '%s' not supported for "
                    "preprocessing, using basic fade",
                    fade_in_type,
                )
                fade_in_type = "fade"
                video_filters.append(f"fade=t=in:st=0:d={fade_in_duration}")
                audio_filters.append(f"afade=t=in:st=0:d={fade_in_duration}")
        if fade_out_duration > 0:
            fade_out_start = (
                max(0, original_duration - fade_out_duration)
                if input_type == "video"
                else fade_in_duration + original_duration
            )
            if TransitionProcessor.is_preprocessing_supported(fade_out_type):
                TransitionProcessor.apply_transition_out_filter(
                    video_filters,
                    audio_filters,
                    fade_out_type,
                    fade_out_duration,
                    fade_out_start,
                )
                transition_type = "overlay" if input_type == "video" else "additive"
                logger.debug(
                    "Applied %s transition-out: %ss starting at %ss (%s)",
                    fade_out_type,
                    fade_out_duration,
                    fade_out_start,
                    transition_type,
                )
            else:
                logger.warning(
                    "Transition-out type '%s' not supported for "
                    "preprocessing, using basic fade",
                    fade_out_type,
                )
                fade_out_type = "fade"
                video_filters.append(
                    f"fade=t=out:st={fade_out_start}:d={fade_out_duration}"
                )
                audio_filters.append(
                    f"afade=t=out:st={fade_out_start}:d={fade_out_duration}"
                )

        # Calculate total duration
        total_duration = (
            original_duration
            if input_type == "video"
            else fade_in_duration + original_duration + fade_out_duration
        )
        # Calculate delay
        delay = fade_in_duration + voice_over.get("start_delay", 0)
        # Handle text overlays - build them separately to avoid conflicts
        text_overs = segment.get("text_over")
        if text_overs:
            if not isinstance(text_overs, list):
                raise VideoCreationError("text_over must be an array of objects")

            # Add text filters directly to video filters
            for text_over in text_overs:
                drawtext_filter = TextOverlayProcessor.build_drawtext_filter(
                    text_over, total_duration, delay
                )
                if drawtext_filter:
                    video_filters.append(drawtext_filter)

        # Build FFmpeg command based on input type
        if input_type == "video":
            ffmpeg_cmd = [
                "ffmpeg",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "anullsrc=channel_layout=stereo:sample_rate=44100",
                "-i",
                input_path,
                "-vf",
                ",".join(video_filters),
                "-af",
                ",".join(audio_filters),
                "-t",
                str(total_duration),
                "-map",
                "1:v",
                "-map",
                "0:a",
                "-pix_fmt",
                "yuv420p",
                "-r",
                str(settings.video_default_fps),
                "-c:v",
                "libx264",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                segment_output_path,
            ]
        else:
            ffmpeg_cmd = [
                "ffmpeg",
                "-y",
                "-loop",
                "1",
                "-i",
                input_path,
                "-i",
                audio_input_path,
                "-vf",
                ",".join(video_filters),
                "-af",
                ",".join(audio_filters),
                "-t",
                str(total_duration),
                "-pix_fmt",
                "yuv420p",
                "-r",
                str(settings.video_default_fps),
                "-c:v",
                "libx264",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                segment_output_path,
            ]
        safe_subprocess_run(ffmpeg_cmd, f"Create segment clip {segment_id}", logger)
        return segment_output_path
