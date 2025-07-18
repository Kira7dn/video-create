"""
PydanticAIValidator processor for advanced schema validation using PydanticAI Agent.
Follows project SRP, error handling, and metrics patterns.
"""

import asyncio
import json
import logging
import os
from typing import Any, Optional

from app.config import settings
from app.services.processors.base_processor import (
    Validator,
    ValidationResult,
    ProcessingStage,
)

try:
    from pydantic_ai import Agent
except ImportError:
    Agent = None
    logging.warning(
        "pydantic-ai is not installed. PydanticAIValidator will not function."
    )

logger = logging.getLogger(__name__)


class PydanticAIValidator(Validator):
    """
    Validator processor that uses PydanticAI Agent for advanced schema validation.
    Configurable via settings. Returns ValidationResult with errors if validation fails.
    """

    def __init__(
        self,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        schema_path: Optional[str] = None,
        metrics_collector=None,
    ):
        super().__init__(metrics_collector)
        self.model = model or settings.ai_pydantic_model
        self.schema_path = schema_path or os.path.join(
            os.path.dirname(__file__), "../../config/schema.json"
        )
        self.schema = self._load_schema()
        self.system_prompt = system_prompt or (
            "You are a strict JSON schema validator for video creation requests. "
            "Validate the provided input data against the following JSON schema. "
            'If the data is valid, return a JSON object: {"valid": true, "normalized_data": <normalized_data>}. '
            'If the data is invalid but can be auto-corrected to match the schema, return {"valid": true, "normalized_data": <corrected_data>}. '
            'If the data is invalid and cannot be auto-corrected, return {"valid": false, "errors": [<error messages>]}. '
            "Do not hallucinate fields. Only use the schema."
        )
        self.agent = None
        if Agent is not None:
            self.agent = Agent(self.model, system_prompt=self.system_prompt)

    def _load_schema(self):
        try:
            with open(os.path.abspath(self.schema_path), "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.error("Failed to load schema for PydanticAIValidator: %s", e)
            return None

    def _validate_sync(self, data: Any) -> ValidationResult:
        """Synchronous validation method to be run in a thread."""
        result = ValidationResult()
        if not settings.ai_pydantic_enabled:
            logger.info("PydanticAI validation is disabled in settings.")
            return result
        if self.agent is None or self.schema is None:
            error_msg = "pydantic-ai is not installed, Agent could not be initialized, or schema missing."
            logger.error(error_msg)
            result.add_error(error_msg)
            return result

        try:
            # Construct prompt with schema and data as JSON
            prompt = (
                "Validate the following data against the provided JSON schema. "
                f"Schema: {json.dumps(self.schema, indent=2)}\n\n"
                f"Data to validate: {json.dumps(data, indent=2)}\n\n"
                "Return a JSON object with 'valid' boolean and either 'normalized_data' or 'errors' array."
            )

            # Get the current event loop if it exists, otherwise create a new one
            try:
                loop = asyncio.get_event_loop()
                # If we got here, we're in an async context with a running event loop
                # Run the agent in a separate thread to avoid blocking the event loop
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(self._run_agent_in_thread, prompt, data)
                    return future.result()

            except RuntimeError:
                # No event loop running, we can create one
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    return loop.run_until_complete(self._run_agent_async(prompt, data))
                finally:
                    loop.close()

        except Exception as e:
            logger.error("PydanticAI Agent validation failed: %s", e, exc_info=True)
            result.add_error(f"PydanticAI Agent validation failed: {e}")
            return result

    def _run_agent_in_thread(self, prompt: str, data: Any) -> ValidationResult:
        """Run agent in a separate thread with its own event loop"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self._run_agent_async(prompt, data))
        finally:
            loop.close()

    async def _run_agent_async(self, prompt: str, data: Any) -> ValidationResult:
        """Run agent asynchronously"""
        result = ValidationResult()
        try:
            # Run the agent and get the response
            response = await self.agent.run(prompt)

            # Process response
            if response and hasattr(response, "content"):
                try:
                    response_data = json.loads(response.content)
                    if response_data.get("valid", False):
                        result.validated_data = response_data.get(
                            "normalized_data", data
                        )
                    else:
                        errors = response_data.get(
                            "errors", ["Unknown validation error"]
                        )
                        if isinstance(errors, list):
                            for err in errors:
                                result.add_error(str(err))
                        else:
                            result.add_error(str(errors))
                except json.JSONDecodeError as e:
                    logger.error("Failed to parse validation response as JSON: %s", e)
                    result.add_error("Failed to parse validation response as JSON")
            else:
                result.add_error("No output from PydanticAI Agent.")

        except Exception as e:
            logger.error("Error running PydanticAI Agent: %s", e, exc_info=True)
            result.add_error(f"Error running PydanticAI Agent: {str(e)}")

        return result

    def validate(self, data: Any) -> ValidationResult:
        """
        Validate input data using PydanticAI Agent. Returns ValidationResult.
        Args:
            data (Any): Input data to validate.
        Returns:
            ValidationResult: Result with errors if validation fails. If valid and agent returns normalized output, set result.validated_data.
        """
        # Start metrics collection
        metric = self._start_processing(ProcessingStage.VALIDATION)
        result = ValidationResult()

        try:
            # Delegate to sync validation method
            result = self._validate_sync(data)
            return result

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            error_msg = f"Unexpected error during PydanticAI validation: {str(e)}"
            logger.error(error_msg, exc_info=True)
            result.add_error(error_msg)
            return result

        finally:
            # Always end the processing metric
            self._end_processing(
                metric,
                success=result.is_valid,
                error_message="; ".join(result.errors) if result.errors else None,
                items_processed=1,
            )
        return self._validate_sync(data)
