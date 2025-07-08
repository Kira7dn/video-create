"""
Batch processor for handling multiple video segments efficiently
"""

import asyncio
import concurrent.futures
from typing import List, Dict, Any, Optional, Callable, Tuple
from app.services.processors.base_processor import BatchProcessor, ProcessingStage, MetricsCollector
from app.core.exceptions import ProcessingError
from app.config.settings import settings
import logging

logger = logging.getLogger(__name__)


class SegmentBatchProcessor(BatchProcessor):
    """Handles batch processing of video segments with configurable concurrency"""
    
    def __init__(self, 
                 processor_func: Callable,
                 max_concurrent: Optional[int] = None,
                 metrics_collector: Optional[MetricsCollector] = None):
        """
        Initialize batch processor
        
        Args:
            processor_func: Function to process individual segments
            max_concurrent: Maximum concurrent operations (defaults to settings)
            metrics_collector: Metrics collector instance
        """
        super().__init__(metrics_collector)
        self.processor_func = processor_func
        self.max_concurrent = max_concurrent or settings.performance_max_concurrent_segments
    
    def process_batch(self, items: List[Dict], **kwargs) -> List[Dict[str, str]]:
        """
        Process multiple segments in batches with concurrency control
        
        Args:
            items: List of segment dictionaries to process
            **kwargs: Additional arguments including temp_dir for processor function
            
        Returns:
            List of segment info dicts with processing results
            
        Raises:
            ProcessingError: If batch processing fails
        """
        metric = self._start_processing(ProcessingStage.SEGMENT_CREATION)
        
        try:
            # Extract temp_dir from kwargs
            temp_dir = kwargs.get('temp_dir')
            if not temp_dir:
                raise ProcessingError("temp_dir is required in kwargs")
            
            segments = items
            total_segments = len(segments)
            self.logger.info(f"Starting batch processing of {total_segments} segments "
                           f"(max concurrent: {self.max_concurrent})")
            
            # Process segments in batches
            results = []
            batch_size = self.max_concurrent
            
            for i in range(0, total_segments, batch_size):
                batch = segments[i:i + batch_size]
                # Create kwargs copy without temp_dir to avoid duplicate argument
                batch_kwargs = {k: v for k, v in kwargs.items() if k != 'temp_dir'}
                batch_results = self._process_segment_batch(batch, temp_dir, **batch_kwargs)
                results.extend(batch_results)
                
                # Log progress
                completed = min(i + batch_size, total_segments)
                self.logger.info(f"✅ Processed batch {completed}/{total_segments} segments")
            
            self._end_processing(metric, success=True, items_processed=total_segments)
            return results
            
        except Exception as e:
            error_msg = f"Batch processing failed: {e}"
            self.logger.error(error_msg, exc_info=True)
            self._end_processing(metric, success=False, error_message=error_msg)
            raise ProcessingError(error_msg) from e
    
    def _process_segment_batch(self, batch: List[Dict], temp_dir: str, **kwargs) -> List[Dict[str, str]]:
        """Process a single batch of segments concurrently"""
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_concurrent) as executor:
            # Submit all tasks
            futures = []
            for segment in batch:
                future = executor.submit(self._process_single_segment, segment, temp_dir, **kwargs)
                futures.append((future, segment))
            
            # Collect results
            results = []
            for future, segment in futures:
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    segment_id = segment.get("id", "unknown")
                    error_msg = f"Failed to process segment {segment_id}: {e}"
                    self.logger.error(error_msg)
                    raise ProcessingError(error_msg) from e
            
            return results
    
    def _process_single_segment(self, segment: Dict, temp_dir: str, **kwargs) -> Dict[str, str]:
        """Process a single segment"""
        try:
            # Call the processor function
            clip_path = self.processor_func(segment, temp_dir, **kwargs)
            
            return {
                "id": segment.get("id", "unknown"),
                "path": clip_path
            }
            
        except Exception as e:
            segment_id = segment.get("id", "unknown")
            raise ProcessingError(f"Segment {segment_id} processing failed: {e}") from e


class AsyncBatchProcessor(BatchProcessor):
    """Async batch processor for handling asynchronous operations"""
    
    def __init__(self, 
                 async_processor_func: Callable,
                 max_concurrent: Optional[int] = None,
                 metrics_collector: Optional[MetricsCollector] = None):
        """
        Initialize async batch processor
        
        Args:
            async_processor_func: Async function to process individual items
            max_concurrent: Maximum concurrent operations
            metrics_collector: Metrics collector instance
        """
        super().__init__(metrics_collector)
        self.async_processor_func = async_processor_func
        self.max_concurrent = max_concurrent or settings.download_max_concurrent
    
    async def process_batch_async(self, items: List[Any], **kwargs) -> List[Any]:
        """
        Process items asynchronously with concurrency control
        
        Args:
            items: List of items to process
            **kwargs: Additional arguments for processor function
            
        Returns:
            List of processing results
        """
        metric = self._start_processing(ProcessingStage.DOWNLOAD)
        
        try:
            # Create semaphore for concurrency control
            semaphore = asyncio.Semaphore(self.max_concurrent)
            
            async def process_with_semaphore(item):
                async with semaphore:
                    return await self.async_processor_func(item, **kwargs)
            
            # Process all items concurrently
            tasks = [process_with_semaphore(item) for item in items]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Handle exceptions
            successful_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    error_msg = f"Item {i} processing failed: {result}"
                    self.logger.error(error_msg)
                    raise ProcessingError(error_msg) from result
                successful_results.append(result)
            
            self._end_processing(metric, success=True, items_processed=len(items))
            return successful_results
            
        except Exception as e:
            error_msg = f"Async batch processing failed: {e}"
            self.logger.error(error_msg, exc_info=True)
            self._end_processing(metric, success=False, error_message=error_msg)
            raise ProcessingError(error_msg) from e
    
    def process_batch(self, items: List[Any], **kwargs) -> List[Any]:
        """Synchronous wrapper for async batch processing"""
        return asyncio.run(self.process_batch_async(items, **kwargs))


class ProgressTracker:
    """Tracks and reports progress of batch operations"""
    
    def __init__(self, total_items: int, report_interval: int = 5):
        self.total_items = total_items
        self.completed_items = 0
        self.failed_items = 0
        self.report_interval = report_interval
        self.last_reported = 0
    
    def update(self, completed: int = 1, failed: int = 0):
        """Update progress counters"""
        self.completed_items += completed
        self.failed_items += failed
        
        # Report progress at intervals
        if (self.completed_items + self.failed_items - self.last_reported) >= self.report_interval:
            self.report_progress()
            self.last_reported = self.completed_items + self.failed_items
    
    def report_progress(self):
        """Report current progress"""
        total_processed = self.completed_items + self.failed_items
        percentage = (total_processed / self.total_items) * 100 if self.total_items > 0 else 0
        
        logger.info(f"Progress: {total_processed}/{self.total_items} ({percentage:.1f}%) "
                   f"- Completed: {self.completed_items}, Failed: {self.failed_items}")
    
    def get_summary(self) -> Dict[str, Any]:
        """Get progress summary"""
        total_processed = self.completed_items + self.failed_items
        return {
            "total_items": self.total_items,
            "completed": self.completed_items,
            "failed": self.failed_items,
            "processed": total_processed,
            "completion_rate": (self.completed_items / self.total_items) * 100 if self.total_items > 0 else 0,
            "success_rate": (self.completed_items / total_processed) * 100 if total_processed > 0 else 0
        }
