"""
Interface for pipeline.

This module defines the IPipeline interface that all pipeline implementations must follow.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, TypeVar, Union

from app.interfaces.pipeline.context import IPipelineContext
from app.interfaces.pipeline.stage import IPipelineStage
from app.services.processors.core.base_processor import AsyncProcessor, SyncProcessor

# Type variables for generic typing
T = TypeVar("T")


class IPipeline(ABC):
    """
    Interface for pipeline implementations.

    A pipeline is a sequence of stages that process data through a series of steps.
    """

    @property
    @abstractmethod
    def stages(self) -> List[IPipelineStage]:
        """
        Get all stages in the pipeline.

        Returns:
            List of pipeline stages
        """

    @abstractmethod
    def get_stage(self, name: str) -> Optional[IPipelineStage]:
        """
        Get a stage by name.

        Args:
            name: Name of the stage to get

        Returns:
            The stage if found, None otherwise
        """

    @abstractmethod
    def add_stage(self, stage: IPipelineStage) -> "IPipeline":
        """
        Add a stage to the pipeline.

        Args:
            stage: The stage to add

        Returns:
            Self for method chaining
        """

    @abstractmethod
    def add_processor_stage(
        self,
        name: str,
        processor: Union[SyncProcessor, AsyncProcessor],
        input_key: str,
        output_key: str,
        required_inputs: Optional[List[str]] = None,
    ) -> "IPipeline":
        """
        Add a processor stage to the pipeline.

        Args:
            name: Name of the stage
            processor: The processor to use
            input_key: Key to get input data from context
            output_key: Key to store output data in context
            required_inputs: List of required input keys

        Returns:
            Self for method chaining
        """

    @abstractmethod
    def add_function_stage(
        self,
        name: str,
        func: Optional[callable] = None,
        func_name: Optional[str] = None,
        output_key: Optional[str] = None,
        required_inputs: Optional[List[str]] = None,
    ) -> "IPipeline":
        """
        Add a function stage to the pipeline.

        Args:
            name: Name of the stage
            func: Processing function (can be provided later via func attribute)
            func_name: Function name to bind later (if func is not provided)
            output_key: Key to store the result in context
            required_inputs: List of required input keys

        Returns:
            Self for method chaining
        """

    @abstractmethod
    async def execute(self, context: IPipelineContext) -> Dict[str, Any]:
        """
        Execute the pipeline with the given context.

        Args:
            context: The pipeline context containing input data

        Returns:
            Dictionary containing execution results and metrics
        """

    @abstractmethod
    def get_stage_summary(self) -> List[Dict[str, Any]]:
        """
        Get summary of all stages in the pipeline.

        Returns:
            List of dictionaries containing stage summaries with name, status,
            duration, and items_processed for each stage in the pipeline.
        """
