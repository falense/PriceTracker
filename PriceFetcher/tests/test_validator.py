"""Tests for validator module."""

import pytest

from src.models import ExtractionResult, ExtractedField
from src.validator import Validator


class TestValidator:
    """Test Validator class."""

    def test_validate_valid_price(self):
        """Test validation of valid price."""
        extraction = ExtractionResult(
            price=ExtractedField(value="$29.99", method="css", confidence=0.9)
        )

        validator = Validator(min_confidence=0.6)
        result = validator.validate_extraction(extraction)

        assert result.valid is True
        assert len(result.errors) == 0
        assert result.confidence >= 0.6

    def test_validate_missing_price(self):
        """Test validation when price is missing."""
        extraction = ExtractionResult(
            price=ExtractedField(value=None, method=None, confidence=0.0)
        )

        validator = Validator(min_confidence=0.6)
        result = validator.validate_extraction(extraction)

        assert result.valid is False
        assert "Price not found" in result.errors

    def test_validate_invalid_price_format(self):
        """Test validation of invalid price format."""
        extraction = ExtractionResult(
            price=ExtractedField(value="Not a price", method="css", confidence=0.9)
        )

        validator = Validator(min_confidence=0.6)
        result = validator.validate_extraction(extraction)

        assert result.valid is False
        assert "No numeric value in price" in result.errors

    def test_validate_negative_price(self):
        """Test validation of negative price."""
        extraction = ExtractionResult(
            price=ExtractedField(value="-10.00", method="css", confidence=0.9)
        )

        validator = Validator(min_confidence=0.6)
        result = validator.validate_extraction(extraction)

        assert result.valid is False
        assert "Price is zero or negative" in result.errors

    def test_validate_price_too_high(self):
        """Test validation of unusually high price."""
        extraction = ExtractionResult(
            price=ExtractedField(value="$150000.00", method="css", confidence=0.9)
        )

        validator = Validator(min_confidence=0.6)
        result = validator.validate_extraction(extraction)

        # Should be valid but with warning
        assert result.valid is True
        assert any("unusually high" in w.lower() for w in result.warnings)

    def test_validate_low_confidence(self):
        """Test validation with confidence below threshold."""
        extraction = ExtractionResult(
            price=ExtractedField(value="$29.99", method="css", confidence=0.3)
        )

        validator = Validator(min_confidence=0.6)
        result = validator.validate_extraction(extraction)

        assert result.valid is False
        assert any("below threshold" in e.lower() for e in result.errors)

    def test_suspicious_price_change(self):
        """Test detection of suspicious price changes."""
        previous = ExtractionResult(
            price=ExtractedField(value="$100.00", method="css", confidence=0.9)
        )

        current = ExtractionResult(
            price=ExtractedField(value="$10.00", method="css", confidence=0.9)
        )

        validator = Validator(min_confidence=0.6, max_price_change_pct=50.0)
        result = validator.validate_extraction(current, previous)

        # Should be valid but with warning
        assert result.valid is True
        assert any("changed by" in w.lower() for w in result.warnings)

    def test_title_validation(self):
        """Test title validation."""
        extraction = ExtractionResult(
            price=ExtractedField(value="$29.99", method="css", confidence=0.9),
            title=ExtractedField(value="Test Product Name", method="css", confidence=0.9),
        )

        validator = Validator(min_confidence=0.6)
        result = validator.validate_extraction(extraction)

        assert result.valid is True
        assert len(result.errors) == 0
