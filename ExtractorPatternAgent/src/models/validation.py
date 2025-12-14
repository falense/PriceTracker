"""Data models for validation results."""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class FieldValidation:
    """Validation result for a single field extraction."""
    field_name: str
    success: bool
    extracted_value: Optional[str] = None
    expected_format: Optional[str] = None
    error_message: Optional[str] = None
    confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "field_name": self.field_name,
            "success": self.success,
            "confidence": self.confidence,
        }
        if self.extracted_value:
            result["extracted_value"] = self.extracted_value
        if self.expected_format:
            result["expected_format"] = self.expected_format
        if self.error_message:
            result["error_message"] = self.error_message
        return result


@dataclass
class ValidationResult:
    """Complete validation result for pattern testing."""
    url: str
    success: bool
    field_validations: List[FieldValidation] = field(default_factory=list)
    overall_confidence: float = 0.0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    execution_time: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "url": self.url,
            "success": self.success,
            "field_validations": [fv.to_dict() for fv in self.field_validations],
            "overall_confidence": self.overall_confidence,
            "errors": self.errors,
            "warnings": self.warnings,
            "execution_time": self.execution_time,
        }

    @property
    def successful_fields(self) -> List[str]:
        """Return list of successfully validated fields."""
        return [fv.field_name for fv in self.field_validations if fv.success]

    @property
    def failed_fields(self) -> List[str]:
        """Return list of failed field validations."""
        return [fv.field_name for fv in self.field_validations if not fv.success]

    def get_field_validation(self, field_name: str) -> Optional[FieldValidation]:
        """Get validation result for a specific field."""
        for fv in self.field_validations:
            if fv.field_name == field_name:
                return fv
        return None
