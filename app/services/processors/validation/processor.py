"""Validation processor for executing multiple validators sequentially.

This module provides ValidationProcessor that allows combining multiple validators
into a single processor that runs them in sequence. It follows the same interface
as other processors in the system for consistency.
"""

import logging
from typing import Any, List, TypeVar

from app.services.processors.core.base_processor import AsyncProcessor
from app.interfaces.validation import IValidator, ValidationResult
from app.services.processors.core.metrics import ProcessingStage

from .schema_validation import SchemaValidator
from .basic_validation import BasicValidator

T = TypeVar("T")

logger = logging.getLogger(__name__)


class ValidationProcessor(AsyncProcessor):
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
        This is the internal implementation of the async processing.

        Args:
            input_data: Data to validate
            **kwargs: Additional arguments

        Returns:
            The validated data if all validations pass

        Raises:
            ValueError: If validation fails and stop_on_error is True
        """
        # Start metrics for validation stage
        metric = self._start_processing(ProcessingStage.VALIDATION)
        try:
            result = await self._validate(input_data)
            if not result.is_valid and result.errors:
                error_msg = "\n".join(result.errors)
                # Increment error counter
                self._end_processing(metric, success=False, error_message=error_msg)
                raise ValueError(error_msg)
            self._end_processing(metric, success=True)
            return result.validated_data
        except Exception as e:
            self._end_processing(metric, success=False, error_message=str(e))
            raise

    async def _validate(self, data: Any) -> ValidationResult[Any]:
        """Run validation on the input data.

        Args:
            data: Data to validate

        Returns:
            ValidationResult with validation status and any errors
        """
        result = ValidationResult[Any](validated_data=data)
        current_data = data

        for validator in self.validators:
            validator_name = type(validator).__name__
            self.logger.debug("Running validator: %s", validator_name)

            try:
                # Use validate_async if available, otherwise fall back to sync validate
                if hasattr(validator, "validate_async") and callable(
                    validator.validate_async
                ):
                    validator_result = await validator.validate_async(current_data)
                else:
                    validator_result = validator.validate(current_data)

                self.logger.debug(
                    "Validator %s completed with result: %s",
                    validator_name,
                    validator_result,
                )
                self.logger.debug("validator_result: %s", validator_result)
                if validator_result.is_valid:
                    # Validation passed - update data for next validator
                    if validator_result.validated_data is not None:
                        current_data = validator_result.validated_data
                        result.validated_data = validator_result.validated_data
                    result.is_valid = True
                else:
                    # Validation failed - stop processing
                    result.is_valid = False
                    if validator_result.errors:
                        result.errors.extend(validator_result.errors)
                    break

            except Exception as e:  # pylint: disable=broad-except
                error_msg = f"Validator {validator_name} failed: {str(e)}"
                self.logger.error(error_msg, exc_info=True)
                result.add_error(error_msg)
                result.is_valid = False
                break
        return result
