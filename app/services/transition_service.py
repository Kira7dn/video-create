"""
Advanced transition effects system for video segments
"""

from moviepy import VideoFileClip, CompositeVideoClip, ColorClip
from moviepy.video.fx import (
    FadeIn,
    FadeOut,
    SlideIn,
    SlideOut,
    CrossFadeIn,
    CrossFadeOut,
)
from typing import List, Dict, Any, Optional, Union
import logging

logger = logging.getLogger(__name__)


class TransitionService:
    """Service for creating advanced video transitions"""

    @staticmethod
    def create_fade_transition(
        clip1: Union[VideoFileClip, CompositeVideoClip],
        clip2: Union[VideoFileClip, CompositeVideoClip],
        duration: float = 1.0,
    ) -> List[Any]:
        """Create fade transition between two clips"""
        # Fade out first clip
        clip1_faded = FadeOut(duration).apply(clip1)

        # Fade in second clip with delay
        clip2_faded = FadeIn(duration).apply(clip2)

        return [clip1_faded, clip2_faded]

    @staticmethod
    def create_crossfade_transition(
        clip1: Union[VideoFileClip, CompositeVideoClip],
        clip2: Union[VideoFileClip, CompositeVideoClip],
        duration: float = 1.0,
    ) -> CompositeVideoClip:
        """Create crossfade transition with overlapping clips"""
        # Adjust clip timings for overlap
        clip1_adjusted = clip1.with_end(clip1.duration)
        clip2_adjusted = clip2.with_start(clip1.duration - duration)

        # Apply crossfade effects
        clip1_fade = CrossFadeOut(duration).apply(clip1_adjusted)
        clip2_fade = CrossFadeIn(duration).apply(clip2_adjusted)

        return CompositeVideoClip([clip1_fade, clip2_fade])

    @staticmethod
    def create_slide_transition(
        clip1: Union[VideoFileClip, CompositeVideoClip],
        clip2: Union[VideoFileClip, CompositeVideoClip],
        direction: str = "left",
        duration: float = 1.0,
    ) -> CompositeVideoClip:
        """Create slide transition effect"""
        # Slide out first clip
        if direction == "left":
            clip1_slide = SlideOut(duration, "left").apply(clip1)
            clip2_slide = SlideIn(duration, "right").apply(
                clip2.with_start(clip1.duration - duration)
            )
        elif direction == "right":
            clip1_slide = SlideOut(duration, "right").apply(clip1)
            clip2_slide = SlideIn(duration, "left").apply(
                clip2.with_start(clip1.duration - duration)
            )
        elif direction == "up":
            clip1_slide = SlideOut(duration, "top").apply(clip1)
            clip2_slide = SlideIn(duration, "bottom").apply(
                clip2.with_start(clip1.duration - duration)
            )
        else:  # down
            clip1_slide = SlideOut(duration, "bottom").apply(clip1)
            clip2_slide = SlideIn(duration, "top").apply(
                clip2.with_start(clip1.duration - duration)
            )

        return CompositeVideoClip([clip1_slide, clip2_slide])

    @staticmethod
    def create_wipe_transition(
        clip1: Union[VideoFileClip, CompositeVideoClip],
        clip2: Union[VideoFileClip, CompositeVideoClip],
        direction: str = "left",
        duration: float = 1.0,
    ) -> CompositeVideoClip:
        """Create wipe transition using masking"""
        # This would require custom mask creation
        # For now, return a simple fade as placeholder
        return TransitionService.create_crossfade_transition(clip1, clip2, duration)

    @staticmethod
    def create_zoom_transition(
        clip1: Union[VideoFileClip, CompositeVideoClip],
        clip2: Union[VideoFileClip, CompositeVideoClip],
        zoom_type: str = "in",
        duration: float = 1.0,
    ) -> CompositeVideoClip:
        """Create zoom transition effect"""
        from moviepy.video.fx.Resize import Resize

        if zoom_type == "in":
            # Zoom into first clip
            clip1_zoom = Resize(lambda t: 1 + 0.5 * (t / clip1.duration)).apply(clip1)
            clip2_start = clip2.with_start(clip1.duration - duration)
            clip2_fade = FadeIn(duration).apply(clip2_start)
        else:  # zoom out
            # Zoom out of first clip
            clip1_zoom = Resize(
                lambda t: max(0.5, 1 - 0.5 * (t / clip1.duration))
            ).apply(clip1)
            clip2_start = clip2.with_start(clip1.duration - duration)
            clip2_fade = FadeIn(duration).apply(clip2_start)

        return CompositeVideoClip([clip1_zoom, clip2_fade])

    @staticmethod
    def create_color_flash_transition(
        clip1: Union[VideoFileClip, CompositeVideoClip],
        clip2: Union[VideoFileClip, CompositeVideoClip],
        flash_color: str = "white",
        duration: float = 0.2,
    ) -> CompositeVideoClip:
        """Create color flash transition"""
        # Create color flash
        flash_clip = ColorClip(
            size=clip1.size, color=flash_color, duration=duration
        ).with_start(clip1.duration - duration / 2)

        # Fade clips around the flash
        clip1_fade = FadeOut(duration / 2).apply(clip1)
        clip2_fade = FadeIn(duration / 2).apply(
            clip2.with_start(clip1.duration - duration / 2)
        )

        return CompositeVideoClip([clip1_fade, flash_clip, clip2_fade])

    @staticmethod
    def apply_transition_between_clips(
        clips: List[Union[VideoFileClip, CompositeVideoClip]],
        transition_configs: List[Dict[str, Any]],
    ) -> List[Union[VideoFileClip, CompositeVideoClip]]:
        """
        Apply transitions between a list of clips

        transition_configs format:
        [
            {
                "type": "crossfade",
                "duration": 1.0,
                "params": {}
            }
        ]
        """
        if len(clips) < 2:
            return clips

        result_clips = [clips[0]]

        for i in range(1, len(clips)):
            if i - 1 < len(transition_configs):
                config = transition_configs[i - 1]
                transition_type = config.get("type", "fade")
                duration = config.get("duration", 1.0)
                params = config.get("params", {})

                prev_clip = result_clips[-1]
                current_clip = clips[i]

                if transition_type == "crossfade":
                    transition_result = TransitionService.create_crossfade_transition(
                        prev_clip, current_clip, duration
                    )
                    # Replace the last clip and add the composite
                    result_clips[-1] = transition_result
                elif transition_type == "slide":
                    direction = params.get("direction", "left")
                    transition_result = TransitionService.create_slide_transition(
                        prev_clip, current_clip, direction, duration
                    )
                    result_clips[-1] = transition_result
                elif transition_type == "zoom":
                    zoom_type = params.get("zoom_type", "in")
                    transition_result = TransitionService.create_zoom_transition(
                        prev_clip, current_clip, zoom_type, duration
                    )
                    result_clips[-1] = transition_result
                elif transition_type == "flash":
                    flash_color = params.get("color", "white")
                    transition_result = TransitionService.create_color_flash_transition(
                        prev_clip, current_clip, flash_color, duration
                    )
                    result_clips[-1] = transition_result
                else:  # default fade
                    fade_clips = TransitionService.create_fade_transition(
                        prev_clip, current_clip, duration
                    )
                    result_clips[-1] = fade_clips[0]
                    result_clips.append(fade_clips[1])
            else:
                result_clips.append(clips[i])

        return result_clips
