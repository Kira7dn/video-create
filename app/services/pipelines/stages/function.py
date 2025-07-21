"""
FunctionPipelineStage implementation.

This module provides a pipeline stage that wraps a function (sync or async).
"""

import asyncio
import logging
from typing import Any, Callable, List, Optional

from app.core.exceptions import ProcessingError
from app.interfaces.pipeline.context import IPipelineContext
from app.services.pipelines.stages.base import BasePipelineStage

logger = logging.getLogger(__name__)


class FunctionPipelineStage(BasePipelineStage):
    """
    Pipeline stage that wraps a function.

    This stage executes a function with the pipeline context and optionally
    stores the result back into the context at the specified output key.
    """

    def __init__(
        self,
        name: str,
        func: Optional[Callable[[IPipelineContext], Any]] = None,
        func_name: Optional[str] = None,
        output_key: Optional[str] = None,
        required_inputs: Optional[List[str]] = None,
    ):
        """
        Initialize a function pipeline stage.

        Args:
            name: A descriptive name for this stage
            func: The function to execute (can be sync or async)
            func_name: Name of the function (for debugging)
            output_key: If provided, store the function's return value in the context with this key
            required_inputs: List of input keys required by this stage
        """
        super().__init__(name, required_inputs or [])
        self.func = func
        self.func_name = func_name or (func.__name__ if func else None)
        self.output_key = output_key

        # Log function type for debugging
        is_async = func and asyncio.iscoroutinefunction(func)
        self.logger.debug(
            "Initialized %s function stage", "async" if is_async else "sync"
        )

    async def _execute_impl(self, context: IPipelineContext) -> IPipelineContext:
        """
        Execute the function with the pipeline context.

        Args:
            context: The pipeline context

        Returns:
            Updated pipeline context with function result (if output_key is set)

        Raises:
            ProcessingError: If function is not set or execution fails
        """
        if self.func is None:
            func_name = self.func_name or "unnamed_function"
            raise ProcessingError(f"Function '{func_name}' is not set")

        try:
            # Execute function (sync or async)
            if asyncio.iscoroutinefunction(self.func):
                self.logger.debug("Executing async function")
                result = await self.func(context)
            else:
                self.logger.debug("Executing sync function")
                result = self.func(context)

                # Handle case where sync function returns a coroutine
                if asyncio.iscoroutine(result):
                    self.logger.debug("Function returned a coroutine, awaiting...")
                    result = await result

            # Store result if output_key is provided
            if self.output_key is not None and result is not None:
                context.set(self.output_key, result)
                self.logger.debug("Stored function result at key: %s", self.output_key)

            return context

        except Exception as e:
            func_name = self.func_name or self.func.__name__
            error_msg = f"Function '{func_name}' failed: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            raise ProcessingError(error_msg) from e
