"""
Abstract base classes for video processing components
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Protocol
from dataclasses import dataclass
from enum import Enum
import time
import logging

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
    
    def start_stage(self, stage: ProcessingStage) -> ProcessingMetrics:
        """Start tracking a processing stage"""
        metric = ProcessingMetrics(
            stage=stage,
            start_time=time.time()
        )
        self.metrics.append(metric)
        return metric
    
    def end_stage(self, metric: ProcessingMetrics, success: bool = True, 
                  error_message: Optional[str] = None, items_processed: int = 0):
        """End tracking a processing stage"""
        metric.end_time = time.time()
        metric.success = success
        metric.error_message = error_message
        metric.items_processed = items_processed
        
        logger.info(f"Stage {metric.stage.value} completed in {metric.duration:.2f}s "
                   f"(success: {success}, items: {items_processed})")
    
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
                    "error": m.error_message
                }
                for m in self.metrics
            ],
            "total_items": sum(m.items_processed for m in self.metrics),
            "failed_stages": [m.stage.value for m in self.metrics if not m.success]
        }


class BaseProcessor(ABC):
    """Abstract base class for all processors"""
    
    def __init__(self, metrics_collector: Optional[MetricsCollector] = None):
        self.metrics_collector = metrics_collector or MetricsCollector()
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    def process(self, input_data: Any, **kwargs) -> Any:
        """Process input data and return result"""
        pass
    
    def _start_processing(self, stage: ProcessingStage) -> ProcessingMetrics:
        """Start processing with metrics tracking"""
        return self.metrics_collector.start_stage(stage)
    
    def _end_processing(self, metric: ProcessingMetrics, success: bool = True,
                       error_message: Optional[str] = None, items_processed: int = 0):
        """End processing with metrics tracking"""
        self.metrics_collector.end_stage(metric, success, error_message, items_processed)


class BatchProcessor(BaseProcessor):
    """Abstract base class for batch processing operations"""
    
    @abstractmethod
    def process_batch(self, items: List[Any], **kwargs) -> List[Any]:
        """Process a batch of items"""
        pass
    
    def process(self, input_data: List[Any], **kwargs) -> List[Any]:
        """Process method that delegates to process_batch"""
        return self.process_batch(input_data, **kwargs)


class ValidationResult:
    """Result of validation operation"""
    
    def __init__(self, is_valid: bool = True, errors: Optional[List[str]] = None, validated_data: Any = None):
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
        ...


class Validator(BaseProcessor):
    """Abstract base class for validators"""
    
    @abstractmethod
    async def validate(self, data: Any) -> ValidationResult:
        """Validate data and return validation result"""
        pass
    
    async def process(self, input_data: Any, **kwargs) -> ValidationResult:
        """Process method that delegates to validate"""
        return await self.validate(input_data)
