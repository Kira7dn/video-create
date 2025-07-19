"""
Metrics collection and processing stage tracking for video processing pipeline.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
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
    UPLOAD = "upload"


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
    ) -> None:
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
