"""
Interfaces for video processing components.

This module defines the protocol interfaces for various processors
used in the video processing pipeline.
"""

from typing import Dict, Any, Protocol, runtime_checkable


@runtime_checkable
class ISegmentProcessor(Protocol):
    """Interface for processing individual video segments.

    Implementations of this protocol are responsible for processing a single video segment
    with its associated assets (images, audio, transitions, etc.).
    """

    async def process_segment(
        self, segment: Dict[str, Any], temp_dir: str, **kwargs
    ) -> Dict[str, Any]:
        """Process a single video segment.

        Args:
            segment: Dictionary containing segment information including:
                - id: Unique identifier for the segment
                - image: Image asset details
                - video: Video asset details
                - transitions: Transition effects to apply
                - voice_over: Audio details for voice over
                - Any other segment-specific metadata
            temp_dir: Path to a temporary directory for storing intermediate files
            **kwargs: Additional processing parameters

        Returns:
            Dictionary containing processing results, including:
                - path: Path to the processed segment file
                - duration: Duration of the processed segment
                - Any other segment-specific metadata

        Raises:
            ProcessingError: If segment processing fails
        """


@runtime_checkable
class IBatchProcessor(Protocol):
    """Interface for batch processing operations."""

    async def process_batch(self, items: list[Any], **kwargs) -> list[Any]:
        """Process a batch of items.

        Args:
            items: List of items to process
            **kwargs: Additional processing parameters

        Returns:
            List of processed items
        """
