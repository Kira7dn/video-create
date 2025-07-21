"""
Module chứa các pipeline xử lý video.

Các thành phần chính:
- VideoPipeline: Core pipeline implementation
- create_video_creation_pipeline: Factory function để tạo video creation pipeline
- get_video_creation_stages: Lấy danh sách các stages mặc định cho video creation
"""

from .context import DefaultPipelineContext
from .stages import (
    BasePipelineStage,
    ProcessorPipelineStage,
    FunctionPipelineStage,
)
from .video_pipeline import VideoPipeline
from .video_creation_pipeline import create_video_creation_pipeline
from .pipeline_config import get_video_creation_stages

# For backward compatibility
PipelineContext = DefaultPipelineContext
PipelineStage = BasePipelineStage

__all__ = [
    "DefaultPipelineContext",
    "PipelineContext",  # Alias for backward compatibility
    "BasePipelineStage",
    "PipelineStage",  # Alias for backward compatibility
    "ProcessorPipelineStage",
    "FunctionPipelineStage",
    "VideoPipeline",
    "create_video_creation_pipeline",
    "get_video_creation_stages",
]
