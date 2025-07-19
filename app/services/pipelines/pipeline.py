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
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from app.core.exceptions import ProcessingError
from app.services.processors.core.base_processor import BaseProcessor, Validator
from app.services.processors.core.metrics import MetricsCollector
from app.services.processors.validation.core.base_validator import PydanticAIValidator

logger = logging.getLogger(__name__)


class PipelineStageStatus(Enum):
    """Status of pipeline stage execution"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PipelineContext:
    """Context object passed through pipeline stages"""

    data: Dict[str, Any]
    temp_dir: str
    video_id: str
    metadata: Dict[str, Any]

    def get(self, key: str, default: Any = None) -> Any:
        """Get value from context data"""
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set value in context data"""
        self.data[key] = value

    def update(self, updates: Dict[str, Any]) -> None:
        """Update context data with multiple values"""
        self.data.update(updates)


class PipelineStage(ABC):
    """Abstract base class for pipeline stages"""

    def __init__(self, name: str, required_inputs: Optional[List[str]] = None):
        self.name = name
        self.required_inputs = required_inputs or []
        self.status = PipelineStageStatus.PENDING
        self.logger = logging.getLogger(f"Pipeline.{name}")

    @abstractmethod
    async def execute(self, context: PipelineContext) -> PipelineContext:
        """Execute this pipeline stage"""

    def validate_inputs(self, context: PipelineContext) -> None:
        """Validate required inputs are present in context"""
        missing_inputs = []
        for required_input in self.required_inputs:
            if required_input not in context.data:
                missing_inputs.append(required_input)

        if missing_inputs:
            raise ProcessingError(
                f"Stage '{self.name}' missing required inputs: {', '.join(missing_inputs)}"
            )

    def can_skip(self, _context: PipelineContext) -> bool:
        """Determine if this stage can be skipped"""
        return False


class ProcessorPipelineStage(PipelineStage):
    """Pipeline stage that wraps a processor"""

    def __init__(
        self,
        name: str,
        processor: BaseProcessor,
        input_key: str,
        output_key: str,
        required_inputs: Optional[List[str]] = None,
    ):
        super().__init__(name, required_inputs)
        self.processor = processor
        self.input_key = input_key
        self.output_key = output_key

    async def execute(self, context: PipelineContext) -> PipelineContext:
        """Execute processor and store result in context"""
        self.validate_inputs(context)

        input_data = context.get(self.input_key)
        if input_data is None:
            raise ProcessingError(f"No input data found for key '{self.input_key}'")

        # Execute processor (handle both sync and async)
        kwargs: Dict[str, Any] = {"context": context}

        if asyncio.iscoroutinefunction(self.processor.process):
            result = await self.processor.process(input_data, **kwargs)
        else:
            result = self.processor.process(input_data, **kwargs)

        # If processor is a Validator, handle validation result
        if isinstance(self.processor, Validator):
            if not result.is_valid:
                # For AI validators, fallback to original data with warning
                if isinstance(self.processor, PydanticAIValidator):
                    self.logger.warning(
                        "AI validation failed, using original data: %s",
                        "; ".join(result.errors),
                    )
                    context.set(
                        self.output_key, input_data
                    )  # Fallback to original input
                else:
                    # For critical validators, fail the pipeline
                    raise ProcessingError(
                        f"Validation failed: {'; '.join(result.errors)}"
                    )
            else:
                # Validation succeeded, use validated data if available
                validated_data = (
                    result.validated_data
                    if result.validated_data is not None
                    else input_data
                )
                context.set(self.output_key, validated_data)
        else:
            context.set(self.output_key, result)

        return context


class FunctionPipelineStage(PipelineStage):
    """Pipeline stage that wraps a function"""

    def __init__(
        self,
        name: str,
        func: Optional[Callable[[PipelineContext], Any]] = None,
        func_name: Optional[str] = None,
        output_key: Optional[str] = None,
        required_inputs: Optional[List[str]] = None,
    ):
        super().__init__(name, required_inputs)
        self.func = func
        self.func_name = func_name  # Tên function để bind sau
        self.output_key = output_key

    async def execute(self, context: PipelineContext) -> PipelineContext:
        """
        Execute function and optionally store result in context

        Raises:
            ProcessingError: Nếu function chưa được bind hoặc có lỗi khi thực thi
        """
        if self.func is None:
            raise ProcessingError(
                f"Function for stage '{self.name}' is not bound. "
                f"Make sure to set the 'func' attribute or provide a valid function."
            )

        self.validate_inputs(context)
        self.status = PipelineStageStatus.RUNNING

        try:
            # Gọi function với context
            if asyncio.iscoroutinefunction(self.func):
                result = await self.func(context)
            else:
                # Nếu function không phải coroutine, chạy trong executor
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, self.func, context)

            if self.output_key is not None:
                context.set(self.output_key, result)

            self.status = PipelineStageStatus.COMPLETED
            return context

        except Exception as e:
            self.status = PipelineStageStatus.FAILED
            self.logger.error(
                "Error in function stage '%s': %s", self.name, str(e), exc_info=True
            )
            raise ProcessingError(f"Error in function stage '{self.name}': {e}") from e


class VideoPipeline:
    """Main pipeline for video processing workflow"""

    def __init__(self, metrics_collector: Optional[MetricsCollector] = None):
        self._stages: List[PipelineStage] = []
        self.metrics_collector = metrics_collector or MetricsCollector()
        self.logger = logging.getLogger("VideoPipeline")

    @property
    def stages(self) -> List[PipelineStage]:
        """Get the list of pipeline stages"""
        return self._stages

    def get_stage(self, name: str) -> Optional[PipelineStage]:
        """
        Get a stage by name

        Args:
            name: Name of the stage to find

        Returns:
            PipelineStage or None if not found
        """
        for stage in self._stages:
            if stage.name == name:
                return stage
        return None

    def add_stage(self, stage: PipelineStage) -> PipelineStage:
        """
        Add a stage to the pipeline

        Args:
            stage: Stage to add to the pipeline

        Returns:
            PipelineStage: The added stage (for method chaining)
        """
        self._stages.append(stage)
        return stage

    def add_processor_stage(
        self,
        name: str,
        processor: BaseProcessor,
        input_key: str,
        output_key: str,
        required_inputs: Optional[List[str]] = None,
    ) -> "VideoPipeline":
        """Add a processor stage to the pipeline"""
        stage = ProcessorPipelineStage(
            name, processor, input_key, output_key, required_inputs
        )
        return self.add_stage(stage)

    def add_function_stage(
        self,
        name: str,
        func: Optional[Callable] = None,
        func_name: Optional[str] = None,
        output_key: Optional[str] = None,
        required_inputs: Optional[List[str]] = None,
    ) -> FunctionPipelineStage:
        """
        Add a function stage to the pipeline

        Args:
            name: Tên của stage
            func: Hàm xử lý (có thể cung cấp sau qua thuộc tính func)
            func_name: Tên hàm để bind sau (nếu chưa có func)
            output_key: Khóa để lưu kết quả vào context
            required_inputs: Danh sách các input bắt buộc

        Returns:
            FunctionPipelineStage: Đối tượng stage vừa được tạo
        """
        stage = FunctionPipelineStage(
            name=name,
            func=func,
            func_name=func_name,
            output_key=output_key,
            required_inputs=required_inputs,
        )
        self.add_stage(stage)
        return stage

    async def execute(self, context: PipelineContext) -> Dict[str, Any]:
        """
        Execute the pipeline with the given context

        Args:
            context: The pipeline context containing data and state

        Returns:
            Dict containing execution results and metrics

        Raises:
            ProcessingError: If any stage fails
        """
        results = {}
        start_time = time.time()

        for stage in self._stages:
            stage_start = time.time()
            self.logger.info("Executing stage: %s", stage.name)

            try:
                # Execute the stage
                context = await stage.execute(context)
                stage_duration = time.time() - stage_start

                # Log success
                self.logger.info(
                    "Completed stage %s in %.2fs", stage.name, stage_duration
                )

                # Collect metrics
                self.metrics_collector.record_stage(
                    stage.name, True, stage_duration, 1  # Assuming 1 item processed
                )

            except Exception as e:
                stage_duration = time.time() - stage_start
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
                        "status": stage.status.value,
                        "duration": getattr(stage, "duration", 0),
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
            List[Dict]: List of stage summaries with name, status, duration, and items_processed
        """
        return [
            {
                "name": stage.name,
                "status": stage.status.value,
                "duration": getattr(stage, "duration", 0),
                "items_processed": getattr(stage, "items_processed", 0),
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
