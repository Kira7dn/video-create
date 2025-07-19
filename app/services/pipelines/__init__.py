"""
Module chứa các pipeline xử lý video.

Các thành phần chính:
- Pipeline: Core pipeline implementation
- create_video_creation_pipeline: Factory function để tạo video creation pipeline
- get_video_creation_stages: Lấy danh sách các stages mặc định cho video creation
"""

from .pipeline import (
    PipelineContext,
    PipelineStage,
    ProcessorPipelineStage,
    FunctionPipelineStage,
    VideoPipeline,
    ConditionalStage,
    ParallelStage,
    PipelineStageStatus,
)
from .video_creation_pipeline import create_video_creation_pipeline
from .pipeline_config import get_video_creation_stages

__all__ = [
    'PipelineContext',
    'PipelineStage',
    'ProcessorPipelineStage',
    'FunctionPipelineStage',
    'VideoPipeline',
    'ConditionalStage',
    'ParallelStage',
    'PipelineStageStatus',
    'create_video_creation_pipeline',
    'get_video_creation_stages'
]
