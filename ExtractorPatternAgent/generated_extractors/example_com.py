"""
Example extractor for documentation and testing purposes.

This is a reference implementation showing the structure
all generated extractors should follow.

Generated: Manual (example)
"""
import re
from decimal import Decimal
from typing import Optional
from bs4 import BeautifulSoup
from ._base import BaseExtractor


# Metadata (required for discovery)
PATTERN_METADATA = {
    'domain': 'example.com',
    'generated_at': '2025-12-17T00:00:00Z',
    'generator': 'Manual (example)',
    'version': '1.0',
    'confidence': 1.0,
    'fields': ['price', 'title', 'image', 'availability', 'article_number', 'model_number'],
    'notes': 'Example extractor for testing and documentation'
}


def extract_price(soup: BeautifulSoup) -> Optional[Decimal]:
    """
    Extract current price from product page.

    Primary selector: .product-price
    Fallback: [data-price]
    Confidence: 1.0
    """
    # Try primary selector
    elem = soup.select_one('.product-price')
    if elem:
        return BaseExtractor.clean_price(elem.get_text(strip=True))

    # Try data-price attribute
    elem = soup.select_one('[data-price]')
    if elem:
        price_text = elem.get('data-price')
        return BaseExtractor.clean_price(price_text)

    return None


def extract_title(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract product title.

    Primary: h1.product-title
    Fallback: og:title meta tag
    Confidence: 1.0
    """
    # Try h1 first
    h1 = soup.select_one('h1.product-title')
    if h1:
        return BaseExtractor.clean_text(h1.get_text())

    # Fallback to Open Graph
    og_title = soup.select_one('meta[property="og:title"]')
    if og_title:
        return BaseExtractor.clean_text(og_title.get('content'))

    return None


def extract_image(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract primary product image URL.

    Primary: .product-image img[src]
    Fallback: og:image meta tag
    Confidence: 1.0
    """
    # Try product image
    img = soup.select_one('.product-image img')
    if img:
        src = img.get('src')
        if src:
            return src

    # Fallback to Open Graph
    og_image = soup.select_one('meta[property="og:image"]')
    if og_image:
        return og_image.get('content')

    return None


def extract_availability(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract stock availability status.

    Primary: .stock-status
    Confidence: 1.0
    """
    elem = soup.select_one('.stock-status')
    if elem:
        return BaseExtractor.clean_text(elem.get_text())

    return None


def extract_article_number(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract store article number (SKU).

    Primary: [itemprop="sku"]
    Confidence: 1.0
    """
    sku_elem = soup.select_one('[itemprop="sku"]')
    if sku_elem:
        return BaseExtractor.clean_text(sku_elem.get_text())

    return None


def extract_model_number(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract manufacturer model number.

    Primary: .model-number
    Confidence: 1.0
    """
    elem = soup.select_one('.model-number')
    if elem:
        return BaseExtractor.clean_text(elem.get_text())

    return None
