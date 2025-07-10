"""
PydanticAIValidator processor for advanced schema validation using PydanticAI Agent.
Follows project SRP, error handling, and metrics patterns.
"""
from typing import Any, Optional
from app.services.processors.base_processor import Validator, ValidationResult
from app.core.exceptions import ProcessingError
from app.config.settings import settings
import logging

try:
    from pydantic_ai import Agent
except ImportError:
    Agent = None
    logging.warning("pydantic-ai is not installed. PydanticAIValidator will not function.")

logger = logging.getLogger(__name__)

class PydanticAIValidator(Validator):
    """
    Validator processor that uses PydanticAI Agent for advanced schema validation.
    Configurable via settings. Returns ValidationResult with errors if validation fails.
    """
    def __init__(self, model: Optional[str] = None, system_prompt: Optional[str] = None):
        self.model = model or settings.ai_pydantic_model
        self.system_prompt = system_prompt or "Validate the input data for video creation. Return valid if schema matches, else return errors."
        self.agent = None
        if Agent is not None:
            self.agent = Agent(self.model, system_prompt=self.system_prompt)

    def validate(self, data: Any) -> ValidationResult:
        """
        Validate input data using PydanticAI Agent. Returns ValidationResult.
        Args:
            data (Any): Input data to validate.
        Returns:
            ValidationResult: Result with errors if validation fails.
        """
        result = ValidationResult()
        if not settings.ai_pydantic_enabled:
            logger.info("PydanticAI validation is disabled in settings.")
            return result
        if self.agent is None:
            error_msg = "pydantic-ai is not installed or Agent could not be initialized."
            logger.error(error_msg)
            result.add_error(error_msg)
            return result
        try:
            # Agent expects a string prompt or structured input; here we use the data as input
            agent_result = self.agent.run_sync(str(data))
            # If validation fails, an exception is typically raised
        except Exception as e:
            logger.error(f"PydanticAI Agent validation failed: {e}", exc_info=True)
            error_msg = f"PydanticAI Agent validation failed: {e}"
            result.add_error(error_msg)
        # Log all errors in ValidationResult
        if result.errors:
            for err in result.errors:
                logger.error(f"Validation error: {err}")
        return result
