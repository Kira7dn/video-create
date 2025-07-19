"""
Workflow orchestration components.

This module contains processors that coordinate the execution of other processors
to implement complete video processing workflows.
"""

from .segment import SegmentProcessor
from .composer import ConcatenationProcessor

__all__ = [
    'SegmentProcessor',
    'ConcatenationProcessor',
]
