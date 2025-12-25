"""Apply extraction patterns to HTML using Python extractors."""

import sys
from pathlib import Path
from typing import Optional
from decimal import Decimal

import structlog

from .models import ExtractionResult, ExtractedField

logger = structlog.get_logger(__name__).bind(service="fetcher")

# Add ExtractorPatternAgent to path for generated_extractors import
REPO_ROOT = Path(__file__).parent.parent.parent
EXTRACTOR_PATH = REPO_ROOT / "ExtractorPatternAgent"
if str(EXTRACTOR_PATH) not in sys.path:
    sys.path.insert(0, str(EXTRACTOR_PATH))


class Extractor:
    """Apply Python extractors to HTML to extract product data."""

    def extract_with_domain(self, html: str, domain: str) -> tuple[ExtractionResult, Optional[str]]:
        """
        Extract data using Python extractor module for domain.

        Args:
            html: Page HTML content
            domain: Store domain (e.g., "komplett.no")

        Returns:
            Tuple of (ExtractionResult with extracted fields, extractor module name)
            Module name will be None if extraction failed or no extractor found
        """
        logger.debug("extraction_started", domain=domain)

        try:
            # Import generated_extractors API
            from generated_extractors import extract_from_html, get_parser

            # Normalize domain (remove www.)
            normalized_domain = domain.lower().replace("www.", "")

            # Determine which module will be used
            # Convert domain to module name (e.g., "komplett.no" -> "komplett_no")
            module_name = normalized_domain.replace(".", "_").replace("-", "_")

            # Check if parser exists for this domain
            parser_module = get_parser(normalized_domain)
            if parser_module is None:
                logger.warning("no_extractor_found", domain=domain, module=module_name)
                return self._empty_result(errors=["No extractor found for domain"]), None

            # Extract using Python module
            result = extract_from_html(normalized_domain, html)

            if result is None:
                logger.warning("extraction_returned_empty", domain=domain, module=module_name)
                return self._empty_result(errors=["Extractor returned no result"]), module_name

            # Convert to ExtractionResult format
            extraction = self._convert_to_extraction_result(result)

            if extraction.errors:
                logger.error(
                    "extraction_reported_errors",
                    domain=domain,
                    module=module_name,
                    errors=extraction.errors,
                )
            elif extraction.warnings:
                logger.warning(
                    "extraction_reported_warnings",
                    domain=domain,
                    module=module_name,
                    warnings=extraction.warnings,
                )

            logger.info(
                "extraction_completed",
                domain=domain,
                module=module_name,
                price_found=extraction.price.value is not None,
                method="python_extractor",
            )

            return extraction, module_name

        except ImportError as e:
            logger.exception("extractor_import_failed", domain=domain, error=str(e))
            return self._empty_result(errors=[f"Extractor import failed: {e}"]), None
        except Exception as e:
            logger.exception("extraction_failed", domain=domain, error=str(e))
            return self._empty_result(errors=[str(e)]), None

    def _convert_to_extraction_result(self, result) -> ExtractionResult:
        """Convert ExtractorResult to ExtractionResult model."""

        # Convert each field
        price_value = getattr(result, "price", None)
        if price_value and isinstance(price_value, (Decimal, float, int, str)):
            try:
                price = ExtractedField(
                    value=str(price_value), method="python_extractor", confidence=1.0
                )
            except Exception:
                price = ExtractedField(value=None, method=None, confidence=0.0)
        else:
            price = ExtractedField(value=None, method=None, confidence=0.0)

        title_value = getattr(result, "title", None)
        title = ExtractedField(
            value=title_value,
            method="python_extractor" if title_value else None,
            confidence=1.0 if title_value else 0.0,
        )

        image_value = getattr(result, "image", None)
        image = ExtractedField(
            value=image_value,
            method="python_extractor" if image_value else None,
            confidence=1.0 if image_value else 0.0,
        )

        availability_value = getattr(result, "availability", None)
        availability = ExtractedField(
            value=availability_value,
            method="python_extractor" if availability_value else None,
            confidence=1.0 if availability_value else 0.0,
        )

        currency_value = getattr(result, "currency", None)
        currency = ExtractedField(
            value=currency_value,
            method="python_extractor" if currency_value else None,
            confidence=1.0 if currency_value else 0.0,
        )

        return ExtractionResult(
            price=price,
            title=title,
            image=image,
            availability=availability,
            currency=currency,
            errors=list(getattr(result, "errors", []) or []),
            warnings=list(getattr(result, "warnings", []) or []),
        )

    def _empty_result(
        self,
        errors: Optional[list[str]] = None,
        warnings: Optional[list[str]] = None,
    ) -> ExtractionResult:
        """Return empty extraction result."""
        empty_field = ExtractedField(value=None, method=None, confidence=0.0)
        return ExtractionResult(
            price=empty_field,
            title=empty_field,
            image=empty_field,
            availability=empty_field,
            errors=errors or [],
            warnings=warnings or [],
        )
