"""
Video processing components.

This package contains implementations of various video processing components
that can be composed to create a complete video processing pipeline.

Structure:
    core/           # Base classes and core functionality
    media/          # Media processing (audio, video, image)
    workflow/       # Workflow orchestration
    io/             # Input/Output operations
    text/           # Text processing
    validation/     # Data validation
"""

# Core components
from .core.base_processor import (
    ProcessorBase,
    SyncProcessor,
    AsyncProcessor,
)
from .core.metrics import MetricsCollector, ProcessingMetrics, ProcessingStage

# Media processing
from .media.audio.processor import AudioProcessor
from .media.video.video_processor import VideoProcessor
from .media.image.processor import ImageProcessor


# I/O
from .io.download import DownloadProcessor
from .io.upload import S3UploadProcessor

# Text processing
from .text.overlay import TextOverlayProcessor
from .text.transcript import TranscriptProcessor

# Validation
from .validation.processor import ValidationProcessor

__all__ = [
    # Core - New classes
    "ProcessorBase",
    "SyncProcessor",
    "AsyncProcessor",
    "MetricsCollector",
    "ProcessingMetrics",
    "ProcessingStage",
    # Media
    "AudioProcessor",
    "VideoProcessor",
    "ImageProcessor",
    # I/O
    "DownloadProcessor",
    "S3UploadProcessor",
    # Text
    "TextOverlayProcessor",
    "TranscriptProcessor",
    # Validation
    "ValidationProcessor",
]
