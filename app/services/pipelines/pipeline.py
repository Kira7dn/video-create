"""
Pipeline pattern implementation for video processing workflow.

This module contains the core pipeline implementation including:
- PipelineContext: Context object passed through pipeline stages
- PipelineStage: Abstract base class for all pipeline stages
- ProcessorPipelineStage: Stage that wraps a processor
- FunctionPipelineStage: Stage that wraps a function
- VideoPipeline: Main pipeline implementation
- ConditionalStage: Stage with conditional execution
- ParallelStage: Stage that executes multiple stages in parallel
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union, cast

from app.core.exceptions import ProcessingError
from app.interfaces import (
    IPipeline,
    IPipelineContext,
    IPipelineStage,
    PipelineStageStatus,
)
from app.services.processors.core.base_processor import AsyncProcessor, SyncProcessor
from app.services.processors.core.metrics import MetricsCollector

logger = logging.getLogger(__name__)

# Define type variables for better type hints
T = TypeVar("T")
ContextT = TypeVar("ContextT", bound=IPipelineContext)
StageT = TypeVar("StageT", bound=IPipelineStage)


class PipelineStageStatus(Enum):
    """Status of pipeline stage execution"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PipelineContext(IPipelineContext):
    """
    Implementation of IPipelineContext that carries data between pipeline stages.
    """

    _data: Dict[str, Any] = field(default_factory=dict)
    _temp_dir: Optional[Path] = None
    _video_id: Optional[str] = None
    _metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def data(self) -> Dict[str, Any]:
        """Get the context data dictionary"""
        return self._data

    @data.setter
    def data(self, value: Dict[str, Any]) -> None:
        """Set the context data dictionary"""
        self._data = value or {}

    @property
    def temp_dir(self) -> Optional[Path]:
        """Get the temporary directory path"""
        return self._temp_dir

    @temp_dir.setter
    def temp_dir(self, value: Optional[Union[str, Path]]) -> None:
        """Set the temporary directory path"""
        self._temp_dir = Path(value) if value else None

    @property
    def video_id(self) -> Optional[str]:
        """Get the video ID"""
        return self._video_id

    @video_id.setter
    def video_id(self, value: Optional[str]) -> None:
        """Set the video ID"""
        self._video_id = value

    @property
    def metadata(self) -> Dict[str, Any]:
        """Get the metadata dictionary"""
        return self._metadata

    @metadata.setter
    def metadata(self, value: Dict[str, Any]) -> None:
        """Set the metadata dictionary"""
        self._metadata = value or {}

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a value from the context data

        Args:
            key: The key to look up
            default: Default value if key is not found

        Returns:
            The value associated with the key, or default if key doesn't exist
        """
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """
        Set a value in the context data

        Args:
            key: The key to set
            value: The value to store
        """
        self._data[key] = value

    def update(self, updates: Dict[str, Any]) -> None:
        """
        Update multiple values in the context data

        Args:
            updates: Dictionary of updates to apply
        """
        self._data.update(updates)


class PipelineStage(IPipelineStage, ABC):
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
        """
        Get the name of the stage.

        Returns:
            str: The name of the stage
        """
        return self._name

    @property
    def status(self) -> PipelineStageStatus:
        """
        Get the current status of the stage.

        Returns:
            PipelineStageStatus: The current status
        """
        return self._status

    @status.setter
    def status(self, value: PipelineStageStatus) -> None:
        """
        Set the status of the stage.

        Args:
            value: The new status
        """
        self._status = value
        self.logger.debug(f"Stage status changed to {value}")

    @property
    def required_inputs(self) -> List[str]:
        """
        Get the list of required input keys.

        Returns:
            List[str]: List of required input keys
        """
        return self._required_inputs

    async def execute(self, context: IPipelineContext) -> IPipelineContext:
        """
        Execute the stage with the given context.

        This method handles common execution logic like status updates and error handling.
        Subclasses should implement _execute_impl() for stage-specific logic.

        Args:
            context: The pipeline context containing input data

        Returns:
            Updated pipeline context with stage results

        Raises:
            ProcessingError: If the stage fails to execute
        """
        self.status = PipelineStageStatus.RUNNING
        self.logger.info(f"Starting execution of stage: {self.name}")

        try:
            # Validate inputs before execution
            if not self.validate_inputs(context):
                missing = [i for i in self.required_inputs if i not in context.data]
                raise ProcessingError(f"Missing required inputs: {missing}")

            # Execute the stage implementation
            result = await self._execute_impl(context)
            self.status = PipelineStageStatus.COMPLETED
            self.logger.info(f"Completed stage: {self.name}")
            return result

        except Exception as e:
            self.status = PipelineStageStatus.FAILED
            error_msg = f"Stage '{self.name}' failed: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            raise ProcessingError(error_msg) from e

    def validate_inputs(self, context: IPipelineContext) -> bool:
        """
        Validate that all required inputs are present in the context.

        Args:
            context: The pipeline context to validate

        Returns:
            bool: True if all required inputs are present, False otherwise

        Note:
            This is called automatically by execute() before _execute_impl()
        """
        if not self.required_inputs:
            return True
        return all(key in context.data for key in self.required_inputs)

    def can_skip(self, context: IPipelineContext) -> bool:
        """
        Check if this stage can be skipped based on the current context.

        Args:
            context: The pipeline context to check

        Returns:
            bool: True if the stage can be skipped, False otherwise

        Note:
            Override this in subclasses to implement custom skip logic.
            The default implementation always returns False.
        """
        return False

    @abstractmethod
    async def _execute_impl(self, context: IPipelineContext) -> IPipelineContext:
        """
        Implementation of stage execution.

        Subclasses must override this method to provide stage-specific logic.

        Args:
            context: The pipeline context containing input data

        Returns:
            Updated pipeline context with stage results

        Raises:
            Exception: If the stage encounters an error
        """
        pass


class ProcessorPipelineStage(PipelineStage):
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
            f"Initialized {'async' if is_async else 'sync'} processor stage"
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
        self.logger.debug(f"Executing processor with input key: {self.input_key}")

        # Get input data from context
        input_data = context.get(self.input_key)
        if input_data is None:
            raise ProcessingError(f"No input data found for key '{self.input_key}'")

        try:
            # Prepare processor arguments
            kwargs: Dict[str, Any] = {"context": context}

            # Log input data type for debugging
            self.logger.debug(f"Input data type: {type(input_data).__name__}")

            # Execute processor (handles both sync and async processors)
            if asyncio.iscoroutinefunction(self.processor.process):
                self.logger.debug("Executing async processor")
                result = await self.processor.process(input_data, **kwargs)
            else:
                self.logger.debug("Executing sync processor")
                result = self.processor.process(input_data, **kwargs)

                # If the processor returns a coroutine, await it
                if asyncio.iscoroutine(result):
                    self.logger.debug("Processor returned a coroutine, awaiting...")
                    result = await result

            # Store result in context
            if result is not None:  # Only store non-None results
                context.set(self.output_key, result)
                self.logger.debug(f"Stored result at key: {self.output_key}")
            else:
                self.logger.warning("Processor returned None, no result stored")

            return context

        except Exception as e:
            error_msg = f"Processor '{self.name}' failed: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            raise ProcessingError(error_msg) from e


class FunctionPipelineStage(PipelineStage):
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
            f"Initialized {'async' if is_async else 'sync'} function stage"
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
            # Execute the function (handles both sync and async functions)
            if asyncio.iscoroutinefunction(self.func):
                self.logger.debug("Executing async function")
                result = await self.func(context)
            else:
                self.logger.debug("Executing sync function")
                result = self.func(context)

                # If the function returns a coroutine, await it
                if asyncio.iscoroutine(result):
                    self.logger.debug("Function returned a coroutine, awaiting...")
                    result = await result

            # Store result in context if output_key is provided
            if self.output_key is not None:
                context.set(self.output_key, result)
                self.logger.debug(f"Stored function result at key: {self.output_key}")

            return context

        except Exception as e:
            func_name = self.func_name or (
                self.func.__name__ if self.func else "unknown"
            )
            error_msg = f"Function '{func_name}' failed: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            raise ProcessingError(error_msg) from e


class VideoPipeline(IPipeline):
    """
    Implementation of IPipeline for video processing workflow.
    This is the main pipeline that orchestrates the execution of multiple stages.
    """

    def __init__(self, metrics_collector: Optional[MetricsCollector] = None):
        self._stages: List[IPipelineStage] = []
        self.metrics_collector = metrics_collector or MetricsCollector()
        self.logger = logging.getLogger("VideoPipeline")

    @property
    def stages(self) -> List[IPipelineStage]:
        """
        Get all stages in the pipeline

        Returns:
            List of pipeline stages
        """
        return self._stages

    def get_stage(self, name: str) -> Optional[IPipelineStage]:
        """
        Get a stage by name

        Args:
            name: Name of the stage to find

        Returns:
            The stage if found, None otherwise
        """
        for stage in self._stages:
            if stage.name == name:
                return stage
        return None

    def add_stage(self, stage: IPipelineStage) -> "IPipeline":
        """
        Add a stage to the pipeline

        Args:
            stage: The stage to add to the pipeline

        Returns:
            Self for method chaining

        Note:
            This method allows method chaining by returning self
        """
        self._stages.append(stage)
        return self

    def add_processor_stage(
        self,
        name: str,
        processor: Union[SyncProcessor, AsyncProcessor],
        input_key: str,
        output_key: str,
        required_inputs: Optional[List[str]] = None,
    ) -> "IPipeline":
        """
        Add a processor stage to the pipeline

        Args:
            name: Name of the stage
            processor: The processor to use
            input_key: Key to get input data from context
            output_key: Key to store output data in context
            required_inputs: List of required input keys

        Returns:
            Self for method chaining
        """
        stage = ProcessorPipelineStage(
            name=name,
            processor=processor,
            input_key=input_key,
            output_key=output_key,
            required_inputs=required_inputs,
        )
        return self.add_stage(stage)

    def add_function_stage(
        self,
        name: str,
        func: Optional[Callable] = None,
        func_name: Optional[str] = None,
        output_key: Optional[str] = None,
        required_inputs: Optional[List[str]] = None,
    ) -> "IPipeline":
        """
        Add a function stage to the pipeline

        Args:
            name: Name of the stage
            func: Processing function (can be provided later via func attribute)
            func_name: Function name to bind later (if func is not provided)
            output_key: Key to store the result in context
            required_inputs: List of required input keys

        Returns:
            Self for method chaining
        """
        stage = FunctionPipelineStage(
            name=name,
            func=func,
            func_name=func_name,
            output_key=output_key,
            required_inputs=required_inputs,
        )
        return self.add_stage(stage)

    async def execute(self, context: IPipelineContext) -> Dict[str, Any]:
        """
        Execute the pipeline with the given context

        Args:
            context: The pipeline context containing data and state

        Returns:
            Dictionary containing execution results and metrics

            Example:
                {
                    "success": True,
                    "duration": 1.23,
                    "stages": [
                        {
                            "name": "stage1",
                            "status": "completed",
                            "duration": 0.5
                        },
                        ...
                    ]
                }

        Raises:
            ProcessingError: If any stage fails during execution
        """
        results: Dict[str, Any] = {}
        start_time = time.time()

        for stage in self._stages:
            stage_start = time.time()
            self.logger.info("Executing stage: %s", stage.name)

            try:
                # Execute the stage
                context = await stage.execute(context)
                stage_duration = time.time() - stage_start
                stage.status = PipelineStageStatus.COMPLETED

                # Log success
                self.logger.info(
                    "Completed stage %s in %.2fs", stage.name, stage_duration
                )

                # Store stage duration for metrics and reporting
                setattr(stage, "_duration", stage_duration)

                # Collect metrics
                self.metrics_collector.record_stage(
                    stage.name, True, stage_duration, 1  # Assuming 1 item processed
                )

            except Exception as e:
                stage_duration = time.time() - stage_start
                stage.status = PipelineStageStatus.FAILED
                self.logger.error(
                    "Stage %s failed after %.2fs: %s",
                    stage.name,
                    stage_duration,
                    str(e),
                    exc_info=True,
                )

                # Record failure in metrics
                self.metrics_collector.record_stage(
                    stage.name, False, stage_duration, 0, str(e)
                )

                # Re-raise with additional context
                raise ProcessingError(f"Stage '{stage.name}' failed: {e}") from e

        total_duration = time.time() - start_time
        self.logger.info("Pipeline completed in %.2fs", total_duration)

        # Add execution summary to results
        results.update(
            {
                "success": True,
                "duration": total_duration,
                "stages": [
                    {
                        "name": stage.name,
                        "status": stage.status,
                        "duration": getattr(stage, "_duration", 0.0),
                    }
                    for stage in self._stages
                ],
            }
        )

        return results

    def get_stage_summary(self) -> List[Dict[str, Any]]:
        """
        Get summary of all stages in the pipeline

        Returns:
            List of dictionaries containing stage summaries with name, status,
            duration, and items_processed for each stage in the pipeline.

            Example:
                [
                    {
                        "name": "stage1",
                        "status": "completed",
                        "duration": 0.5,
                        "items_processed": 1
                    },
                    ...
                ]
        """
        return [
            {
                "name": stage.name,
                "status": stage.status,
                "duration": getattr(stage, "_duration", 0.0),
                "items_processed": getattr(stage, "_items_processed", 1),
            }
            for stage in self._stages
        ]


class ConditionalStage(PipelineStage):
    """Pipeline stage that executes conditionally"""

    def __init__(
        self,
        name: str,
        condition: Callable[[PipelineContext], bool],
        true_stage: PipelineStage,
        false_stage: Optional[PipelineStage] = None,
    ):
        super().__init__(name)
        self.condition = condition
        self.true_stage = true_stage
        self.false_stage = false_stage

    async def execute(self, context: PipelineContext) -> PipelineContext:
        """Execute conditional logic"""
        if self.condition(context):
            self.logger.info("Condition true, executing: %s", self.true_stage.name)
            return await self.true_stage.execute(context)
        elif self.false_stage:
            self.logger.info("Condition false, executing: %s", self.false_stage.name)
            return await self.false_stage.execute(context)
        else:
            self.logger.info("Condition false, no alternative stage")
            return context


class ParallelStage(PipelineStage):
    """Pipeline stage that executes multiple stages in parallel"""

    def __init__(self, name: str, stages: List[PipelineStage]):
        super().__init__(name)
        self.parallel_stages = stages

    async def execute(self, context: PipelineContext) -> PipelineContext:
        """Execute stages in parallel"""
        self.logger.info("Executing %d stages in parallel", len(self.parallel_stages))

        # Create tasks for parallel execution
        tasks = []
        for stage in self.parallel_stages:
            # Create a copy of context for each parallel stage
            stage_context = PipelineContext(
                data=context.data.copy(),
                temp_dir=context.temp_dir,
                video_id=context.video_id,
                metadata=context.metadata.copy(),
            )
            tasks.append(stage.execute(stage_context))

        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Merge results back into main context
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                stage_name = self.parallel_stages[i].name
                raise ProcessingError(f"Parallel stage '{stage_name}' failed: {result}")
            elif isinstance(result, PipelineContext):
                # Merge stage result into main context
                context.update(result.data)

        return context
