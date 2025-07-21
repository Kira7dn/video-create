"""
Schema validation using Pydantic AI.

This module provides AI-powered validation using PydanticAI Agent, allowing for
complex validation logic that goes beyond static schema validation.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional, TypeVar

from pydantic import BaseModel, Field

from pydantic_ai import Agent

from app.config import settings
from app.interfaces.validation import IValidator, ValidationResult

logger = logging.getLogger(__name__)


class AgentValidationSchema(BaseModel):
    """Structured schema for validation response from the AI agent.

    This class defines the expected structure of the validation response
    returned by the AI agent. It is used for documentation and type hinting
    purposes to understand the contract between our code and the AI agent.
    """

    is_valid: bool = Field(..., description="Whether the input data is valid")
    normalized_data: Optional[Dict[str, Any]] = Field(
        None, description="Normalized data, present when valid is true"
    )
    errors: Optional[List[str]] = Field(
        None, description="List of error messages, present when valid is false"
    )


T = TypeVar("T")


class SchemaValidator(IValidator[Dict[str, Any]]):
    """Validates data against a JSON schema using AI-powered validation.

    This validator uses Pydantic AI to validate data against a JSON schema,
    providing more flexible validation than static schema validation.
    """

    def __init__(
        self,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        schema_path: Optional[str] = None,
    ) -> None:
        """Initialize the SchemaValidator.

        Args:
            model: The AI model to use for validation. Defaults to settings.ai_pydantic_model.
            system_prompt: Custom system prompt for the AI agent.
            schema_path: Path to the JSON schema file. Defaults to '../../config/schema.json'.

        Raises:
            FileNotFoundError: If schema file is not found.
            json.JSONDecodeError: If schema file contains invalid JSON.
            OSError: For other file-related errors.
        """
        self.model = model or settings.ai_pydantic_model
        # Sử dụng đường dẫn schema từ cấu hình settings
        self.schema_path = schema_path or os.path.abspath(settings.schema_path)
        self.schema = self._load_schema()

        # System prompt defines the agent's role and basic behavior
        prompt_parts = [
            "You are an AI assistant specialized in JSON Schema validation and "
            "data normalization. Your task is to validate input data against a "
            "provided schema and return structured results.",
            "## STRICT RULES (MUST FOLLOW):\n",
            "1. NEVER add, modify, or remove any field names from the input data\n",
            "2. ONLY use field names and types defined in the schema\n",
            "3. For invalid values, either correct them to match the schema or return an error\n",
            "4. For missing required fields, use sensible defaults when possible\n",
            "5. NEVER modify field names, even if they contain typos (return error instead)\n",
            "6. Preserve all valid data exactly as provided",
            "\n## VALIDATION BEHAVIOR:\n",
            "- If a field is valid: keep it exactly as is\n",
            "- If a field is invalid but can be corrected: fix just the value\n",
            "- If a field is invalid and cannot be corrected: add an error message\n",
            "- If a required field is missing: use a default value or add an error",
        ]

        self.system_prompt = system_prompt or "\n".join(prompt_parts)

        # Initialize agent with output type validation
        self.agent = Agent(
            self.model,
            system_prompt=self.system_prompt,
            output_type=AgentValidationSchema,
        )

    def _load_schema(self) -> dict:
        """Load and parse JSON schema from file.

        Returns:
            dict: The parsed JSON schema.

        Raises:
            FileNotFoundError: If schema file is not found.
            json.JSONDecodeError: If schema file contains invalid JSON.
            OSError: For other file-related errors.
        """
        try:
            with open(os.path.abspath(self.schema_path), "r", encoding="utf-8") as f:
                schema = json.load(f)
                if not isinstance(schema, dict):
                    raise json.JSONDecodeError("Schema must be a JSON object", "", 0)
                return schema
        except FileNotFoundError:
            logger.critical(
                "Schema file not found at %s", self.schema_path, exc_info=True
            )
            raise
        except json.JSONDecodeError:
            logger.critical(
                "Invalid JSON in schema file %s", self.schema_path, exc_info=True
            )
            raise
        except OSError:
            logger.critical(
                "Failed to load schema from %s", self.schema_path, exc_info=True
            )
            raise

    async def _validate_async(self, data: Any) -> ValidationResult[Dict[str, Any]]:
        """Asynchronously validate data against the schema.

        This is the primary validation method that should be used in async contexts.
        It uses AI-powered validation to check data against the schema.

        Args:
            data: The data to validate. Will be converted to dict if not already.

        Returns:
            ValidationResult containing validation status, any errors, and normalized data
        """
        if not isinstance(data, dict):
            try:
                data = dict(data)
            except (TypeError, ValueError) as e:
                result = ValidationResult[Dict[str, Any]]()
                result.add_error(f"Input data must be dict-like: {str(e)}")
                return result
        result = ValidationResult[Dict[str, Any]](validated_data=data)

        try:
            # Convert data to JSON string for AI validation
            input_data = json.dumps(data, ensure_ascii=False, indent=2)
            schema_json = json.dumps(self.schema, indent=2)

            # Create validation prompt with schema and data
            prompt = (
                "## VALIDATION TASK\n"
                f"Validate and normalize the following JSON data against the schema.\n\n"
                "## SCHEMA\n"
                "```json\n"
                f"{schema_json}\n"
                "```\n\n"
                "## INPUT DATA\n"
                "```json\n"
                f"{input_data}\n"
                "```\n\n"
                "## INSTRUCTIONS\n"
                "1. If the data is valid, return a JSON object with: "
                '{"is_valid": true, "normalized_data": <original_data>}\n\n'
                "2. If the data can be auto-corrected to be valid, return: "
                '{"is_valid": true, "normalized_data": <corrected_data>}\n\n'
                "3. If the data is invalid and cannot be corrected, return: "
                '{"is_valid": false, "errors": ["error1", "error2"]}'
            )

            # Get validation result from AI agent
            response = await self.agent.run(prompt)

            # Log thông tin cơ bản về response
            logger.debug("Processing AI agent response")

            # Xử lý response từ AI agent
            if hasattr(response, "output") and isinstance(
                response.output, AgentValidationSchema
            ):
                agent_schema = response.output
                logger.debug(
                    "Received valid validation schema, is_valid=%s",
                    agent_schema.is_valid,
                )

                # Chuyển đổi trực tiếp sang ValidationResult
                result = ValidationResult[Dict[str, Any]]()
                result.is_valid = agent_schema.is_valid

                if agent_schema.is_valid:
                    result.validated_data = agent_schema.normalized_data or data

                if not agent_schema.is_valid and agent_schema.errors:
                    for error in agent_schema.errors:
                        result.add_error(error)

                logger.debug(
                    "Validation completed with %d error(s)",
                    len(result.errors) if result.errors else 0,
                )
                return result
            else:
                error_msg = (
                    "Invalid response format from AI agent - missing or invalid output"
                )
            logger.error(
                "%s. Response type: %s, has output: %s",
                error_msg,
                type(response).__name__,
                hasattr(response, "output"),
            )
            result = ValidationResult[Dict[str, Any]]()
            result.add_error(error_msg)
            return result

        except (TypeError, ValueError, json.JSONDecodeError) as e:
            error_msg = f"Failed to process data for validation: {str(e)}"
            logger.error(error_msg, exc_info=True)
            result = ValidationResult[Dict[str, Any]]()
            result.add_error(error_msg)
            return result
        except (OSError, AttributeError) as e:
            error_msg = f"System error during validation: {str(e)}"
            logger.error(error_msg, exc_info=True)
            result = ValidationResult[Dict[str, Any]]()
            result.add_error(error_msg)
            return result

    def validate(self, data: Any) -> ValidationResult[Dict[str, Any]]:
        """Synchronously validate data against the schema.

        This is a convenience method that wraps the async version.
        Note: Using validate_async() directly is preferred for better performance.

        Args:
            data: The data to validate.

        Returns:
            ValidationResult: Result containing validation status and any errors.
        """
        result = ValidationResult[Dict[str, Any]](validated_data=data)

        if not settings.ai_pydantic_enabled:
            logger.info("PydanticAI validation is disabled in settings")
            return result

        try:
            # Sử dụng phiên bản đồng bộ từ IValidator
            return super().validate(data)
        except (OSError, json.JSONDecodeError, AttributeError) as e:
            error_msg = f"Failed to process validation: {str(e)}"
            logger.error(error_msg, exc_info=True)
            result.add_error(error_msg)
            return result

    async def validate_async(self, data: Any) -> ValidationResult[Dict[str, Any]]:
        """Validate data against the schema asynchronously using PydanticAI Agent.

        This method should be called from async contexts like ValidationProcessor.

        Args:
            data: The data to validate.

        Returns:
            ValidationResult: Result containing validation status and any errors.
        """
        result = ValidationResult[Dict[str, Any]](validated_data=data)

        if not settings.ai_pydantic_enabled:
            logger.info("PydanticAI validation is disabled in settings")
            return result

        try:
            return await self._validate_async(data)
        except (OSError, json.JSONDecodeError, AttributeError) as e:
            error_msg = f"Failed to process validation: {str(e)}"
            logger.error(error_msg, exc_info=True)
            result.add_error(error_msg)
            return result
