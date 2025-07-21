"""
VideoPipeline implementation.

This module provides the main pipeline implementation for video processing workflows.
"""

import logging
import time
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union

from app.core.exceptions import ProcessingError
from app.interfaces.pipeline import IPipeline
from app.interfaces.pipeline.context import IPipelineContext
from app.interfaces.pipeline.stage import IPipelineStage
from app.services.processors.core.base_processor import AsyncProcessor, SyncProcessor
from app.services.processors.core.metrics import MetricsCollector
from app.services.pipelines.stages.processor import ProcessorPipelineStage
from app.services.pipelines.stages.function import FunctionPipelineStage

logger = logging.getLogger("VideoPipeline")

# Type variable for context
ContextT = TypeVar("ContextT", bound=IPipelineContext)


class VideoPipeline(IPipeline):
    """
    Implementation of IPipeline for video processing workflow.

    This is the main pipeline that orchestrates the execution of multiple stages.
    """

    def __init__(self, metrics_collector: Optional[MetricsCollector] = None):
        """
        Initialize a new video pipeline.

        Args:
            metrics_collector: Optional metrics collector for tracking pipeline execution
        """
        self._stages: List[IPipelineStage] = []
        self.metrics_collector = metrics_collector or MetricsCollector()
        self.logger = logging.getLogger("VideoPipeline")

    @property
    def stages(self) -> List[IPipelineStage]:
        """
        Get all stages in the pipeline.

        Returns:
            List of pipeline stages
        """
        return self._stages

    def get_stage(self, name: str) -> Optional[IPipelineStage]:
        """
        Get a stage by name.

        Args:
            name: Name of the stage to find

        Returns:
            The stage if found, None otherwise
        """
        for stage in self._stages:
            if stage.name == name:
                return stage
        return None

    def add_stage(self, stage: IPipelineStage) -> "VideoPipeline":
        """
        Add a stage to the pipeline.

        Args:
            stage: The stage to add to the pipeline

        Returns:
            Self for method chaining
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
    ) -> "VideoPipeline":
        """
        Add a processor stage to the pipeline.

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
        func: Optional[Callable[[IPipelineContext], Any]] = None,
        func_name: Optional[str] = None,
        output_key: Optional[str] = None,
        required_inputs: Optional[List[str]] = None,
    ) -> "VideoPipeline":
        """
        Add a function stage to the pipeline.

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
        Execute the pipeline with the given context.

        Args:
            context: The pipeline context containing data and state

        Returns:
            Dictionary containing execution results and metrics

        Raises:
            ProcessingError: If any stage fails during execution
        """
        start_time = time.time()
        results = {
            "success": False,
            "duration": 0.0,
            "stages": [],
            "error": None,
        }

        try:
            self.logger.info(
                "Starting pipeline execution with %d stages", len(self._stages)
            )

            # Execute each stage in sequence
            for stage in self._stages:
                stage_start = time.time()
                stage_result = {
                    "name": stage.name,
                    "status": "pending",
                    "duration": 0.0,
                }
                results["stages"].append(stage_result)

                try:
                    # Execute the stage
                    self.logger.info("Executing stage: %s", stage.name)
                    await stage.execute(context)

                    # Record successful execution
                    stage_result["status"] = stage.status.value
                    stage_result["duration"] = time.time() - stage_start

                    self.logger.info(
                        "Completed stage %s in %.2fs",
                        stage.name,
                        stage_result["duration"],
                    )

                except Exception as e:
                    # Record stage failure
                    stage_result["status"] = "failed"
                    stage_result["error"] = str(e)
                    stage_result["duration"] = time.time() - stage_start

                    error_msg = f"Pipeline failed at stage '{stage.name}': {str(e)}"
                    self.logger.error(error_msg, exc_info=True)

                    # Record overall failure
                    results["error"] = error_msg
                    results["duration"] = time.time() - start_time
                    results["success"] = False

                    # Collect metrics for failed pipeline
                    self._collect_metrics(results)
                    raise ProcessingError(error_msg) from e

            # Record successful pipeline execution
            results["duration"] = time.time() - start_time
            results["success"] = True
            self.logger.info(
                "Pipeline completed successfully in %.2f seconds", results["duration"]
            )

            # Collect metrics for successful pipeline
            self._collect_metrics(results)
            return results

        except Exception as e:
            # Handle any unexpected errors
            results["duration"] = time.time() - start_time
            results["error"] = str(e)
            results["success"] = False

            self.logger.error(
                "Pipeline failed after %.2f seconds: %s",
                results["duration"],
                str(e),
                exc_info=True,
            )

            # Collect metrics for failed pipeline
            self._collect_metrics(results)
            raise

    def get_stage_summary(self) -> List[Dict[str, Any]]:
        """
        Get summary of all stages in the pipeline.

        Returns:
            List of dictionaries containing stage summaries with name, status,
            duration, and items_processed for each stage in the pipeline.
        """
        return [
            {
                "name": stage.name,
                "status": stage.status.value,
                "duration": getattr(stage, "duration", 0.0),
                "items_processed": getattr(stage, "items_processed", 0),
            }
            for stage in self._stages
        ]

    def _collect_metrics(self, results: Dict[str, Any]) -> None:
        """
        Collect metrics for the pipeline execution.

        Args:
            results: Pipeline execution results
        """
        try:
            # Record pipeline execution metrics
            self.metrics_collector.record_metric(
                "pipeline_execution_time_seconds",
                results["duration"],
                {"success": str(results["success"]).lower()},
            )

            # Record stage metrics
            for stage_result in results.get("stages", []):
                self.metrics_collector.record_metric(
                    "stage_execution_time_seconds",
                    stage_result.get("duration", 0.0),
                    {
                        "stage": stage_result.get("name", "unknown"),
                        "status": stage_result.get("status", "unknown"),
                    },
                )

        except (KeyError, AttributeError, ValueError) as e:
            # Log specific errors that could occur during metrics collection
            self.logger.error(
                "Failed to collect pipeline metrics: %s", str(e), exc_info=True
            )
        except Exception as e:  # pylint: disable=broad-except
            # Catch any other unexpected errors to prevent pipeline failure
            self.logger.critical(
                "Unexpected error while collecting pipeline metrics: %s",
                str(e),
                exc_info=True,
            )
