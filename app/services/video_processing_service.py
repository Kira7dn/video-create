"""
Video processing service for creating video clips from segments
Refactored to work with new processor architecture
"""

import logging
from typing import List, Dict, Optional, Any
from app.core.exceptions import VideoCreationError
from app.services.resource_manager import ResourceManager
from app.services.processors.audio_processor import AudioProcessor
from app.services.processors.transition_processor import TransitionProcessor
from app.services.processors.segment_processor import SegmentProcessor
from app.services.processors.concatenation_processor import ConcatenationProcessor

logger = logging.getLogger(__name__)


class VideoProcessingService:
    """Service for processing video clips from segments - now acts as coordinator"""

    def __init__(self, resource_manager: Optional[ResourceManager] = None):
        self.resource_manager = resource_manager or ResourceManager()
        self.concatenation_processor = ConcatenationProcessor()

    def _create_audio_composition(
        self, segment: Dict, temp_dir: str
    ) -> Optional[str]:
        return AudioProcessor.create_audio_composition(segment, temp_dir)

    def create_segment_clip(self, segment: Dict, temp_dir: str) -> str:
        return SegmentProcessor.create_segment_clip(segment, temp_dir)

    def create_multiple_segment_clips(
        self, segments: List[Dict], temp_dir: str
    ) -> List[Dict[str, str]]:
        """Create multiple segment clips and return list of dicts with id and file path (for transition pipeline)"""
        clip_infos = []
        total_segments = len(segments)
        for i, segment in enumerate(segments):
            try:
                clip_path = self.create_segment_clip(segment, temp_dir)
                clip_infos.append({"id": segment.get("id", str(i)), "path": clip_path})
                # Log progress every 20% for better performance
                if (i + 1) % max(1, total_segments // 5) == 0 or i == total_segments - 1:
                    logger.info(f"✅ Created segments {i+1}/{total_segments}")
            except Exception as e:
                logger.error(f"❌ Failed to create segment {i+1}: {e}")
                raise
        return clip_infos

    def concatenate_clips(
        self, video_segments: List[Dict[str, str]],
        output_path: str,
        temp_dir: str,
        transitions: Optional[list] = None,
        background_music: Optional[dict] = None,
        default_transition_type: str = "fade",
        default_transition_duration: float = 1.0,
    ) -> Any:
        """Concatenate video clips using the new concatenation processor"""
        try:
            return self.concatenation_processor.concatenate_clips(
                video_segments=video_segments,
                output_path=output_path,
                temp_dir=temp_dir,
                transitions=transitions,
                background_music=background_music,
                default_transition_type=default_transition_type,
                default_transition_duration=default_transition_duration,
            )
        except Exception as e:
            logger.error(f"Failed to concatenate clips: {e}", exc_info=True)
            raise VideoCreationError(f"Failed to concatenate clips: {e}") from e

    def _is_preprocessing_supported(self, transition_type: str) -> bool:
        """Check if transition type can be preprocessed at segment level"""
        return TransitionProcessor.is_preprocessing_supported(transition_type)

    def _apply_transition_in_filter(self, video_filters: list, audio_filters: list, transition_type: str, duration: float) -> None:
        """Apply transition-in filter based on type"""
        return TransitionProcessor.apply_transition_in_filter(video_filters, audio_filters, transition_type, duration)

    def _apply_transition_out_filter(self, video_filters: list, audio_filters: list, transition_type: str, duration: float, start_time: float) -> None:
        """Apply transition-out filter based on type"""
        return TransitionProcessor.apply_transition_out_filter(video_filters, audio_filters, transition_type, duration, start_time)
