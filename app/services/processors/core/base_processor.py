"""Abstract base classes for video processing components"""

from abc import ABC, abstractmethod
from typing import Any, Optional
import logging

from .metrics import MetricsCollector, ProcessingMetrics, ProcessingStage

logger = logging.getLogger(__name__)


class ProcessorBase(ABC):
    """Base class providing common functionality for all processors.

    This class contains shared functionality like metrics collection, logging,
    and error handling that is used by both synchronous and asynchronous processors.
    """

    def __init__(self, metrics_collector: Optional[MetricsCollector] = None):
        """Initialize processor with metrics collector and logger.

        Args:
            metrics_collector: Optional metrics collector. If None, creates a new one.
        """
        self.metrics_collector = metrics_collector or MetricsCollector()
        self.logger = logging.getLogger(self.__class__.__name__)

    def _start_processing(self, stage: ProcessingStage) -> ProcessingMetrics:
        """Start processing with metrics tracking.

        Args:
            stage: Processing stage to track

        Returns:
            ProcessingMetrics object for tracking this processing stage
        """
        return self.metrics_collector.start_stage(stage)

    def _end_processing(
        self,
        metric: ProcessingMetrics,
        success: bool = True,
        error_message: Optional[str] = None,
        items_processed: int = 0,
    ) -> None:
        """End processing with metrics tracking.

        Args:
            metric: ProcessingMetrics object from _start_processing
            success: Whether processing was successful
            error_message: Error message if processing failed
            items_processed: Number of items processed
        """
        self.metrics_collector.end_stage(
            metric,
            success=success,
            error_message=error_message,
            items_processed=items_processed,
        )

    def _handle_processing_error(self, e: Exception, metric: ProcessingMetrics) -> None:
        """Common error handling logic.

        Args:
            e: Exception that occurred during processing
            metric: ProcessingMetrics object to update
        """
        error_msg = str(e)
        self.logger.error(
            "Processing failed: %s",
            error_msg,
            exc_info=True,
            extra={"error_type": type(e).__name__},
        )
        self._end_processing(metric, success=False, error_message=error_msg)


class SyncProcessor(ProcessorBase):
    """Base class for synchronous processors.

    This should be used for CPU-bound operations that don't require async I/O.
    Examples: image processing, text parsing, mathematical calculations.
    """

    @abstractmethod
    def _process_sync(self, input_data: Any, **kwargs) -> Any:
        """Implement synchronous processing logic.

        This method must be implemented by subclasses to define the actual
        processing logic for the specific processor.

        Args:
            input_data: Data to process
            **kwargs: Additional processing parameters

        Returns:
            Processed result
        """
        raise NotImplementedError("Subclasses must implement _process_sync")

    def process(self, input_data: Any, **kwargs) -> Any:
        """Main entry point with error handling and metrics.

        Args:
            input_data: Data to process
            **kwargs: Additional processing parameters

        Returns:
            Processed result

        Raises:
            Exception: Re-raises any exception from _process_sync after logging
        """
        stage = kwargs.get("processing_stage", ProcessingStage.PROCESSING)
        metric = self._start_processing(stage)

        try:
            self.logger.debug(
                "Starting synchronous processing",
                extra={"input_type": type(input_data).__name__},
            )

            result = self._process_sync(input_data, **kwargs)

            self.logger.debug(
                "Synchronous processing completed successfully",
                extra={"result_type": type(result).__name__},
            )

            self._end_processing(metric, success=True, items_processed=1)
            return result

        except Exception as e:
            self._handle_processing_error(e, metric)
            raise


class AsyncProcessor(ProcessorBase):
    """Base class for asynchronous processors.

    This should be used for I/O-bound operations that benefit from async/await.
    Examples: API calls, file operations, database queries, network requests.
    
    Subclasses should implement the actual processing logic in the process() method.
    """

    @abstractmethod
    async def process(self, input_data: Any, **kwargs) -> Any:
        """Implement asynchronous processing logic.

        This method must be implemented by subclasses to define the actual
        processing logic for the specific processor.

        Args:
            input_data: Data to process
            **kwargs: Additional processing parameters

        Returns:
            Processed result
            
        Raises:
            Exception: Any exception that occurs during processing
        """
        raise NotImplementedError("Subclasses must implement process()")

    def __call__(self, *args, **kwargs):
        """Prevent direct sync calls to the processor.

        Raises:
            NotImplementedError: Always, to prevent sync usage of async processor
        """
        raise NotImplementedError(
            "This is an async processor. Use 'await processor.process()' instead."
        )
