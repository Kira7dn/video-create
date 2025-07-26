"""
Media processing components.

This module contains processors for handling different types of media,
including audio, video, and images.
"""

# Import processors from submodules
from .audio.processor import AudioProcessor
from .video.video_processor import VideoProcessor
from .image.processor import ImageProcessor
from .video.transition_processor import TransitionProcessor
from .video.concat_processor import ConcatenationProcessor

__all__ = [
    "AudioProcessor",
    "VideoProcessor",
    "ImageProcessor",
    "TransitionProcessor",
    "ConcatenationProcessor",
]
