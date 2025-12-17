"""
Auto-generated extractor for komplett.no

Converted from JSON pattern on 2025-12-17T16:02:31.859473
Original confidence: 0.92
"""
import re
from decimal import Decimal
from typing import Optional
from bs4 import BeautifulSoup
from ._base import BaseExtractor


# Metadata (required for discovery)
PATTERN_METADATA = {
    'domain': 'komplett.no',
    'generated_at': '2025-12-17T16:02:31.859494',
    'generator': 'JSON to Python converter',
    'version': '1.0',
    'confidence': 0.92,
    'fields': ['price', 'title', 'availability', 'image'],
    'notes': 'Converted from JSON pattern'
}


def extract_price(soup: BeautifulSoup) -> Optional[Decimal]:
    """
    Extract price.

    Primary: Primary price in data attribute
    Confidence: 0.95
    """
    # Primary selector
    elem = soup.select_one("#cash-price-container")
    if elem:
        value = elem.get("data-price")
        if value:
            return value
    if elem:
        return BaseExtractor.clean_price(elem.get_text(strip=True))

    # Fallback 1: Price from JSON in data-initobject attribute
    # Extract from JSON in data-initobject
    elem = soup.select_one(".buy-button")
    if elem and elem.get("data-initobject"):
        try:
            import json
            from html import unescape
            data_str = unescape(elem.get("data-initobject"))
            data = json.loads(data_str)
            value = BaseExtractor.extract_json_field(data, "price")
            if value:
                return str(value)
        except:
            pass

    # Fallback 2: Displayed price text
    elem = soup.select_one(".product-price-now")
    if elem:
        return BaseExtractor.clean_text(elem.get_text())
    if elem:
        return BaseExtractor.clean_price(elem.get_text(strip=True))

    return None


def extract_title(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract title.

    Primary: Open Graph title meta tag
    Confidence: 0.95
    """
    # Primary selector
    elem = soup.select_one("meta[property='og:title']")
    if elem:
        value = elem.get("content")
        if value:
            return value

    # Fallback 1: Product title heading
    elem = soup.select_one("h1.product-main-info__title")
    if elem:
        return BaseExtractor.clean_text(elem.get_text())

    # Fallback 2: Title from buy button JSON data
    # Extract from JSON in data-initobject
    elem = soup.select_one(".buy-button")
    if elem and elem.get("data-initobject"):
        try:
            import json
            from html import unescape
            data_str = unescape(elem.get("data-initobject"))
            data = json.loads(data_str)
            value = BaseExtractor.extract_json_field(data, "webtext1")
            if value:
                return str(value)
        except:
            pass

    return None


def extract_image(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract image.

    Primary: Secure product image from Open Graph
    Confidence: 0.95
    """
    # Primary selector
    elem = soup.select_one("meta[property='og:image:secure_url']")
    if elem:
        value = elem.get("content")
        if value:
            return value

    # Fallback 1: Product image from Open Graph (may include multiple)
    elem = soup.select_one("meta[property='og:image']")
    if elem:
        value = elem.get("content")
        if value:
            return value

    # Fallback 2: Main product image element
    elem = soup.select_one(".product-main-image img")
    if elem:
        value = elem.get("src")
        if value:
            return value

    return None


def extract_availability(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract availability.

    Primary: Stock status icon title attribute
    Confidence: 0.90
    """
    # Primary selector
    elem = soup.select_one(".stockstatus-instock")
    if elem:
        value = elem.get("title")
        if value:
            return value

    # Fallback 1: Stock status text
    elem = soup.select_one(".stockstatus-stock-details")
    if elem:
        return BaseExtractor.clean_text(elem.get_text())

    # Fallback 2: Stock status from JSON data (values: Stocked, OutOfStock)
    # Extract from JSON in data-initobject
    elem = soup.select_one(".buy-button")
    if elem and elem.get("data-initobject"):
        try:
            import json
            from html import unescape
            data_str = unescape(elem.get("data-initobject"))
            data = json.loads(data_str)
            value = BaseExtractor.extract_json_field(data, "item_stock_status")
            if value:
                return str(value)
        except:
            pass

    return None


def extract_article_number(soup: BeautifulSoup) -> Optional[str]:
    """Extract article_number (not available in source pattern)."""
    return None


def extract_model_number(soup: BeautifulSoup) -> Optional[str]:
    """Extract model_number (not available in source pattern)."""
    return None


