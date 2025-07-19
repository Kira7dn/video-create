"""Audio processing interfaces."""

from typing import Dict, Optional
from typing_extensions import Protocol, runtime_checkable


@runtime_checkable
class IAudioProcessor(Protocol):
    """Interface for audio processing operations."""

    @staticmethod
    def create_audio_composition(segment: Dict, temp_dir: str) -> Optional[str]:
        """Create audio composition with voice over, delays, and normalization.

        Args:
            segment: Dictionary containing segment data with voice_over configuration
            temp_dir: Temporary directory path for output files

        Returns:
            Path to the generated audio file, or None if no voice over
        """
