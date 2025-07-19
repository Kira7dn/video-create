"""
Data validation components.

This module contains processors and validators for data validation,
including basic validation and AI-assisted schema validation.
"""

from app.interfaces.validation import IValidator, ValidationResult
from .basic_validation import BasicValidator
from .schema_validation import SchemaValidator
from .processor import ValidationProcessor

# Re-export types for easier imports
__all__ = [
    # Base interfaces
    "IValidator",
    "ValidationResult",
    # Concrete validators
    "BasicValidator",
    "SchemaValidator",
    # Main processor
    "ValidationProcessor",
]
