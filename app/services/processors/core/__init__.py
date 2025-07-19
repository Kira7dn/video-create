"""
Core processor components.

This module contains the base processor classes and core functionality
used throughout the video processing pipeline.
"""

from .base_processor import BaseProcessor, BaseSyncProcessor, BatchProcessor
from .metrics import MetricsCollector, ProcessingMetrics, ProcessingStage

__all__ = [
    "BaseProcessor",
    "BaseSyncProcessor",
    "BatchProcessor",
    "MetricsCollector",
    "ProcessingMetrics",
    "ProcessingStage",
]
