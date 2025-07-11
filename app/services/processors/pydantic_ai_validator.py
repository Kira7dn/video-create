"""
PydanticAIValidator processor for advanced schema validation using PydanticAI Agent.
Follows project SRP, error handling, and metrics patterns.
"""
from typing import Any, Optional
from app.services.processors.base_processor import Validator, ValidationResult
from app.core.exceptions import ProcessingError
from app.config.settings import settings
import logging
import json
import os

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
    def __init__(self, model: Optional[str] = None, system_prompt: Optional[str] = None, schema_path: Optional[str] = None):
        self.model = model or settings.ai_pydantic_model
        self.schema_path = schema_path or os.path.join(os.path.dirname(__file__), '../../config/schema.json')
        self.schema = self._load_schema()
        self.system_prompt = system_prompt or (
            "You are a strict JSON schema validator for video creation requests. "
            "Validate the provided input data against the following JSON schema. "
            "If the data is valid, return a JSON object: {\"valid\": true, \"normalized_data\": <normalized_data>}. "
            "If the data is invalid but can be auto-corrected to match the schema, return {\"valid\": true, \"normalized_data\": <corrected_data>}. "
            "If the data is invalid and cannot be auto-corrected, return {\"valid\": false, \"errors\": [<error messages>]}. "
            "Do not hallucinate fields. Only use the schema."
        )
        self.agent = None
        if Agent is not None:
            self.agent = Agent(self.model, system_prompt=self.system_prompt)

    def _load_schema(self):
        try:
            with open(os.path.abspath(self.schema_path), "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load schema for PydanticAIValidator: {e}")
            return None

    async def validate(self, data: Any) -> ValidationResult:
        """
        Validate input data using PydanticAI Agent. Returns ValidationResult.
        Args:
            data (Any): Input data to validate.
        Returns:
            ValidationResult: Result with errors if validation fails. If valid and agent returns normalized output, set result.validated_data.
        """
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
                "Schema:\n" + json.dumps(self.schema, ensure_ascii=False, indent=2) +
                "\nData:\n" + json.dumps(data, ensure_ascii=False, indent=2)
            )
            agent_result = await self.agent.run(prompt)
            # Expect agent_result.output to be a JSON string
            output = getattr(agent_result, "output", None)
            if output:
                try:
                    parsed = json.loads(output) if isinstance(output, str) else output
                    if parsed.get("valid") is True:
                        result.validated_data = parsed.get("normalized_data", data)
                    else:
                        errors = parsed.get("errors")
                        if errors:
                            for err in errors:
                                result.add_error(str(err))
                        else:
                            result.add_error("Validation failed but no errors provided by agent.")
                except Exception as parse_exc:
                    logger.error(f"Failed to parse agent output: {parse_exc}")
                    result.add_error(f"Failed to parse agent output: {parse_exc}")
            else:
                result.add_error("No output from PydanticAI Agent.")
        except Exception as e:
            logger.error(f"PydanticAI Agent validation failed: {e}", exc_info=True)
            error_msg = f"PydanticAI Agent validation failed: {e}"
            result.add_error(error_msg)
        if result.errors:
            for err in result.errors:
                logger.error(f"Validation error: {err}")
        return result
