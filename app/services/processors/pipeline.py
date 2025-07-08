"""
Pipeline pattern implementation for video processing workflow
"""

from typing import List, Dict, Any, Optional, Union, Callable
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
import asyncio
import logging

from app.services.processors.base_processor import (
    BaseProcessor, MetricsCollector, ProcessingStage
)
from app.core.exceptions import ProcessingError, VideoCreationError

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
        pass
    
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
    
    def can_skip(self, context: PipelineContext) -> bool:
        """Determine if this stage can be skipped"""
        return False


class ProcessorPipelineStage(PipelineStage):
    """Pipeline stage that wraps a processor"""
    
    def __init__(self, 
                 name: str, 
                 processor: BaseProcessor,
                 input_key: str,
                 output_key: str,
                 required_inputs: Optional[List[str]] = None):
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
        
        # Execute processor
        result = self.processor.process(input_data, context=context)
        
        # Store result in context
        context.set(self.output_key, result)
        
        return context


class FunctionPipelineStage(PipelineStage):
    """Pipeline stage that wraps a function"""
    
    def __init__(self, 
                 name: str, 
                 func: Callable[[PipelineContext], Any],
                 output_key: Optional[str] = None,
                 required_inputs: Optional[List[str]] = None):
        super().__init__(name, required_inputs)
        self.func = func
        self.output_key = output_key
    
    async def execute(self, context: PipelineContext) -> PipelineContext:
        """Execute function and optionally store result in context"""
        self.validate_inputs(context)
        
        # Execute function
        if asyncio.iscoroutinefunction(self.func):
            result = await self.func(context)
        else:
            result = self.func(context)
        
        # Store result if output key specified
        if self.output_key:
            context.set(self.output_key, result)
        
        return context


class VideoPipeline:
    """Main pipeline for video processing workflow"""
    
    def __init__(self, metrics_collector: Optional[MetricsCollector] = None):
        self.stages: List[PipelineStage] = []
        self.metrics_collector = metrics_collector or MetricsCollector()
        self.logger = logging.getLogger("VideoPipeline")
    
    def add_stage(self, stage: PipelineStage) -> 'VideoPipeline':
        """Add a stage to the pipeline"""
        self.stages.append(stage)
        return self
    
    def add_processor_stage(self, 
                           name: str, 
                           processor: BaseProcessor,
                           input_key: str,
                           output_key: str,
                           required_inputs: Optional[List[str]] = None) -> 'VideoPipeline':
        """Add a processor stage to the pipeline"""
        stage = ProcessorPipelineStage(name, processor, input_key, output_key, required_inputs)
        return self.add_stage(stage)
    
    def add_function_stage(self, 
                          name: str, 
                          func: Callable,
                          output_key: Optional[str] = None,
                          required_inputs: Optional[List[str]] = None) -> 'VideoPipeline':
        """Add a function stage to the pipeline"""
        stage = FunctionPipelineStage(name, func, output_key, required_inputs)
        return self.add_stage(stage)
    
    async def execute(self, initial_context: PipelineContext) -> PipelineContext:
        """Execute the entire pipeline"""
        context = initial_context
        executed_stages = []
        
        try:
            self.logger.info(f"Starting pipeline execution with {len(self.stages)} stages")
            
            for i, stage in enumerate(self.stages):
                try:
                    self.logger.info(f"Executing stage {i+1}/{len(self.stages)}: {stage.name}")
                    stage.status = PipelineStageStatus.RUNNING
                    
                    # Check if stage can be skipped
                    if stage.can_skip(context):
                        self.logger.info(f"Skipping stage: {stage.name}")
                        stage.status = PipelineStageStatus.SKIPPED
                        continue
                    
                    # Execute stage
                    context = await stage.execute(context)
                    stage.status = PipelineStageStatus.COMPLETED
                    executed_stages.append(stage.name)
                    
                    self.logger.info(f"✅ Completed stage: {stage.name}")
                    
                except Exception as e:
                    stage.status = PipelineStageStatus.FAILED
                    error_msg = f"Stage '{stage.name}' failed: {e}"
                    self.logger.error(error_msg, exc_info=True)
                    raise ProcessingError(error_msg) from e
            
            self.logger.info(f"✅ Pipeline execution completed successfully")
            self.logger.info(f"   Executed stages: {', '.join(executed_stages)}")
            
            return context
            
        except Exception as e:
            # Mark remaining stages as failed
            for stage in self.stages:
                if stage.status == PipelineStageStatus.PENDING:
                    stage.status = PipelineStageStatus.FAILED
            
            self.logger.error(f"❌ Pipeline execution failed: {e}")
            raise VideoCreationError(f"Pipeline execution failed: {e}") from e
    
    def get_stage_summary(self) -> List[Dict[str, Any]]:
        """Get summary of all stages"""
        return [
            {
                "name": stage.name,
                "status": stage.status.value,
                "required_inputs": stage.required_inputs
            }
            for stage in self.stages
        ]


class ConditionalStage(PipelineStage):
    """Pipeline stage that executes conditionally"""
    
    def __init__(self, 
                 name: str, 
                 condition: Callable[[PipelineContext], bool],
                 true_stage: PipelineStage,
                 false_stage: Optional[PipelineStage] = None):
        super().__init__(name)
        self.condition = condition
        self.true_stage = true_stage
        self.false_stage = false_stage
    
    async def execute(self, context: PipelineContext) -> PipelineContext:
        """Execute conditional logic"""
        if self.condition(context):
            self.logger.info(f"Condition true, executing: {self.true_stage.name}")
            return await self.true_stage.execute(context)
        elif self.false_stage:
            self.logger.info(f"Condition false, executing: {self.false_stage.name}")
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
        self.logger.info(f"Executing {len(self.parallel_stages)} stages in parallel")
        
        # Create tasks for parallel execution
        tasks = []
        for stage in self.parallel_stages:
            # Create a copy of context for each parallel stage
            stage_context = PipelineContext(
                data=context.data.copy(),
                temp_dir=context.temp_dir,
                video_id=context.video_id,
                metadata=context.metadata.copy()
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
