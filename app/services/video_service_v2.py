"""
Refactored video creation service with improved architecture
"""

import os
import uuid
import logging
import time
from typing import List, Dict, Any, Optional
from pathlib import Path

from app.core.exceptions import VideoCreationError, DownloadError, ProcessingError
from app.config.settings import settings
from app.services.resource_manager import (
    managed_resources,
    managed_temp_directory,
    cleanup_old_temp_directories,
)
from app.services.download_service import DownloadService
from app.services.video_processing_service import VideoProcessingService

# Import new processors
from app.services.processors.base_processor import MetricsCollector
from app.services.processors.validation_processor import create_video_request_validator
from app.services.processors.concatenation_processor import ConcatenationProcessor
from app.services.processors.batch_processor import SegmentBatchProcessor
from app.services.processors.pipeline import (
    VideoPipeline, PipelineContext, FunctionPipelineStage
)

logger = logging.getLogger(__name__)


class VideoCreationServiceV2:
    """
    Refactored video creation service with improved separation of concerns
    """

    def __init__(self):
        self.metrics_collector = MetricsCollector()
        self.validator = create_video_request_validator(self.metrics_collector)
        self.concatenation_processor = ConcatenationProcessor(self.metrics_collector)
        self._ensure_output_directory()
        self._cleanup_old_directories()

    def _ensure_output_directory(self):
        """Ensure output directory exists"""
        output_dir = Path(settings.output_directory)
        output_dir.mkdir(parents=True, exist_ok=True)

    def _cleanup_old_directories(self):
        """Clean up old temporary directories on startup"""
        try:
            cleanup_old_temp_directories()
        except Exception as e:
            logger.warning(f"Failed to cleanup old temp directories on startup: {e}")

    async def create_video_from_json(self, json_data: Dict) -> str:
        """
        Create a video from JSON data with improved resource management and pipeline processing
        """
        # Reset metrics for new request
        self.metrics_collector = MetricsCollector()
        
        # Validate input data first
        validation_result = self.validator.validate(json_data)
        if not validation_result.is_valid:
            error_msg = f"Validation failed: {'; '.join(validation_result.errors)}"
            logger.error(error_msg)
            raise VideoCreationError(error_msg)

        video_id = uuid.uuid4().hex

        # Use async context manager for temporary directory
        async with managed_temp_directory() as temp_dir:
            try:
                return await self._process_video_creation_pipeline(json_data, temp_dir, video_id)
            except DownloadError as e:
                logger.error(f"Asset download failed: {e}", exc_info=True)
                raise VideoCreationError(f"Asset download failed: {e}") from e
            except ProcessingError as e:
                logger.error(f"Video processing failed: {e}", exc_info=True)
                raise VideoCreationError(f"Video processing failed: {e}") from e
            except Exception as e:
                logger.error(f"Unexpected error in video creation: {e}", exc_info=True)
                raise VideoCreationError(f"Video creation failed: {e}") from e
            finally:
                # Log processing summary
                self._log_processing_summary()

    def _log_processing_summary(self):
        """Log processing metrics summary"""
        try:
            summary = self.metrics_collector.get_summary()
            logger.info("🎬 Video Creation Summary:")
            logger.info(f"   Total Duration: {summary['total_duration']:.2f}s")
            logger.info(f"   Total Items Processed: {summary['total_items']}")
            
            if summary['failed_stages']:
                logger.warning(f"   Failed Stages: {', '.join(summary['failed_stages'])}")
            
            for stage in summary['stages']:
                status_emoji = "✅" if stage['success'] else "❌"
                logger.info(f"   {status_emoji} {stage['stage']}: {stage['duration']:.2f}s ({stage['items_processed']} items)")
        except Exception as e:
            logger.warning(f"Failed to log processing summary: {e}")

    async def _process_video_creation_pipeline(
        self, json_data: Dict, temp_dir: str, video_id: str
    ) -> str:
        """Process video creation using pipeline pattern"""
        # Create pipeline context
        context = PipelineContext(
            data={
                "json_data": json_data,
                "segments": json_data.get("segments", []),
                "transitions": json_data.get("transitions", []),
                "background_music": json_data.get("background_music")
            },
            temp_dir=temp_dir,
            video_id=video_id,
            metadata={"start_time": time.time()}
        )

        # Build and execute pipeline
        pipeline = self._build_video_pipeline()
        result_context = await pipeline.execute(context)

        # Return final video path
        final_video_path = result_context.get("final_video_path")
        if not final_video_path or not os.path.exists(final_video_path):
            raise VideoCreationError("Final video was not created successfully")

        return final_video_path

    def _build_video_pipeline(self) -> VideoPipeline:
        """Build the video processing pipeline"""
        pipeline = VideoPipeline(self.metrics_collector)

        # Stage 1: Download assets
        pipeline.add_function_stage(
            name="download_assets",
            func=self._download_assets_stage,
            output_key="download_results",
            required_inputs=["json_data"]
        )

        # Stage 2: Process segments
        pipeline.add_function_stage(
            name="process_segments", 
            func=self._process_segments_stage,
            output_key="processed_segments",
            required_inputs=["segments", "download_results"]
        )

        # Stage 3: Create segment clips
        pipeline.add_function_stage(
            name="create_segment_clips",
            func=self._create_segment_clips_stage,
            output_key="clip_paths",
            required_inputs=["processed_segments"]
        )

        # Stage 4: Concatenate final video
        pipeline.add_function_stage(
            name="concatenate_video",
            func=self._concatenate_video_stage,
            output_key="final_video_path",
            required_inputs=["clip_paths", "transitions", "background_music"]
        )

        return pipeline

    async def _download_assets_stage(self, context: PipelineContext) -> tuple:
        """Pipeline stage for downloading assets"""
        json_data = context.get("json_data")
        
        try:
            async with DownloadService() as download_service:
                segment_results, background_music_result = await download_service.batch_download_segments(
                    json_data, context.temp_dir
                )
                return segment_results, background_music_result
        except Exception as e:
            raise DownloadError(f"Failed to download assets: {e}") from e

    def _process_segments_stage(self, context: PipelineContext) -> List[Dict]:
        """Pipeline stage for processing segments with download results"""
        segments = context.get("segments")
        download_results = context.get("download_results")
        
        if not download_results or len(download_results) != 2:
            raise ProcessingError("Invalid download results format")
        
        segment_results, _ = download_results
        
        if len(segments) != len(segment_results):
            raise ProcessingError(
                f"Segment count mismatch: {len(segments)} vs {len(segment_results)}"
            )

        processed_segments = []
        for segment, download_result in zip(segments, segment_results):
            processed_segment = segment.copy()
            
            # Merge asset objects into segment
            for asset_type, asset_obj in download_result.items():
                processed_segment[asset_type] = asset_obj

            processed_segments.append(processed_segment)

        return processed_segments

    def _create_segment_clips_stage(self, context: PipelineContext) -> List[Dict[str, str]]:
        """Pipeline stage for creating individual segment clips"""
        processed_segments = context.get("processed_segments")
        
        try:
            with managed_resources() as resource_manager:
                video_processor = VideoProcessingService(resource_manager)
                
                # Use batch processor for segment creation
                from app.services.processors.segment_processor import SegmentProcessor
                batch_processor = SegmentBatchProcessor(
                    processor_func=SegmentProcessor.create_segment_clip,
                    metrics_collector=self.metrics_collector
                )
                
                clip_paths = batch_processor.process_batch(
                    processed_segments, 
                    temp_dir=context.temp_dir
                )
                
                return clip_paths
                
        except Exception as e:
            raise ProcessingError(f"Failed to create segment clips: {e}") from e

    def _concatenate_video_stage(self, context: PipelineContext) -> str:
        """Pipeline stage for concatenating final video"""
        clip_paths = context.get("clip_paths")
        transitions = context.get("transitions")
        download_results = context.get("download_results")
        
        if not download_results or len(download_results) != 2:
            raise ProcessingError("Background music download result not found")
        
        _, background_music_result = download_results

        # Generate output path
        output_path = self._get_output_path(context.video_id)
        
        # Concatenate clips
        final_clip_path = self.concatenation_processor.concatenate_clips(
            video_segments=clip_paths,
            output_path=output_path,
            temp_dir=context.temp_dir,
            background_music=background_music_result,
            transitions=transitions
        )
        
        logger.info(f"✅ Created video: {final_clip_path}")
        return final_clip_path

    def _get_output_path(self, video_id: str) -> str:
        """Generate output path for video"""
        filename = f"final_video_{video_id}.mp4"
        return os.path.join(settings.output_directory, filename)


# Create service instance
video_service_v2 = VideoCreationServiceV2()
