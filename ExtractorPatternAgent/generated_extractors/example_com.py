"""
Auto-generated extractor for www.example.com

Converted from JSON pattern on 2025-12-17T15:55:12.744092
Original confidence: 0.00
"""
import re
from decimal import Decimal
from typing import Optional
from bs4 import BeautifulSoup
from ._base import BaseExtractor


# Metadata (required for discovery)
PATTERN_METADATA = {
    'domain': 'example.com',
    'generated_at': '2025-12-17T15:55:12.744096',
    'generator': 'JSON to Python converter',
    'version': '1.0',
    'confidence': 0.00,
    'fields': ['title'],
    'notes': 'Converted from JSON pattern'
}


def extract_price(soup: BeautifulSoup) -> Optional[Decimal]:
    """Extract price (not available in source pattern)."""
    return None


def extract_title(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract title.

    Primary: h1
    Confidence: 0.85
    """
    # Primary selector
    elem = soup.select_one('h1')
    if elem:
        return BaseExtractor.clean_text(elem.get_text())

    return None


def extract_image(soup: BeautifulSoup) -> Optional[str]:
    """Extract image (not available in source pattern)."""
    return None


def extract_availability(soup: BeautifulSoup) -> Optional[str]:
    """Extract availability (not available in source pattern)."""
    return None


def extract_article_number(soup: BeautifulSoup) -> Optional[str]:
    """Extract article_number (not available in source pattern)."""
    return None


def extract_model_number(soup: BeautifulSoup) -> Optional[str]:
    """Extract model_number (not available in source pattern)."""
    return None


