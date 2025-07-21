"""
Base implementation of IPipelineStage.

This module provides the base PipelineStage class that can be extended
by other stage implementations.
"""

import logging
from abc import ABC, abstractmethod
from typing import List, Optional

from app.interfaces.pipeline.context import IPipelineContext
from app.interfaces.pipeline.stage import IPipelineStage, PipelineStageStatus
from app.core.exceptions import ProcessingError


class BasePipelineStage(IPipelineStage, ABC):
    """
    Base implementation of IPipelineStage that can be used directly or subclassed.
    """

    def __init__(self, name: str, required_inputs: Optional[List[str]] = None):
        """
        Initialize a new pipeline stage.

        Args:
            name: The name of the stage (must be unique within the pipeline)
            required_inputs: List of input keys required by this stage
        """
        self._name = name
        self._required_inputs = required_inputs or []
        self._status = PipelineStageStatus.PENDING
        self.logger = logging.getLogger(f"Pipeline.{name}")

    @property
    def name(self) -> str:
        """Get the name of the stage."""
        return self._name

    @property
    def status(self) -> PipelineStageStatus:
        """Get the current status of the stage."""
        return self._status

    @status.setter
    def status(self, value: PipelineStageStatus) -> None:
        """Set the status of the stage."""
        self._status = value
        self.logger.debug("Stage status changed to %s", value)

    @property
    def required_inputs(self) -> List[str]:
        """Get the list of required input keys."""
        return self._required_inputs

    async def execute(self, context: IPipelineContext) -> IPipelineContext:
        """
        Execute the stage with the given context.

        This method handles common execution logic like status updates and error handling.
        Subclasses should implement _execute_impl() for stage-specific logic.

        Args:
            context: The pipeline context

        Returns:
            Updated pipeline context

        Raises:
            ProcessingError: If stage execution fails
        """
        self.status = PipelineStageStatus.RUNNING
        self.logger.debug("Starting stage execution")

        try:
            # Validate inputs before execution
            if not self.validate_inputs(context):
                missing = [
                    key for key in self.required_inputs if key not in context.data
                ]
                raise ProcessingError(f"Missing required inputs: {', '.join(missing)}")

            # Check if stage can be skipped
            if self.can_skip(context):
                self.status = PipelineStageStatus.SKIPPED
                self.logger.info("Stage skipped")
                return context

            # Execute the stage-specific implementation
            result = await self._execute_impl(context)
            self.status = PipelineStageStatus.COMPLETED
            self.logger.debug("Stage completed successfully")
            return result

        except Exception as e:
            self.status = PipelineStageStatus.FAILED
            error_msg = f"Stage '{self.name}' failed: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            raise ProcessingError(error_msg) from e

    @abstractmethod
    async def _execute_impl(self, context: IPipelineContext) -> IPipelineContext:
        """
        Implementation of stage execution logic.

        Subclasses must implement this method with their specific logic.

        Args:
            context: The pipeline context

        Returns:
            Updated pipeline context

        Raises:
            Exception: If execution fails
        """

    def validate_inputs(self, context: IPipelineContext) -> bool:
        """
        Validate that all required inputs are present in the context.

        Args:
            context: The pipeline context to validate

        Returns:
            bool: True if all required inputs are present, False otherwise
        """
        if not self.required_inputs:
            return True

        return all(key in context.data for key in self.required_inputs)

    def can_skip(self, context: IPipelineContext) -> bool:
        """
        Check if this stage can be skipped based on the current context.

        Base implementation always returns False. Subclasses can override this
        to implement custom skip logic.

        Args:
            context: The pipeline context to check

        Returns:
            bool: True if the stage can be skipped, False otherwise
        """
        return False
