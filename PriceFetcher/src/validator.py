"""Validate extracted product data."""

import re
from decimal import Decimal, InvalidOperation
from typing import List, Optional

import structlog

from .models import ExtractionResult, ExtractedField, ValidationResult

logger = structlog.get_logger(__name__).bind(service='fetcher')


class Validator:
    """Validate extracted product data quality."""

    def __init__(
        self,
        min_confidence: float = 0.6,
        max_price_change_pct: float = 50.0,
    ):
        """
        Initialize validator with thresholds.

        Args:
            min_confidence: Minimum confidence score to consider valid
            max_price_change_pct: Max % price change before warning
        """
        self.min_confidence = min_confidence
        self.max_price_change_pct = max_price_change_pct
        logger.info(
            "validator_initialized",
            min_confidence=min_confidence,
            max_price_change_pct=max_price_change_pct,
        )

    def validate_extraction(
        self,
        extraction: ExtractionResult,
        previous_extraction: Optional[ExtractionResult] = None,
    ) -> ValidationResult:
        """
        Validate extracted data.

        Args:
            extraction: Current extraction result
            previous_extraction: Previous extraction for comparison

        Returns:
            ValidationResult with validity, errors, warnings, and confidence
        """
        errors: List[str] = []
        warnings: List[str] = []

        # Validate price (required)
        price_result = self._validate_price(extraction.price)
        if not price_result["valid"]:
            errors.extend(price_result["errors"])
        warnings.extend(price_result.get("warnings", []))

        # Validate title (optional but recommended)
        if extraction.title:
            title_result = self._validate_title(extraction.title)
            if not title_result["valid"]:
                warnings.extend(title_result["errors"])

        # Check for suspicious changes if we have previous data
        if previous_extraction:
            change_warnings = self._check_suspicious_changes(
                extraction, previous_extraction
            )
            warnings.extend(change_warnings)

        # Calculate overall confidence
        confidence = self._calculate_confidence(extraction, errors, warnings)

        # Check if confidence meets threshold
        if confidence < self.min_confidence:
            errors.append(f"Confidence {confidence:.2f} below threshold {self.min_confidence}")

        valid = len(errors) == 0

        result = ValidationResult(
            valid=valid,
            errors=errors,
            warnings=warnings,
            confidence=confidence,
        )

        logger.info(
            "validation_completed",
            valid=valid,
            confidence=confidence,
            errors=len(errors),
            warnings=len(warnings),
        )

        return result

    def _validate_price(self, price_field: ExtractedField) -> dict:
        """
        Validate price field.

        Args:
            price_field: Extracted price field

        Returns:
            Dict with valid, errors, warnings
        """
        if not price_field or not price_field.value:
            return {"valid": False, "errors": ["Price not found"]}

        price_str = price_field.value
        errors = []
        warnings = []

        # Extract numeric value
        numeric_match = re.search(r"(\d+\.?\d*)", price_str)
        if not numeric_match:
            errors.append("No numeric value in price")
            return {"valid": False, "errors": errors}

        try:
            price_value = Decimal(numeric_match.group(1))

            # Sanity checks
            if price_value <= 0:
                errors.append("Price is zero or negative")
            elif price_value > 100000:
                warnings.append("Price unusually high (>$100k)")
            elif price_value < 0.01:
                warnings.append("Price unusually low (<$0.01)")

        except InvalidOperation:
            errors.append("Invalid price format")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
        }

    def _validate_title(self, title_field: ExtractedField) -> dict:
        """
        Validate title field.

        Args:
            title_field: Extracted title field

        Returns:
            Dict with valid, errors
        """
        if not title_field or not title_field.value:
            return {"valid": False, "errors": ["Title not found"]}

        title = title_field.value
        errors = []

        if len(title) < 3:
            errors.append("Title too short")
        elif len(title) > 500:
            errors.append("Title too long")

        return {"valid": len(errors) == 0, "errors": errors}

    def _check_suspicious_changes(
        self,
        current: ExtractionResult,
        previous: ExtractionResult,
    ) -> List[str]:
        """
        Check for suspicious data changes.

        Args:
            current: Current extraction
            previous: Previous extraction

        Returns:
            List of warning messages
        """
        warnings = []

        # Check price change
        if current.price and previous.price:
            curr_price = self._extract_numeric_price(current.price)
            prev_price = self._extract_numeric_price(previous.price)

            if curr_price and prev_price and prev_price > 0:
                change_pct = abs(curr_price - prev_price) / prev_price * 100

                if change_pct > self.max_price_change_pct:
                    warnings.append(
                        f"Price changed by {change_pct:.1f}% "
                        f"(${prev_price} → ${curr_price})"
                    )

        # Check title change
        if current.title and previous.title:
            if (
                current.title.value
                and previous.title.value
                and current.title.value != previous.title.value
            ):
                warnings.append("Product title changed")

        # Check availability change
        if current.availability and previous.availability:
            curr_avail = "available" in (current.availability.value or "").lower()
            prev_avail = "available" in (previous.availability.value or "").lower()

            if curr_avail != prev_avail:
                status = "back in stock" if curr_avail else "out of stock"
                warnings.append(f"Availability changed: {status}")

        return warnings

    def _extract_numeric_price(self, price_field: ExtractedField) -> Optional[Decimal]:
        """
        Extract numeric price value from field.

        Args:
            price_field: Price field

        Returns:
            Decimal price or None
        """
        if not price_field or not price_field.value:
            return None

        match = re.search(r"(\d+\.?\d*)", price_field.value)
        if match:
            try:
                return Decimal(match.group(1))
            except (InvalidOperation, ValueError):
                pass

        return None

    def _calculate_confidence(
        self,
        extraction: ExtractionResult,
        errors: List[str],
        warnings: List[str],
    ) -> float:
        """
        Calculate overall confidence score.

        Args:
            extraction: Extraction result
            errors: List of errors
            warnings: List of warnings

        Returns:
            Confidence score (0.0 - 1.0)
        """
        if errors:
            return 0.0

        # Start with extraction method confidence
        confidences = []

        if extraction.price and extraction.price.confidence:
            confidences.append(extraction.price.confidence)

        if extraction.title and extraction.title.confidence:
            confidences.append(extraction.title.confidence)

        if extraction.availability and extraction.availability.confidence:
            confidences.append(extraction.availability.confidence)

        if extraction.image and extraction.image.confidence:
            confidences.append(extraction.image.confidence)

        # Average confidence from extraction methods
        base_confidence = sum(confidences) / len(confidences) if confidences else 0.5

        # Reduce for warnings (5% per warning)
        penalty = len(warnings) * 0.05
        final_confidence = max(0.0, base_confidence - penalty)

        return round(final_confidence, 2)
