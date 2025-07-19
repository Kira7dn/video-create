"""
Video processing interfaces.
"""

from typing import Dict, Any, List, Optional
from typing_extensions import Protocol, runtime_checkable


@runtime_checkable
class IVideoProcessor(Protocol):
    """Interface for video processing operations."""

    async def create_segment_clip(self, segment: Dict, temp_dir: str) -> str:
        """Create a video clip from a single segment.

        Args:
            segment: Dictionary containing segment information
            temp_dir: Temporary directory for intermediate files

        Returns:
            Path to the created video clip

        Raises:
            VideoCreationError: If there's an error creating the segment clip
        """

    def concatenate_clips(
        self,
        video_segments: List[Dict[str, str]],
        output_path: str,
        temp_dir: str,
        transitions: Optional[list] = None,
        background_music: Optional[dict] = None,
        default_transition_type: str = "fade",
        default_transition_duration: float = 1.0,
    ) -> str:
        """Concatenate multiple video clips into a single video.

        Args:
            video_segments: List of segment dictionaries with 'path' and 'duration'
            output_path: Path where the final video will be saved
            temp_dir: Directory for temporary files
            transitions: List of transition configurations
            background_music: Background music configuration
            default_transition_type: Default transition type if not specified
            default_transition_duration: Default transition duration in seconds

        Returns:
            Path to the concatenated video file
        """


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
