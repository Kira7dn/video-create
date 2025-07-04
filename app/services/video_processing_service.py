"""
Video processing service for creating video clips from segments
"""

import os
import uuid
import logging
import gc
import numpy as np
from typing import List, Dict, Optional, Any

from moviepy import (
    VideoFileClip,
    ImageClip,
    AudioFileClip,
    CompositeVideoClip,
    concatenate_videoclips,
    concatenate_audioclips,
    ColorClip,
    TextClip,
    CompositeAudioClip,
    AudioClip,
)

from app.core.exceptions import VideoCreationError
from app.services.config.video_config import video_config
from app.services.resource_manager import ResourceManager
from utils.video_utils import export_final_video_clip

logger = logging.getLogger(__name__)


class VideoProcessingService:
    """Service for processing video clips from segments"""

    def __init__(self, resource_manager: Optional[ResourceManager] = None):
        self.resource_manager = resource_manager or ResourceManager()

    def _create_text_clips(self, texts: List[Dict], duration: float) -> List[TextClip]:
        """Create text clips from text configurations"""
        text_clips = []

        for text_info in texts:
            txt_clip = (
                TextClip(
                    text_info["text"],
                    font_size=text_info.get("fontsize", video_config.default_font_size),
                    color=text_info.get("color", video_config.default_text_color),
                )
                .with_position(
                    text_info.get("position", video_config.default_text_position)
                )
                .with_duration(duration)
            )
            text_clips.append(self.resource_manager.track_clip(txt_clip))

        return text_clips

    def _create_audio_composition(
        self, segment: Dict, apply_duration: float
    ) -> Optional[CompositeAudioClip]:
        """Create composite audio from segment audio assets (asset object format)"""
        audio_clips = []

        # Background music
        bg_music = segment.get("background_music", {})
        bg_music_path = bg_music.get("local_path")
        bgm_start_delay = bg_music.get("start_delay", 0)
        bgm_end_delay = bg_music.get("end_delay", 0)
        if bg_music_path:
            bgm_clip = self.resource_manager.track_clip(AudioFileClip(bg_music_path))

            # Loop or trim background music to match duration (không tính delay)
            music_duration = apply_duration - bgm_start_delay - bgm_end_delay
            if music_duration < 0:
                music_duration = 0
            if bgm_clip.duration < music_duration:
                bgm_clip = bgm_clip.with_duration(music_duration).with_fps(
                    video_config.default_audio_fps
                )
            else:
                bgm_clip = bgm_clip.with_duration(music_duration)

            # Thêm silence đầu/cuối nếu có delay
            from moviepy.audio.AudioClip import AudioClip as MoviePyAudioClip
            if bgm_start_delay > 0:
                silence_start = MoviePyAudioClip(
                    lambda t: np.zeros((len(t) if hasattr(t, "__len__") else 1, 2)),
                    duration=bgm_start_delay,
                    fps=getattr(bgm_clip, "fps", video_config.default_audio_fps),
                )
                audio_clips.append(silence_start)
            # Giảm volume
            from moviepy.audio.fx.MultiplyVolume import MultiplyVolume
            bgm_quiet = MultiplyVolume(
                factor=video_config.background_music_volume
            ).apply(bgm_clip)
            audio_clips.append(bgm_quiet)
            if bgm_end_delay > 0:
                silence_end = MoviePyAudioClip(
                    lambda t: np.zeros((len(t) if hasattr(t, "__len__") else 1, 2)),
                    duration=bgm_end_delay,
                    fps=getattr(bgm_clip, "fps", video_config.default_audio_fps),
                )
                audio_clips.append(silence_end)

        # Voice over with delays
        voice_over = segment.get("voice_over", {})
        voice_over_path = voice_over.get("local_path")
        start_delay = voice_over.get("start_delay", video_config.default_start_delay)
        end_delay = voice_over.get("end_delay", video_config.default_end_delay)
        if voice_over_path:
            original_voice_clip = self.resource_manager.track_clip(
                AudioFileClip(voice_over_path)
            )

            # Create silence clips
            silence_start = AudioClip(
                lambda t: np.zeros((len(t) if hasattr(t, "__len__") else 1, 2)),
                duration=start_delay,
                fps=getattr(original_voice_clip, "fps", video_config.default_audio_fps),
            )
            silence_end = AudioClip(
                lambda t: np.zeros((len(t) if hasattr(t, "__len__") else 1, 2)),
                duration=end_delay,
                fps=getattr(original_voice_clip, "fps", video_config.default_audio_fps),
            )

            # Concatenate: silence + voice + silence
            voice_clip = concatenate_audioclips(
                [silence_start, original_voice_clip, silence_end]
            )
            audio_clips.append(self.resource_manager.track_clip(voice_clip))

        return CompositeAudioClip(audio_clips) if audio_clips else None

    def _determine_segment_duration(self, segment: Dict) -> float:
        """Determine the total duration for a segment, including start_delay and end_delay, theo format asset object mới"""
        # Ưu tiên lấy duration từ voice_over nếu có
        voice_over = segment.get("voice_over", {})
        voice_over_path = voice_over.get("local_path")
        start_delay = voice_over.get("start_delay", video_config.default_start_delay)
        end_delay = voice_over.get("end_delay", video_config.default_end_delay)
        if voice_over_path:
            try:
                voice_clip = AudioFileClip(voice_over_path)
                duration = voice_clip.duration
                voice_clip.close()
                logger.info(f"Set segment duration from voice_over: {duration:.2f}s")
            except Exception as e:
                logger.warning(f"Failed to get duration from voice_over: {e}")
                duration = video_config.default_segment_duration
        else:
            duration = video_config.default_segment_duration

        total_duration = duration + start_delay + end_delay
        logger.info(f"Total segment duration (with delay): {total_duration:.2f}s")
        return total_duration

    def create_segment_clip(self, segment: Dict, temp_dir: str) -> VideoFileClip:
        """Create a video clip from a processed segment (asset object format)"""
        try:
            # Determine timing
            total_duration = self._determine_segment_duration(segment)
            logger.info(
                f"Creating clip with total duration: {total_duration:.2f}s"
            )

            # Validate background image
            image_obj = segment.get("image", {})
            bg_image_path = image_obj.get("local_path")
            if not bg_image_path or not os.path.exists(bg_image_path):
                raise VideoCreationError("Background image not found for segment")

            # Process image with padding for consistent size
            from utils.image_utils import process_images_with_padding

            processed_paths = process_images_with_padding(
                image_paths=bg_image_path,
                target_size=(1920, 1080),  # Standard HD size
                smart_pad_color=True,  # Enable smart padding color detection
                pad_color_method="average_edge",  # Use average edge method
                auto_enhance=True,  # Enable auto image enhancement
                enhance_brightness=True,  # Auto brightness adjustment
                enhance_contrast=True,  # Auto contrast enhancement
                enhance_saturation=True,  # Auto saturation optimization
                output_dir=temp_dir,
            )

            if not processed_paths:
                raise VideoCreationError("Failed to process background image")

            processed_bg_path = processed_paths[0]

            # Track processed file for cleanup
            self.resource_manager.track_file(processed_bg_path)

            # Create base video clip with processed image
            base_clip = self.resource_manager.track_clip(
                ImageClip(processed_bg_path, duration=total_duration)
            )

            # Add text overlays
            text_clips = self._create_text_clips(
                segment.get("texts", []), total_duration
            )

            # Compose video with text overlays
            video_clips = [base_clip] + text_clips
            final_clip = CompositeVideoClip(
                video_clips, size=getattr(base_clip, "size", (1920, 1080))
            )

            # Add audio composition
            # Cần truyền đúng asset object cho _create_audio_composition nếu muốn đồng bộ
            audio_composition = self._create_audio_composition(segment, total_duration)
            if audio_composition:
                final_clip = final_clip.with_audio(audio_composition)

            # Set FPS
            final_clip = final_clip.with_fps(video_config.default_fps)

            # Export to file
            segment_id = segment.get("id", str(uuid.uuid4()))
            segment_output_path = os.path.join(
                temp_dir, f"temp_segment_{segment_id}.mp4"
            )
            export_final_video_clip(final_clip, segment_output_path)

            # Track output file for cleanup
            self.resource_manager.track_file(segment_output_path)

            # Close the composition clip
            final_clip.close()

            # Return a new clip loaded from the stable file
            return VideoFileClip(segment_output_path)

        except Exception as e:
            logger.error(f"Failed to create segment clip: {e}", exc_info=True)
            raise VideoCreationError(f"Failed to create segment clip: {e}") from e

    def create_multiple_segment_clips(
        self, segments: List[Dict], temp_dir: str
    ) -> List[str]:
        """Create multiple segment clips and return file paths"""
        clip_paths = []

        for i, segment in enumerate(segments):
            try:
                clip = self.create_segment_clip(segment, temp_dir)
                # Get the file path before closing
                clip_path = clip.filename
                clip_paths.append(clip_path)

                # Close the clip immediately to free memory
                clip.close()

                # Force garbage collection to ensure memory is freed
                gc.collect()

                logger.info(
                    f"✅ Created and closed segment {i+1}/{len(segments)}: {clip_path}"
                )
            except Exception as e:
                logger.error(f"❌ Failed to create segment {i+1}: {e}")
                # No need to clean up clips since we close them immediately
                raise

        return clip_paths

    def concatenate_clips(
        self, clip_paths: List[str], output_path: str, background_music: Optional[dict] = None
    ) -> Any:
        """Concatenate video clips using ffmpeg only. Transitions are not supported."""
        from utils.video_utils import ffmpeg_concat_videos
        import psutil

        try:
            if not clip_paths:
                raise VideoCreationError("No clip paths provided for concatenation")

            # Log memory usage before concatenation
            memory = psutil.virtual_memory()
            logger.info(
                f"Memory usage before concatenation: {memory.percent:.1f}% ({memory.used // 1024 // 1024} MB used)"
            )

            ffmpeg_concat_videos(clip_paths, output_path, background_music, logger=logger)
            logger.info(f"ffmpeg concat output: {output_path}")
            # self.resource_manager.track_file(output_path)

            # Log memory usage after concatenation
            memory_after = psutil.virtual_memory()
            logger.info(
                f"Memory usage after concatenation: {memory_after.percent:.1f}% ({memory_after.used // 1024 // 1024} MB used)"
            )

            return output_path

        except Exception as e:
            logger.error(f"Failed to concatenate clips: {e}", exc_info=True)
            raise VideoCreationError(f"Failed to concatenate clips: {e}") from e
