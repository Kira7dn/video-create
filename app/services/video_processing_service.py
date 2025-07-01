"""
Video processing service for creating video clips from segments
"""

import os
import uuid
import logging
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
        """Create composite audio from segment audio assets"""
        audio_clips = []

        # Background music
        if bg_music_path := segment.get("background_music_path"):
            bgm_clip = self.resource_manager.track_clip(AudioFileClip(bg_music_path))

            # Loop or trim background music to match duration
            if bgm_clip.duration < apply_duration:
                bgm_clip = bgm_clip.with_duration(apply_duration).with_fps(
                    video_config.default_audio_fps
                )
            else:
                bgm_clip = bgm_clip.with_duration(apply_duration)

            # Reduce volume
            from moviepy.audio.fx.MultiplyVolume import MultiplyVolume

            bgm_quiet = MultiplyVolume(
                factor=video_config.background_music_volume
            ).apply(bgm_clip)
            audio_clips.append(bgm_quiet)

        # Voice over with delays
        if voice_over_path := segment.get("voice_over_path"):
            start_delay = segment.get("start_delay", video_config.default_start_delay)
            end_delay = segment.get("end_delay", video_config.default_end_delay)

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
        """Determine the duration for a segment"""
        # If voice_over exists, use its duration
        if voice_over_path := segment.get("voice_over_path"):
            try:
                voice_clip = AudioFileClip(voice_over_path)
                duration = voice_clip.duration
                voice_clip.close()
                logger.info(f"Set segment duration from voice_over: {duration:.2f}s")
                return duration
            except Exception as e:
                logger.warning(f"Failed to get duration from voice_over: {e}")

        # Use explicit duration or default
        return segment.get("duration", video_config.default_segment_duration)

    def create_segment_clip(self, segment: Dict, temp_dir: str) -> VideoFileClip:
        """Create a video clip from a processed segment"""
        try:
            # Determine timing
            duration = self._determine_segment_duration(segment)
            start_delay = segment.get("start_delay", video_config.default_start_delay)
            end_delay = segment.get("end_delay", video_config.default_end_delay)
            apply_duration = duration + start_delay + end_delay

            logger.info(
                f"Creating clip with duration: {duration:.2f}s, total: {apply_duration:.2f}s"
            )

            # Validate background image
            bg_image_path = segment.get("background_image_path")
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
                ImageClip(processed_bg_path, duration=apply_duration)
            )

            # Add text overlays
            text_clips = self._create_text_clips(
                segment.get("texts", []), apply_duration
            )

            # Compose video with text overlays
            video_clips = [base_clip] + text_clips
            final_clip = CompositeVideoClip(
                video_clips, size=getattr(base_clip, "size", (1920, 1080))
            )

            # Add audio composition
            audio_composition = self._create_audio_composition(segment, apply_duration)
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
    ) -> List[VideoFileClip]:
        """Create multiple segment clips"""
        clips = []

        for i, segment in enumerate(segments):
            try:
                clip = self.create_segment_clip(segment, temp_dir)
                clips.append(clip)
                logger.info(f"✅ Created segment {i+1}/{len(segments)}")
            except Exception as e:
                logger.error(f"❌ Failed to create segment {i+1}: {e}")
                # Clean up successful clips before re-raising
                for clip in clips:
                    try:
                        clip.close()
                    except:
                        pass
                raise

        return clips

    def concatenate_clips_with_transitions(
        self, clip_paths: List[str], transitions: Optional[List[Any]] = None
    ) -> Any:
        """Concatenate video clips with optional transitions"""
        from utils.video_utils import concatenate_videos_with_sequence

        try:
            if not clip_paths:
                raise VideoCreationError("No clip paths provided for concatenation")

            # Use utility function for concatenation with transitions
            final_clip = concatenate_videos_with_sequence(
                clip_paths, transitions=transitions
            )

            # Ensure we have a valid video clip (VideoFileClip, CompositeVideoClip, or VideoClip)
            if final_clip is not None:
                self.resource_manager.track_clip(final_clip)
                return final_clip
            else:
                raise VideoCreationError("Concatenation returned None")

        except Exception as e:
            logger.error(f"Failed to concatenate clips: {e}", exc_info=True)
            raise VideoCreationError(f"Failed to concatenate clips: {e}") from e
