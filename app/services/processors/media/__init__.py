"""
Media processing components.

This module contains processors for handling different types of media,
including audio, video, and images.
"""

# Import processors from submodules
from .audio.processor import AudioProcessor
from .video.processor import VideoProcessor
from .image.processor import ImageProcessor

__all__ = [
    "AudioProcessor",
    "VideoProcessor",
    "ImageProcessor",
]
