"""
Abstract base classes for video processing components
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Protocol
from dataclasses import dataclass
from enum import Enum
import time
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class ProcessingStage(Enum):
    """Enumeration of processing stages"""

    VALIDATION = "validation"
    DOWNLOAD = "download"
    AUDIO_PROCESSING = "audio_processing"
    TEXT_OVERLAY = "text_overlay"
    SEGMENT_CREATION = "segment_creation"
    CONCATENATION = "concatenation"
    CLEANUP = "cleanup"
    S3_UPLOAD = "s3_upload"


@dataclass
class ProcessingMetrics:
    """Metrics for processing operations"""

    stage: ProcessingStage
    start_time: float
    end_time: Optional[float] = None
    success: bool = True
    error_message: Optional[str] = None
    items_processed: int = 0

    @property
    def duration(self) -> float:
        """Get processing duration in seconds"""
        if self.end_time is None:
            return time.time() - self.start_time
        return self.end_time - self.start_time


class MetricsCollector:
    """Collects and manages processing metrics"""

    def __init__(self):
        self.metrics: List[ProcessingMetrics] = []
        self._counters: Dict[str, int] = defaultdict(int)

    def start_stage(self, stage: ProcessingStage) -> ProcessingMetrics:
        """Start tracking a processing stage"""
        metric = ProcessingMetrics(stage=stage, start_time=time.time())
        self.metrics.append(metric)
        return metric

    def increment_counter(self, name: str, value: int = 1) -> None:
        """Increment a counter metric.

        Args:
            name: Name of the counter to increment
            value: Amount to increment the counter by (default: 1)
        """
        self._counters[name] = self._counters.get(name, 0) + value
        logger.debug("Counter '%s' incremented to %d", name, self._counters[name])

    def record_execution_time(
        self, stage: Any, execution_time: float, success: bool = True
    ) -> None:
        """Record execution time for a specific stage

        Args:
            stage: Can be a ProcessingStage enum or a string representing the stage name
            execution_time: Execution time in milliseconds
            success: Whether the stage completed successfully
        """
        status = "succeeded" if success else "failed"
        stage_name = stage.value if hasattr(stage, "value") else str(stage)

        # Increment appropriate counter based on success/failure
        counter_name = f"{stage_name}_{status}"
        self.increment_counter(counter_name)

        logger.debug(
            "Stage %s %s in %.2f ms",
            stage_name,
            status,
            execution_time,
        )

    def end_stage(
        self,
        metric: ProcessingMetrics,
        success: bool = True,
        error_message: Optional[str] = None,
        items_processed: int = 0,
    ):
        """End tracking a processing stage"""
        metric.end_time = time.time()
        metric.success = success
        metric.error_message = error_message
        metric.items_processed = items_processed

        logger.info(
            "Stage %s completed in %.2fs (success: %s, items: %d)",
            metric.stage.value,
            metric.duration,
            success,
            items_processed,
        )

    def get_total_duration(self) -> float:
        """Get total processing duration"""
        if not self.metrics:
            return 0.0

        start_time = min(m.start_time for m in self.metrics)
        end_time = max(m.end_time or time.time() for m in self.metrics)
        return end_time - start_time

    def get_summary(self) -> Dict[str, Any]:
        """Get processing summary"""
        return {
            "total_duration": self.get_total_duration(),
            "stages": [
                {
                    "stage": m.stage.value,
                    "duration": m.duration,
                    "success": m.success,
                    "items_processed": m.items_processed,
                    "error": m.error_message,
                }
                for m in self.metrics
            ],
            "total_items": sum(m.items_processed for m in self.metrics),
            "failed_stages": [m.stage.value for m in self.metrics if not m.success],
        }


class BaseSyncProcessor(ABC):
    """Base class for synchronous processors.

    This should be used for CPU-bound operations that don't require async I/O.
    """

    def __init__(self, metrics_collector: Optional[MetricsCollector] = None):
        self.metrics_collector = metrics_collector or MetricsCollector()
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def process(self, input_data: Any, **kwargs) -> Any:
        """Process input data synchronously"""

    def _start_processing(self, stage: ProcessingStage) -> ProcessingMetrics:
        """Start processing with metrics tracking"""
        return self.metrics_collector.start_stage(stage)

    def _end_processing(
        self,
        metric: ProcessingMetrics,
        success: bool = True,
        error_message: Optional[str] = None,
        items_processed: int = 0,
    ) -> None:
        """End processing with metrics tracking"""
        self.metrics_collector.end_stage(
            metric,
            success=success,
            error_message=error_message,
            items_processed=items_processed,
        )


class BaseProcessor(ABC):
    """Base class for asynchronous processors.

    This should be used for I/O-bound operations that benefit from async/await.
    """

    def __init__(self, metrics_collector: Optional[MetricsCollector] = None):
        self.metrics_collector = metrics_collector or MetricsCollector()
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    async def _process_async(self, input_data: Any, **kwargs) -> Any:
        """Async processing implementation - must be overridden by subclasses"""

    # Main entry point that enforces async usage
    async def process(self, input_data: Any, **kwargs) -> Any:
        """Process input data asynchronously"""
        return await self._process_async(input_data, **kwargs)

    # Prevent direct sync calls to process()
    def __call__(self, *args, **kwargs):
        """Prevent direct sync calls to the processor"""
        raise NotImplementedError(
            "This is an async processor. Use 'await processor.process()' instead."
        )

    # Reuse metrics methods from BaseSyncProcessor
    def _start_processing(self, stage: ProcessingStage) -> ProcessingMetrics:
        """Start processing with metrics tracking"""
        return self.metrics_collector.start_stage(stage)

    def _end_processing(
        self,
        metric: ProcessingMetrics,
        success: bool = True,
        error_message: Optional[str] = None,
        items_processed: int = 0,
    ) -> None:
        """End processing with metrics tracking"""
        self.metrics_collector.end_stage(
            metric,
            success=success,
            error_message=error_message,
            items_processed=items_processed,
        )


class BatchProcessor(BaseProcessor):
    """Abstract base class for batch processing operations"""

    @abstractmethod
    def process_batch(self, items: List[Any], **kwargs) -> List[Any]:
        """Process a batch of items"""

    async def process(self, input_data: List[Any], **kwargs) -> List[Any]:
        """Process method that delegates to process_batch"""
        return await self.process_batch(input_data, **kwargs)


class ValidationResult:
    """Result of validation operation"""

    def __init__(
        self,
        is_valid: bool = True,
        errors: Optional[List[str]] = None,
        validated_data: Any = None,
    ):
        self.is_valid = is_valid
        self.errors = errors or []
        self.validated_data = validated_data  # Lưu output đã chuẩn hóa nếu có

    def add_error(self, error: str):
        """Add validation error"""
        self.errors.append(error)
        self.is_valid = False

    def __bool__(self):
        return self.is_valid


class ValidatorProtocol(Protocol):
    """Protocol for validation functions"""

    def __call__(self, data: Any) -> ValidationResult:
        """Validate data and return result"""


class Validator(BaseSyncProcessor):
    """Base class for synchronous validators.

    Note: This is intentionally synchronous since validation is typically CPU-bound.
    """

    @abstractmethod
    def validate(self, data: Any) -> ValidationResult:
        """Validate data and return validation result"""

    def process(self, input_data: Any, **kwargs) -> ValidationResult:
        """Process input data by validating it"""
        return self.validate(input_data)
