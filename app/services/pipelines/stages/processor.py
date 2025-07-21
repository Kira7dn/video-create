"""
ProcessorPipelineStage implementation.

This module provides a pipeline stage that wraps a processor (sync or async).
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Union

from app.core.exceptions import ProcessingError
from app.interfaces.pipeline.context import IPipelineContext
from app.services.pipelines.stages.base import BasePipelineStage
from app.services.processors.core.base_processor import AsyncProcessor, SyncProcessor

logger = logging.getLogger(__name__)


class ProcessorPipelineStage(BasePipelineStage):
    """
    Pipeline stage that wraps a processor (synchronous or asynchronous).

    This stage executes a processor with input from the context and stores
    the result back into the context at the specified output key.
    """

    def __init__(
        self,
        name: str,
        processor: Union[SyncProcessor, AsyncProcessor],
        input_key: str,
        output_key: str,
        required_inputs: Optional[List[str]] = None,
    ):
        """
        Initialize a processor pipeline stage.

        Args:
            name: A descriptive name for this stage
            processor: The processor to execute (can be sync or async)
            input_key: Key to retrieve input data from the context
            output_key: Key to store the processor's output in the context
            required_inputs: Additional required input keys beyond the input_key
        """
        # Include input_key in required_inputs if not already present
        all_required = [input_key] + (required_inputs or [])
        super().__init__(name, list(dict.fromkeys(all_required)))  # Remove duplicates

        self.processor = processor
        self.input_key = input_key
        self.output_key = output_key

        # Log processor type for debugging
        is_async = asyncio.iscoroutinefunction(processor.process)
        self.logger.debug(
            "Initialized %s processor stage", "async" if is_async else "sync"
        )

    async def _execute_impl(self, context: IPipelineContext) -> IPipelineContext:
        """
        Execute the processor with input from context and store the result.

        Args:
            context: The pipeline context containing input data

        Returns:
            Updated pipeline context with processor output

        Raises:
            ProcessingError: If processor execution fails or input is invalid
        """
        self.logger.debug("Executing processor with input key: %s", self.input_key)

        # Get input data from context
        input_data = context.get(self.input_key)
        if input_data is None:
            raise ProcessingError(f"No input data found for key '{self.input_key}'")

        try:
            # Prepare kwargs for processor
            kwargs: Dict[str, Any] = {"context": context}
            self.logger.debug("Input data type: %s", type(input_data).__name__)

            # Execute processor (sync or async)
            if asyncio.iscoroutinefunction(self.processor.process):
                self.logger.debug("Executing async processor")
                result = await self.processor.process(input_data, **kwargs)
            else:
                self.logger.debug("Executing sync processor")
                result = self.processor.process(input_data, **kwargs)

                # Handle case where sync processor returns a coroutine
                if asyncio.iscoroutine(result):
                    self.logger.debug("Processor returned a coroutine, awaiting...")
                    result = await result

            # Store result if not None
            if result is not None:
                context.set(self.output_key, result)
                self.logger.debug("Stored result at key: %s", self.output_key)
            else:
                self.logger.warning("Processor returned None, no result stored")

            return context

        except Exception as e:
            error_msg = f"Processor '{self.name}' failed: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            raise ProcessingError(error_msg) from e
