"""Base extractor interface for all generated extractors."""
from typing import Optional, Dict, Any, Protocol
from decimal import Decimal
from bs4 import BeautifulSoup
import re


class ExtractorProtocol(Protocol):
    """Protocol that all generated extractors must implement."""

    # Required metadata
    PATTERN_METADATA: Dict[str, Any]

    # Required extraction methods
    def extract_price(self, soup: BeautifulSoup) -> Optional[Decimal]:
        """Extract price from product page."""
        ...

    def extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract product title."""
        ...

    def extract_image(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract primary product image URL."""
        ...

    def extract_availability(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract stock availability status."""
        ...

    def extract_article_number(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract store article number (SKU)."""
        ...

    def extract_model_number(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract manufacturer model number."""
        ...


class BaseExtractor:
    """Base class for generated extractors (optional, for shared utilities)."""

    @staticmethod
    def clean_price(text: str) -> Optional[Decimal]:
        """
        Common price cleaning logic.

        Handles various price formats:
        - Norwegian: "1 990,-" or "1.990,50"
        - US: "1,990.50" or "$1990"
        - European: "1.990,50€"

        Args:
            text: Raw price text

        Returns:
            Decimal price or None if parsing fails
        """
        if not text:
            return None

        # Remove common currency symbols and whitespace
        text = str(text).strip()
        text = text.replace(' ', '').replace('kr', '').replace('$', '')
        text = text.replace('€', '').replace('£', '').replace(',-', '')

        # Handle different decimal separators
        # "1.990,50" -> "1990.50"
        # "1,990.50" -> "1990.50"
        if ',' in text and '.' in text:
            # Determine which is decimal separator
            comma_pos = text.rindex(',')
            dot_pos = text.rindex('.')
            if comma_pos > dot_pos:
                # European format: 1.990,50
                text = text.replace('.', '').replace(',', '.')
            else:
                # US format: 1,990.50
                text = text.replace(',', '')
        elif ',' in text:
            # Assume comma is decimal if only 2 digits after
            parts = text.split(',')
            if len(parts) == 2 and len(parts[1]) == 2:
                text = text.replace(',', '.')
            else:
                # Thousand separator
                text = text.replace(',', '')

        # Extract number
        match = re.search(r'\d+\.?\d*', text)
        if match:
            try:
                price = Decimal(match.group())
                # Sanity check
                if 0 < price < 1_000_000_000:
                    return price
            except (ValueError, ArithmeticError):
                return None

        return None

    @staticmethod
    def clean_text(text: Optional[str]) -> Optional[str]:
        """
        Common text cleaning.

        Args:
            text: Raw text

        Returns:
            Cleaned text or None
        """
        if not text:
            return None

        # Strip whitespace
        text = str(text).strip()

        # Remove excess whitespace
        text = re.sub(r'\s+', ' ', text)

        return text if text else None

    @staticmethod
    def extract_json_field(json_data: Dict, path: str) -> Optional[Any]:
        """
        Extract field from nested JSON using dot notation.

        Args:
            json_data: JSON dictionary
            path: Dot-separated path (e.g., "trackingData.item_manufacturer_number")

        Returns:
            Value at path or None

        Example:
            >>> data = {"tracking": {"item": {"price": 199}}}
            >>> extract_json_field(data, "tracking.item.price")
            199
        """
        if not json_data or not path:
            return None

        value = json_data
        for key in path.split('.'):
            if not key:  # Skip empty keys
                continue

            if isinstance(value, dict):
                value = value.get(key)
            elif isinstance(value, list) and key.isdigit():
                try:
                    value = value[int(key)]
                except (IndexError, ValueError):
                    return None
            else:
                return None

            if value is None:
                return None

        return value


class ExtractorResult:
    """Result from extraction attempt."""

    def __init__(self, domain: str):
        self.domain = domain
        self.price: Optional[Decimal] = None
        self.title: Optional[str] = None
        self.image: Optional[str] = None
        self.availability: Optional[str] = None
        self.article_number: Optional[str] = None
        self.model_number: Optional[str] = None
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary.

        Returns:
            Dict representation of result
        """
        return {
            'domain': self.domain,
            'price': str(self.price) if self.price else None,
            'title': self.title,
            'image': self.image,
            'availability': self.availability,
            'article_number': self.article_number,
            'model_number': self.model_number,
            'errors': self.errors,
            'warnings': self.warnings,
        }

    @property
    def success(self) -> bool:
        """
        Check if extraction was successful.

        Success criteria: price extracted and no errors.

        Returns:
            True if successful
        """
        return self.price is not None and len(self.errors) == 0

    def __repr__(self) -> str:
        """String representation."""
        status = "SUCCESS" if self.success else "FAILED"
        return f"<ExtractorResult {self.domain} {status} price={self.price}>"
