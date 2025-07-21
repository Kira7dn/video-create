"""
Interface for pipeline
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any

from app.interfaces.pipeline_context import IPipelineContext
from app.interfaces.pipeline_stage import IPipelineStage


class IPipeline(ABC):
    """
    Interface defining the contract for a pipeline.
    A pipeline is a series of stages that process data in sequence.
    """

    @property
    @abstractmethod
    def stages(self) -> List[IPipelineStage]:
        """
        Get all stages in the pipeline
        
        Returns:
            List of pipeline stages
        """
        pass

    @abstractmethod
    def add_stage(self, stage: IPipelineStage) -> 'IPipeline':
        """
        Add a stage to the pipeline
        
        Args:
            stage: The stage to add
            
        Returns:
            Self for method chaining
        """
        pass

    @abstractmethod
    def get_stage(self, name: str) -> Optional[IPipelineStage]:
        """
        Get a stage by name
        
        Args:
            name: Name of the stage to find
            
        Returns:
            The stage if found, None otherwise
        """
        pass

    @abstractmethod
    async def execute(self, context: IPipelineContext) -> Dict[str, Any]:
        """
        Execute the pipeline with the given context
        
        Args:
            context: The pipeline context
            
        Returns:
            Dictionary containing execution results and metrics
            
        Raises:
            ProcessingError: If any stage fails
        """
        pass

    @abstractmethod
    def get_stage_summary(self) -> List[Dict[str, Any]]:
        """
        Get summary of all stages in the pipeline
        
        Returns:
            List of dictionaries containing stage summaries with name, status, 
            duration, and other relevant information
        """
        pass
