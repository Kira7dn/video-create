"""Validation processor for executing multiple validators sequentially.

This module provides ValidationProcessor that allows combining multiple validators
into a single processor that runs them in sequence. It follows the same interface
as other processors in the system for consistency.
"""

import logging
from typing import Any, Dict, List, TypeVar, Generic, Type

from pydantic import ValidationError
from app.services.processors.core.base_processor import BaseProcessor
from app.interfaces.validation import IValidator, ValidationResult

# Import specific validators
from .schema_validation import SchemaValidator
from .basic_validation import BasicValidator

T = TypeVar("T")

logger = logging.getLogger(__name__)


class ValidationProcessor(BaseProcessor):
    """A processor that chains multiple validators together and executes them sequentially.

    This processor runs each validator in sequence and combines their results.
    It's designed to work with the processor pipeline and can be used as a drop-in replacement
    for any single processor that needs validation.

    Attributes:
        validators: List of validators to execute in sequence
    """

    def __init__(self) -> None:
        """Initialize the ValidationProcessor with default validators."""
        super().__init__()
        self.validators: List[IValidator] = [
            BasicValidator(),
            SchemaValidator(),
        ]

    async def process(self, input_data: Any, **kwargs) -> Any:
        """
        Process input data by validating it through all validators in sequence.

        Args:
            input_data: Data to validate
            **kwargs: Additional arguments passed to validators

        Returns:
            The validated data if successful

        Raises:
            ValidationError: If validation fails
        """
        result = await self._validate(input_data, **kwargs)

        if not result.is_valid:
            error_msg = "; ".join(result.errors)
            logger.error("Validation failed: %s", error_msg)
            raise ValidationError(errors=result.errors, model=type(input_data))

        return result.validated_data

    async def _validate(self, data: Any, **kwargs) -> ValidationResult[Any]:
        """Run validation on the input data.

        Args:
            data: Data to validate
            **kwargs: Additional arguments for validation

        Returns:
            ValidationResult with validation status and any errors
        """
        result = ValidationResult[Any](validated_data=data)
        current_data = data

        for validator in self.validators:
            try:
                # Run the validator
                validator_result = validator.validate(current_data, **kwargs)

                # Update result with validation errors
                if not validator_result.is_valid:
                    result.is_valid = False
                    result.errors.extend(validator_result.errors)
                    break  # Stop on first error

                # Update current data with validated data if available
                if validator_result.validated_data is not None:
                    current_data = validator_result.validated_data
                    result.validated_data = current_data

            except Exception as e:
                logger.error("Validator %s failed: %s", type(validator).__name__, str(e), exc_info=True)
                result.is_valid = False
                result.add_error(f"Validator {type(validator).__name__} failed: {str(e)}")
                break  # Stop on first error

        return result
