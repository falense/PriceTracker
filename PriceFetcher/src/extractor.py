"""Apply extraction patterns to HTML using Python extractors."""

import sys
from pathlib import Path
from typing import Optional
from decimal import Decimal

import structlog

from .models import ExtractionResult, ExtractedField

logger = structlog.get_logger(__name__).bind(service='fetcher')

# Add ExtractorPatternAgent to path for generated_extractors import
REPO_ROOT = Path(__file__).parent.parent.parent
EXTRACTOR_PATH = REPO_ROOT / 'ExtractorPatternAgent'
if str(EXTRACTOR_PATH) not in sys.path:
    sys.path.insert(0, str(EXTRACTOR_PATH))


class Extractor:
    """Apply Python extractors to HTML to extract product data."""

    def extract_with_domain(
        self, html: str, domain: str
    ) -> ExtractionResult:
        """
        Extract data using Python extractor module for domain.

        Args:
            html: Page HTML content
            domain: Store domain (e.g., "komplett.no")

        Returns:
            ExtractionResult with extracted fields
        """
        logger.debug("extraction_started", domain=domain)

        try:
            # Import generated_extractors API
            from generated_extractors import extract_from_html, has_parser

            # Normalize domain (remove www.)
            normalized_domain = domain.lower().replace('www.', '')

            # Check if extractor exists
            if not has_parser(normalized_domain):
                logger.error("no_extractor_found", domain=domain, normalized=normalized_domain)
                return self._empty_result()

            # Extract using Python module
            result_dict = extract_from_html(normalized_domain, html)

            if not result_dict:
                logger.warning("extraction_returned_empty", domain=domain)
                return self._empty_result()

            # Convert to ExtractionResult format
            extraction = self._convert_to_extraction_result(result_dict)

            logger.info(
                "extraction_completed",
                domain=domain,
                price_found=extraction.price.value is not None,
                method="python_extractor",
            )

            return extraction

        except ImportError as e:
            logger.error("extractor_import_failed", domain=domain, error=str(e))
            return self._empty_result()
        except Exception as e:
            logger.exception("extraction_failed", domain=domain, error=str(e))
            return self._empty_result()

    def _convert_to_extraction_result(self, result_dict: dict) -> ExtractionResult:
        """Convert extracted dict to ExtractionResult model."""

        # Convert each field
        price_value = result_dict.get('price')
        if price_value and isinstance(price_value, (Decimal, float, int, str)):
            try:
                price = ExtractedField(
                    value=str(price_value),
                    method="python_extractor",
                    confidence=1.0
                )
            except:
                price = ExtractedField(value=None, method=None, confidence=0.0)
        else:
            price = ExtractedField(value=None, method=None, confidence=0.0)

        title = ExtractedField(
            value=result_dict.get('title'),
            method="python_extractor" if result_dict.get('title') else None,
            confidence=1.0 if result_dict.get('title') else 0.0
        )

        image = ExtractedField(
            value=result_dict.get('image'),
            method="python_extractor" if result_dict.get('image') else None,
            confidence=1.0 if result_dict.get('image') else 0.0
        )

        availability = ExtractedField(
            value=result_dict.get('availability'),
            method="python_extractor" if result_dict.get('availability') else None,
            confidence=1.0 if result_dict.get('availability') else 0.0
        )

        article_number = ExtractedField(
            value=result_dict.get('article_number'),
            method="python_extractor" if result_dict.get('article_number') else None,
            confidence=1.0 if result_dict.get('article_number') else 0.0
        )

        model_number = ExtractedField(
            value=result_dict.get('model_number'),
            method="python_extractor" if result_dict.get('model_number') else None,
            confidence=1.0 if result_dict.get('model_number') else 0.0
        )

        return ExtractionResult(
            price=price,
            title=title,
            image=image,
            availability=availability,
            article_number=article_number,
            model_number=model_number
        )

    def _empty_result(self) -> ExtractionResult:
        """Return empty extraction result."""
        empty_field = ExtractedField(value=None, method=None, confidence=0.0)
        return ExtractionResult(
            price=empty_field,
            title=empty_field,
            image=empty_field,
            availability=empty_field,
            article_number=empty_field,
            model_number=empty_field
        )
