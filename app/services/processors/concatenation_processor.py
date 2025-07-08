"""
Concatenation processor for combining video segments
"""

import os
from typing import List, Dict, Optional, Any
from app.services.processors.base_processor import BaseProcessor, ProcessingStage, MetricsCollector
from app.core.exceptions import VideoCreationError, ProcessingError
from utils.video_utils import ffmpeg_concat_videos
import logging

logger = logging.getLogger(__name__)


class ConcatenationProcessor(BaseProcessor):
    """Handles video concatenation with transitions and background music"""
    
    def __init__(self, metrics_collector: Optional[MetricsCollector] = None):
        super().__init__(metrics_collector)
    
    def process(self, input_data: Dict[str, Any], **kwargs) -> str:
        """Process concatenation request"""
        return self.concatenate_clips(**input_data, **kwargs)
    
    def concatenate_clips(
        self,
        video_segments: List[Dict[str, str]],
        output_path: str,
        temp_dir: str,
        transitions: Optional[List[Dict]] = None,
        background_music: Optional[Dict] = None,
        default_transition_type: str = "fade",
        default_transition_duration: float = 1.0,
        **kwargs
    ) -> str:
        """
        Concatenate video clips using ffmpeg with transitions and background music
        
        Args:
            video_segments: List of video segment info dicts with 'id' and 'path'
            output_path: Path for the final output video
            temp_dir: Temporary directory for processing
            transitions: List of transition configurations
            background_music: Background music configuration
            default_transition_type: Default transition type if not specified
            default_transition_duration: Default transition duration if not specified
            
        Returns:
            Path to the final concatenated video
            
        Raises:
            ProcessingError: If concatenation fails
        """
        metric = self._start_processing(ProcessingStage.CONCATENATION)
        
        try:
            # Validate inputs
            self._validate_concatenation_inputs(video_segments, output_path, temp_dir)
            
            # Log concatenation start
            self.logger.info(f"Starting concatenation of {len(video_segments)} segments")
            self.logger.info(f"Output path: {output_path}")
            
            # Perform concatenation using existing utility
            ffmpeg_concat_videos(
                video_segments=video_segments,
                output_path=output_path,
                temp_dir=temp_dir,
                transitions=transitions,
                background_music=background_music,
                logger=self.logger,
                default_transition_type=default_transition_type,
                default_transition_duration=default_transition_duration,
            )
            
            # Verify output exists
            if not os.path.exists(output_path):
                raise ProcessingError(f"Concatenation completed but output file not found: {output_path}")
            
            # Get file size for metrics
            file_size = os.path.getsize(output_path)
            
            self.logger.info(f"✅ Video concatenation completed successfully")
            self.logger.info(f"   Output: {output_path}")
            self.logger.info(f"   Size: {file_size / (1024*1024):.2f} MB")
            
            self._end_processing(
                metric, 
                success=True, 
                items_processed=len(video_segments)
            )
            
            return output_path
            
        except Exception as e:
            error_msg = f"Failed to concatenate video clips: {e}"
            self.logger.error(error_msg, exc_info=True)
            self._end_processing(metric, success=False, error_message=error_msg)
            raise ProcessingError(error_msg) from e
    
    def _validate_concatenation_inputs(
        self, 
        video_segments: List[Dict[str, str]], 
        output_path: str, 
        temp_dir: str
    ):
        """Validate concatenation input parameters"""
        if not video_segments:
            raise ProcessingError("No video segments provided for concatenation")
        
        if not output_path:
            raise ProcessingError("Output path not specified")
        
        if not temp_dir or not os.path.exists(temp_dir):
            raise ProcessingError(f"Temporary directory does not exist: {temp_dir}")
        
        # Validate each video segment
        for i, segment in enumerate(video_segments):
            if not isinstance(segment, dict):
                raise ProcessingError(f"Video segment {i} must be a dictionary")
            
            if "path" not in segment:
                raise ProcessingError(f"Video segment {i} missing 'path' field")
            
            segment_path = segment["path"]
            if not segment_path or not os.path.exists(segment_path):
                raise ProcessingError(f"Video segment {i} file not found: {segment_path}")
            
            # Check file is not empty
            if os.path.getsize(segment_path) == 0:
                raise ProcessingError(f"Video segment {i} file is empty: {segment_path}")
        
        # Ensure output directory exists
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir, exist_ok=True)
            except Exception as e:
                raise ProcessingError(f"Failed to create output directory {output_dir}: {e}")
    
    def prepare_segments_for_concatenation(
        self, 
        segments: List[Dict], 
        clip_paths: List[str]
    ) -> List[Dict[str, str]]:
        """
        Prepare segments for concatenation by combining metadata with file paths
        
        Args:
            segments: Original segment metadata
            clip_paths: List of generated clip file paths
            
        Returns:
            List of segment info dicts suitable for concatenation
        """
        if len(segments) != len(clip_paths):
            raise ProcessingError(
                f"Segment count mismatch: {len(segments)} segments vs {len(clip_paths)} clips"
            )
        
        video_segments = []
        for segment, clip_path in zip(segments, clip_paths):
            segment_info = {
                "id": segment.get("id", "unknown"),
                "path": clip_path
            }
            
            # Add additional metadata if needed
            if "duration" in segment:
                segment_info["duration"] = segment["duration"]
            
            video_segments.append(segment_info)
        
        return video_segments
    
    def estimate_output_size(self, video_segments: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Estimate output video size and duration
        
        Args:
            video_segments: List of video segment info
            
        Returns:
            Dictionary with size and duration estimates
        """
        total_size = 0
        total_files = 0
        
        for segment in video_segments:
            segment_path = segment.get("path")
            if segment_path and os.path.exists(segment_path):
                total_size += os.path.getsize(segment_path)
                total_files += 1
        
        return {
            "estimated_size_mb": total_size / (1024 * 1024),
            "total_input_files": total_files,
            "average_file_size_mb": (total_size / total_files / (1024 * 1024)) if total_files > 0 else 0
        }
