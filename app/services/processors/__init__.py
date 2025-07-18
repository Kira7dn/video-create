# Package marker for processors
"""
Video processing components.

This package contains implementations of various video processing components
that can be composed to create a complete video processing pipeline.
"""

from .interfaces import ISegmentProcessor, IBatchProcessor
from .segment_processor import SegmentProcessor

__all__ = [
    'ISegmentProcessor',
    'IBatchProcessor',
    'SegmentProcessor',
]
