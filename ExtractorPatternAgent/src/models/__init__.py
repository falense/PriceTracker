"""Data models for extraction patterns and validation results."""

from .pattern import Pattern, SelectorPattern, PatternResult
from .validation import ValidationResult, FieldValidation

__all__ = [
    "Pattern",
    "SelectorPattern",
    "PatternResult",
    "ValidationResult",
    "FieldValidation",
]
