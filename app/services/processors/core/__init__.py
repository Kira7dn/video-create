"""
Core processor components.

This module contains the base processor classes and core functionality
used throughout the video processing pipeline.
"""

from .base_processor import (
    ProcessorBase,
    SyncProcessor,
    AsyncProcessor,
)
from .metrics import MetricsCollector, ProcessingMetrics, ProcessingStage

__all__ = [
    # New classes
    "ProcessorBase",
    "SyncProcessor",
    "AsyncProcessor",
    # Metrics
    "MetricsCollector",
    "ProcessingMetrics",
    "ProcessingStage",
]
