"""
Basic validation for video creation data.

This module provides basic validation for video creation requests, ensuring that
all required fields are present and properly formatted.
"""

import logging
from typing import Any, Dict

from app.interfaces.validation import IValidator, ValidationResult

logger = logging.getLogger(__name__)


class BasicValidator(IValidator[Dict[str, Any]]):
    """Validates the basic structure of video creation data.

    This validator performs minimal validation to ensure:
    - Required top-level fields exist (title, description, segments)
    - Segments is a non-empty list of dictionaries
    - Each segment has an 'id' field
    """

    async def validate_async(self, data: Any) -> ValidationResult[Dict[str, Any]]:
        """Asynchronously validate the input data structure.

        Args:
            data: The input data to validate

        Returns:
            ValidationResult with validation status and any errors
        """
        # Gọi phương thức validate đồng bộ
        return self.validate(data)

    def validate(self, data: Any) -> ValidationResult[Dict[str, Any]]:
        """Synchronously validate the input data structure.

        Args:
            data: The input data to validate

        Returns:
            ValidationResult with validation status and any errors
        """
        result = ValidationResult[Dict[str, Any]](validated_data=data)

        try:
            # Basic structure validation
            self._validate_basic_structure(data, result)

        except (AttributeError, TypeError) as e:
            # These are the most common exceptions that might occur during dictionary access
            logger.error(
                "Validation error in BasicValidator: %s", str(e), exc_info=True
            )
            result.add_error(f"Validation error: {str(e)}")
        except Exception as e:  # pylint: disable=broad-except
            # Keep this as a last resort, but log it as a critical error
            logger.critical(
                "Unexpected error in BasicValidator: %s", str(e), exc_info=True
            )
            result.add_error("An unexpected error occurred during validation")

        return result

    def _validate_basic_structure(self, data: Any, result: ValidationResult) -> None:
        """Validate the basic structure of the input data."""
        if not isinstance(data, dict):
            result.add_error("Input data must be a dictionary")
            return

        # Check required top-level fields
        for field in ["title", "description", "segments"]:
            if field not in data:
                result.add_error(f"Missing required field: '{field}'")

        # Validate segments is a non-empty list
        if "segments" in data:
            if not isinstance(data["segments"], list):
                result.add_error("'segments' must be a list")
            elif not data["segments"]:
                result.add_error("'segments' cannot be empty")
            else:
                # Validate each segment
                for i, segment in enumerate(data["segments"]):
                    if not isinstance(segment, dict):
                        result.add_error(f"Segment {i} must be a dictionary")
                        continue

                    # Only check for required 'id' field
                    if "id" not in segment:
                        result.add_error(f"Segment {i} is missing required 'id' field")
