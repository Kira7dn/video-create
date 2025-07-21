"""
Package containing pipeline-related interfaces.

This package defines the core interfaces for the pipeline system,
including IPipelineContext, IPipelineStage, and IPipeline.
"""

from .context import IPipelineContext
from .stage import IPipelineStage
from .pipeline import IPipeline

__all__ = ["IPipelineContext", "IPipelineStage", "IPipeline"]
