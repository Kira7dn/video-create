"""
Interfaces package for the application.

This package contains all the interface definitions used across the application.
"""

from .video import IVideoProcessor, ISegmentProcessor
from .storage import IDownloader, IUploader
from .validation import IValidator
from .metrics import IMetricsCollector
from .audio import IAudioProcessor

__all__ = [
    'IVideoProcessor',
    'ISegmentProcessor',
    'IDownloader',
    'IUploader',
    'IValidator',
    'IMetricsCollector',
    'IAudioProcessor',
]
