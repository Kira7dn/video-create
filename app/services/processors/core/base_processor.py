"""
Abstract base classes for video processing components
"""

from abc import ABC, abstractmethod
from typing import Any, List, Optional
import logging

from .metrics import MetricsCollector, ProcessingMetrics, ProcessingStage

logger = logging.getLogger(__name__)


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
