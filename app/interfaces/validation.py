"""
Validation-related interfaces and data structures.
"""

import asyncio
from dataclasses import dataclass, field
from typing import (
    Any,
    Generic,
    List,
    Optional,
    Protocol,
    TypeVar,
    runtime_checkable,
)

T = TypeVar("T")


@dataclass
class ValidationResult(Generic[T]):
    """Result of a validation operation with generic type support."""

    is_valid: bool = True
    errors: List[str] = field(default_factory=list)
    validated_data: Optional[T] = None

    def add_error(self, error: str) -> None:
        """Add a validation error."""
        self.errors.append(error)
        self.is_valid = False

    def __bool__(self) -> bool:
        return self.is_valid

    def __str__(self) -> str:
        return f"ValidationResult(valid={self.is_valid}, errors={len(self.errors)})"


@runtime_checkable
class IValidator(Protocol[T]):
    """Interface for data validation with type support.

    Implementations should validate input data and return a ValidationResult
    containing the validation status, any errors, and potentially normalized data.
    """

    async def validate_async(self, data: Any) -> ValidationResult[T]:
        """Asynchronously validate the given data.

        This is the preferred method for validation as it supports both synchronous
        and asynchronous operations.

        Args:
            data: The data to validate

        Returns:
            Awaitable[ValidationResult] containing validation status and any errors
        """

    def validate(self, data: Any) -> ValidationResult[T]:
        """Synchronously validate the given data.

        Note: This is a convenience method that wraps the async version.
        For better performance, prefer using validate_async() directly.

        Args:
            data: The data to validate

        Returns:
            ValidationResult containing validation status and any errors
        """

        return asyncio.run(self.validate_async(data))
