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
from .core.base_processor import BaseProcessor, BaseSyncProcessor, BatchProcessor
from .core.metrics import MetricsCollector, ProcessingMetrics, ProcessingStage

# Media processing
from .media.audio.processor import AudioProcessor
from .media.video.processor import VideoProcessor
from .media.image.processor import ImageProcessor

# Workflow
from .workflow.segment import SegmentProcessor
from .workflow.composer import ConcatenationProcessor

# I/O
from .io.download import DownloadProcessor
from .io.upload import S3UploadProcessor

# Text processing
from .text.overlay import TextOverlayProcessor
from .text.transcript import TranscriptProcessor

# Validation
from .validation.processor import create_validation_processor

__all__ = [
    # Core
    "BaseProcessor",
    "BaseSyncProcessor",
    "BatchProcessor",
    "MetricsCollector",
    "ProcessingMetrics",
    "ProcessingStage",
    # Media
    "AudioProcessor",
    "VideoProcessor",
    "ImageProcessor",
    # Workflow
    "SegmentProcessor",
    "ConcatenationProcessor",
    # I/O
    "DownloadProcessor",
    "S3UploadProcessor",
    # Text
    "TextOverlayProcessor",
    "TranscriptProcessor",
    # Validation
    "create_validation_processor",
]
