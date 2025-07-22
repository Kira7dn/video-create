"""
Interfaces package for the application.

This package contains all the interface definitions used across the application.
"""

from .audio import IAudioProcessor
from .metrics import IMetricsCollector
from .pipeline import IPipeline, IPipelineContext, IPipelineStage
from .storage import IDownloader, IUploader
from .validation import IValidator
from .video import IVideoProcessor, ISegmentProcessor

__all__ = [
    # Pipeline interfaces
    "IPipeline",
    "IPipelineContext",
    "IPipelineStage",
    # Other interfaces
    "IAudioProcessor",
    "IDownloader",
    "IUploader",
    "IValidator",
    "IMetricsCollector",
    "IVideoProcessor",
    "ISegmentProcessor",
]
