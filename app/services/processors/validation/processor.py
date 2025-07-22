"""Validation processor for executing multiple validators sequentially.

This module provides ValidationProcessor that allows combining multiple validators
into a single processor that runs them in sequence. It follows the same interface
as other processors in the system for consistency.
"""

import json
import logging
from typing import Any, List, TypeVar

from app.services.processors.core.base_processor import AsyncProcessor
from app.interfaces.validation import IValidator, ValidationResult
from app.services.processors.core.metrics import ProcessingStage

# Import specific validators
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
            **kwargs: Additional arguments passed to validators

        Returns:
            The validated data if all validations pass

        Raises:
            ValueError: If validation fails and stop_on_error is True
        """
        # Start metrics for validation stage
        metric = self.metrics_collector.start_stage(ProcessingStage.VALIDATION)
        try:
            result = await self._validate(input_data, **kwargs)
            if not result.is_valid and result.errors:
                error_msg = "\n".join(result.errors)
                # Increment error counter
                self.metrics_collector.increment_counter("validation_errors")
                self.metrics_collector.end_stage(
                    metric, success=False, error_message=error_msg
                )
                raise ValueError(error_msg)
            self.metrics_collector.end_stage(metric, success=True)
            return result.validated_data
        except Exception as e:
            self.metrics_collector.end_stage(
                metric, success=False, error_message=str(e)
            )
            raise

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
            validator_name = type(validator).__name__
            self.logger.debug("Running validator: %s", validator_name)

            # Start tracking validator execution time
            metric = self.metrics_collector.start_stage(ProcessingStage.PROCESSING)
            try:
                # Use validate_async if available, otherwise fall back to sync
                if hasattr(validator, "validate_async"):
                    validator_result = await validator.validate_async(
                        current_data, **kwargs
                    )
                else:
                    validator_result = validator.validate(current_data, **kwargs)

                self.logger.debug(
                    "Validator %s completed with result: %s",
                    validator_name,
                    validator_result,
                )

                # Handle validation result
                if validator_result is None:
                    error_msg = f"Validator {validator_name} returned None instead of ValidationResult"
                    self.logger.error(error_msg)
                    result.add_error(error_msg)
                    result.is_valid = False
                    self.metrics_collector.end_stage(
                        metric, success=False, error_message=error_msg
                    )
                    break

                if not validator_result.is_valid:
                    error_msg = (
                        f"{validator_name} failed: {', '.join(validator_result.errors)}"
                    )
                    result.is_valid = False
                    result.errors.extend(validator_result.errors)
                    # Increment validation error counter
                    self.metrics_collector.increment_counter(
                        f"validator_{validator_name.lower()}_errors"
                    )
                    self.metrics_collector.end_stage(
                        metric, success=False, error_message=error_msg
                    )
                    break

                if validator_result.validated_data is not None:
                    current_data = validator_result.validated_data
                    result.validated_data = current_data

                # End stage successfully if we got here
                self.metrics_collector.end_stage(metric, success=True)

            except (ValueError, TypeError, json.JSONDecodeError, OSError) as e:
                error_msg = f"Validator {validator_name} failed: {str(e)}"
                self.logger.error(error_msg, exc_info=True)
                result.is_valid = False
                result.add_error(error_msg)
                # Increment exception counter
                self.metrics_collector.increment_counter("validator_exceptions")
                self.metrics_collector.end_stage(
                    metric, success=False, error_message=error_msg
                )
                break  # Stop on first error

        # Record final validation result
        if result.is_valid:
            self.metrics_collector.increment_counter("validation_success")
        else:
            self.metrics_collector.increment_counter("validation_failed")
        return result
