"""
Interface for pipeline stages
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.interfaces.pipeline_context import IPipelineContext


class PipelineStageStatus(Enum):
    """Status of pipeline stage execution"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class IPipelineStage(ABC):
    """
    Interface defining the contract for pipeline stages.

    Pipeline stages are individual processing units that can be composed together
    to form a complete pipeline. Each stage processes the context and passes it
    to the next stage in the pipeline.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Get the name of the stage

        Returns:
            str: The name of the stage
        """
        pass

    @property
    @abstractmethod
    def status(self) -> "PipelineStageStatus":
        """
        Get the current status of the stage

        Returns:
            PipelineStageStatus: The current status
        """
        pass

    @status.setter
    @abstractmethod
    def status(self, value: "PipelineStageStatus") -> None:
        """
        Set the status of the stage

        Args:
            value: The new status
        """
        pass

    @property
    @abstractmethod
    def required_inputs(self) -> List[str]:
        """
        Get list of required input keys that must be present in the context

        Returns:
            List[str]: List of required input keys
        """
        pass

    @abstractmethod
    async def execute(self, context: "IPipelineContext") -> "IPipelineContext":
        """
        Execute the pipeline stage

        Args:
            context: The pipeline context containing input data

        Returns:
            Updated pipeline context with stage results

        Raises:
            ProcessingError: If the stage fails to execute
        """
        pass

    @abstractmethod
    def validate_inputs(self, context: "IPipelineContext") -> bool:
        """
        Validate that all required inputs are present in the context

        Args:
            context: The pipeline context to validate

        Returns:
            bool: True if all required inputs are present, False otherwise

        Note:
            This should be called before execute() to ensure all required
            inputs are available
        """
        pass

    @abstractmethod
    def can_skip(self, context: "IPipelineContext") -> bool:
        """
        Check if this stage can be skipped based on the current context

        Args:
            context: The pipeline context to check

        Returns:
            bool: True if the stage can be skipped, False otherwise

        Note:
            This is useful for conditional execution of stages
        """
        pass
