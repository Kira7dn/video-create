"""
Interface for pipeline stages.

This module defines the IPipelineStage interface that all pipeline stages must implement.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import List

from app.interfaces.pipeline.context import IPipelineContext


class PipelineStageStatus(Enum):
    """Status of pipeline stage execution"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class IPipelineStage(ABC):
    """
    Interface for pipeline stages.

    A pipeline stage is a unit of work that can be executed as part of a pipeline.
    Each stage can read from and write to the pipeline context.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Get the name of the stage.

        Returns:
            str: The name of the stage
        """

    @property
    @abstractmethod
    def status(self) -> PipelineStageStatus:
        """
        Get the current status of the stage.

        Returns:
            PipelineStageStatus: The current status
        """

    @status.setter
    @abstractmethod
    def status(self, value: PipelineStageStatus) -> None:
        """
        Set the status of the stage.

        Args:
            value: The new status
        """

    @property
    @abstractmethod
    def required_inputs(self) -> List[str]:
        """
        Get the list of required input keys.

        Returns:
            List[str]: List of required input keys
        """

    @abstractmethod
    async def execute(self, context: IPipelineContext) -> IPipelineContext:
        """
        Execute the stage with the given context.

        Args:
            context: The pipeline context containing input data

        Returns:
            Updated pipeline context with stage results

        Raises:
            ProcessingError: If the stage fails to execute
        """

    @abstractmethod
    def validate_inputs(self, context: IPipelineContext) -> bool:
        """
        Validate that all required inputs are present in the context.

        Args:
            context: The pipeline context to validate

        Returns:
            bool: True if all required inputs are present, False otherwise
        """

    @abstractmethod
    def can_skip(self, context: IPipelineContext) -> bool:
        """
        Check if this stage can be skipped based on the current context.

        Args:
            context: The pipeline context to check

        Returns:
            bool: True if the stage can be skipped, False otherwise
        """
