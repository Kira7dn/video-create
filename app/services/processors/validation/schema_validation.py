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
from app.interfaces.validation import ValidationResult

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


class SchemaValidator:
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
            "You are a JSON Schema validator. Your ONLY job is to validate input data "
            "against the provided JSON schema. Do NOT add any fields or requirements "
            "that are not explicitly defined in the schema.",
            "## CRITICAL RULES:\n",
            "1. ONLY validate against the provided schema - ignore any other knowledge\n",
            "2. If a field is NOT in the schema, it's allowed (additional properties)\n",
            "3. ONLY check 'required' fields listed in the schema\n",
            "4. Do NOT invent or assume any required fields not in the schema\n",
            "5. Preserve all valid data exactly as provided\n",
            "6. For type mismatches, return an error (don't auto-correct)",
            "\n## VALIDATION PROCESS:\n",
            "- Check if required fields (if any) are present\n",
            "- Validate field types match the schema\n",
            "- Allow additional fields not defined in schema\n",
            "- Return is_valid=true if data conforms to schema",
        ]

        self.system_prompt = system_prompt or "\n".join(prompt_parts)

        # Initialize agent with output type validation and low temperature for consistency
        try:
            self.agent = Agent(
                self.model,
                system_prompt=self.system_prompt,
                output_type=AgentValidationSchema,
                model_settings={'temperature': 0.1}  # Low temperature for more deterministic responses
            )
        except Exception:
            # Fallback if model_settings not supported
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
            with open(self.schema_path, "r", encoding="utf-8") as f:
                schema = json.load(f)
                if not isinstance(schema, dict):
                    raise json.JSONDecodeError("Schema must be a JSON object", "", 0)
                return schema
        except (FileNotFoundError, json.JSONDecodeError, OSError) as e:
            logger.critical(
                "Schema file not found at %s", self.schema_path, exc_info=True
            )
            raise e

    async def validate_async(self, data: Any) -> ValidationResult[Dict[str, Any]]:
        """Validate data against the schema asynchronously using PydanticAI Agent.

        This method should be called from async contexts like ValidationProcessor.

        Args:
            data: The data to validate.

        Returns:
            ValidationResult: Result containing validation status and any errors.
        """
        # Initialize result once
        result = ValidationResult[Dict[str, Any]]()
        result.validated_data = data

        if not settings.ai_pydantic_enabled:
            logger.info("PydanticAI validation is disabled in settings")
            return result

        # Check if required AI settings are configured
        if not hasattr(settings, 'openai_api_key') or not settings.openai_api_key:
            logger.warning("OpenAI API key not configured, skipping AI validation")
            result.add_error("AI validation requires OpenAI API key configuration")
            return result

        # Convert input to dict if needed
        if not isinstance(data, dict):
            try:
                # Handle various input types
                if hasattr(data, '__dict__'):
                    data = data.__dict__
                elif hasattr(data, 'items'):
                    data = dict(data)
                else:
                    data = dict(data)
                result.validated_data = data  # Update with converted data
            except (TypeError, ValueError) as e:
                result.add_error(f"Input data must be dict-like: {str(e)}")
                return result

        try:
            # Convert data to JSON string for AI validation
            input_data = json.dumps(data, ensure_ascii=False, indent=2)
            schema_json = json.dumps(self.schema, indent=2)
            
            # Extract required fields from schema for explicit instruction
            required_fields = []
            if isinstance(self.schema, dict):
                # Top-level required fields
                if 'required' in self.schema:
                    required_fields.extend(self.schema['required'])
                
                # Segment required fields
                segments_schema = self.schema.get('properties', {}).get('segments', {})
                if 'items' in segments_schema and 'required' in segments_schema['items']:
                    segment_required = segments_schema['items']['required']
                    required_fields.extend([f"segments[].{field}" for field in segment_required])
            
            required_fields_text = "\n".join([f"- {field}" for field in required_fields]) if required_fields else "- No required fields defined in schema"

            # Create validation prompt with schema and data
            prompt = (
                "## VALIDATION TASK\n"
                f"Validate the following JSON data against the provided schema.\n\n"
                "## CRITICAL INSTRUCTIONS\n"
                "- ONLY validate against the schema provided below\n"
                "- Do NOT require any fields not listed in 'required' arrays\n"
                "- Do NOT invent or assume any missing properties\n"
                "- If a property is not in 'required', it's OPTIONAL\n"
                "- Additional properties are ALLOWED unless explicitly forbidden\n\n"
                "## REQUIRED FIELDS (ONLY THESE)\n"
                f"{required_fields_text}\n\n"
                "## SCHEMA\n"
                "```json\n"
                f"{schema_json}\n"
                "```\n\n"
                "## INPUT DATA\n"
                "```json\n"
                f"{input_data}\n"
                "```\n\n"
                "## VALIDATION RULES\n"
                "1. Check ONLY the required fields listed above\n"
                "2. Validate data types match the schema\n"
                "3. Allow any additional fields not in schema\n"
                "4. Return is_valid=true if data conforms to schema\n\n"
                "## RESPONSE FORMAT\n"
                "- Valid data: {\"is_valid\": true, \"normalized_data\": <original_data>}\n"
                "- Invalid data: {\"is_valid\": false, \"errors\": [\"specific_error\"]}"
            )

            # Get validation result from AI agent
            response = await self.agent.run(prompt)
            logger.debug("Processing AI agent response")

            # Handle invalid response format
            if not hasattr(response, "output") or not isinstance(response.output, AgentValidationSchema):
                error_msg = "Invalid response format from AI agent - missing or invalid output"
                logger.error(
                    "%s. Response type: %s, has output: %s",
                    error_msg,
                    type(response).__name__,
                    hasattr(response, "output"),
                )
                result.add_error(error_msg)
                return result

            # Process valid response
            agent_schema = response.output
            logger.debug(
                "Received valid validation schema, is_valid=%s",
                agent_schema.is_valid,
            )

            # Update result based on agent's response
            result.is_valid = agent_schema.is_valid
            if agent_schema.is_valid:
                # Use normalized data if available, otherwise keep current validated_data
                if agent_schema.normalized_data is not None:
                    result.validated_data = agent_schema.normalized_data
                # If normalized_data is None but validation passed, keep current data
            elif agent_schema.errors:
                for error in agent_schema.errors:
                    result.add_error(error)
            else:
                # No errors provided but validation failed
                result.add_error("Validation failed but no specific errors were provided")

        except (TypeError, ValueError, json.JSONDecodeError) as e:
            error_msg = f"Failed to process data for validation: {str(e)}"
            logger.error(error_msg, exc_info=True)
            result.add_error(error_msg)
        except (OSError, AttributeError) as e:
            error_msg = f"System error during validation: {str(e)}"
            logger.error(error_msg, exc_info=True)
            result.add_error(error_msg)
        except Exception as e:
            # Catch any other unexpected errors (e.g., AI API errors)
            error_msg = f"Unexpected error during AI validation: {str(e)}"
            logger.error(error_msg, exc_info=True)
            result.add_error(error_msg)
        
        logger.debug(
            "Validation completed with %d error(s)",
            len(result.errors) if result.errors else 0,
        )
        return result
