"""
Video processing service for creating video clips from segments.

This service implements the IVideoProcessor interface and provides low-level
video processing operations like segment creation and clip concatenation.
"""

import logging
from typing import List, Dict, Optional, Any

from app.core.exceptions import VideoCreationError
from app.services.interfaces import IVideoProcessor
from app.services.resource_manager import ResourceManager
from app.services.processors.audio_processor import AudioProcessor
from app.services.processors.transition_processor import TransitionProcessor
from app.services.processors import ISegmentProcessor, SegmentProcessor
from app.services.processors.concatenation_processor import ConcatenationProcessor
from app.services.processors.base_processor import MetricsCollector

logger = logging.getLogger(__name__)


class VideoProcessingService(IVideoProcessor):
    """Service for processing video clips from segments - now acts as coordinator"""

    def __init__(
        self,
        resource_manager: Optional[ResourceManager] = None,
        segment_processor: Optional[ISegmentProcessor] = None,
        concatenation_processor: Optional[ConcatenationProcessor] = None,
        metrics_collector: Optional[MetricsCollector] = None,
    ):
        """Initialize the video processing service.

        Args:
            resource_manager: Optional resource manager instance
            segment_processor: Optional segment processor instance
            concatenation_processor: Optional concatenation processor instance
            metrics_collector: Optional metrics collector instance
        """
        self.resource_manager = resource_manager or ResourceManager()
        self.metrics_collector = metrics_collector or MetricsCollector()
        self.segment_processor = segment_processor or SegmentProcessor(
            metrics_collector=self.metrics_collector
        )
        self.concatenation_processor = (
            concatenation_processor
            or ConcatenationProcessor(metrics_collector=self.metrics_collector)
        )

    def _create_audio_composition(self, segment: Dict, temp_dir: str) -> Optional[str]:
        return AudioProcessor.create_audio_composition(segment, temp_dir)

    async def create_segment_clip(self, segment: Dict, temp_dir: str) -> str:
        """Tạo một video clip từ một segment.

        Args:
            segment: Dictionary chứa thông tin về segment cần tạo clip
            temp_dir: Thư mục tạm để lưu các file trung gian

        Returns:
            str: Đường dẫn đến file video đã tạo

        Raises:
            VideoCreationError: Nếu có lỗi trong quá trình tạo clip
        """
        try:
            result = await self.segment_processor.process_segment(segment, temp_dir)
            return result["path"]
        except Exception as e:
            raise VideoCreationError(f"Failed to create segment clip: {str(e)}") from e

    def concatenate_clips(
        self,
        video_segments: List[Dict[str, str]],
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
            logger.error("Failed to concatenate clips: %s", e, exc_info=True)
            raise VideoCreationError(f"Failed to concatenate clips: {e}") from e

    def _is_preprocessing_supported(self, transition_type: str) -> bool:
        """Check if transition type can be preprocessed at segment level"""
        return TransitionProcessor.is_preprocessing_supported(transition_type)

    def _apply_transition_in_filter(
        self,
        video_filters: list,
        audio_filters: list,
        transition_type: str,
        duration: float,
    ) -> None:
        """Apply transition-in filter based on type"""
        return TransitionProcessor.apply_transition_in_filter(
            video_filters, audio_filters, transition_type, duration
        )

    def _apply_transition_out_filter(
        self,
        video_filters: list,
        audio_filters: list,
        transition_type: str,
        duration: float,
        start_time: float,
    ) -> None:
        """Apply transition-out filter based on type"""
        return TransitionProcessor.apply_transition_out_filter(
            video_filters, audio_filters, transition_type, duration, start_time
        )
