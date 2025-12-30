"""
Auto-generated extractor for www.hair247.no

Generated on 2025-12-27 for product extraction.
Uses microdata (itemprop) attributes and Open Graph meta tags.
"""

from decimal import Decimal
from typing import Optional

from bs4 import BeautifulSoup

from ._base import BaseExtractor


PATTERN_METADATA = {
    "domain": "hair247.no",
    "generated_at": "2025-12-27T17:34:00",
    "generator": "generate-pattern",
    "version": "1.0",
    "confidence": 0.95,
    "fields": [
        "price",
        "title",
        "image",
        "availability",
        "article_number",
        "currency",
    ],
    "notes": "Microdata with itemprop attributes and Open Graph fallbacks",
}


def extract_price(soup: BeautifulSoup) -> Optional[Decimal]:
    """
    Extract price.

    Primary: itemprop="price" with content or data-unitprice attribute
    Confidence: 0.95
    """
    
    # Primary selector: itemprop="price" with content attribute
    elem = soup.select_one('[itemprop="price"][content]')
    if elem:
        value = elem.get("content")
        if value:
            return BaseExtractor.clean_price(value)

    # Fallback 1: itemprop="price" with data-unitprice
    elem = soup.select_one('[itemprop="price"][data-unitprice]')
    if elem:
        value = elem.get("data-unitprice")
        if value:
            return BaseExtractor.clean_price(value)

    # Fallback 2: itemprop="price" text content
    elem = soup.select_one('[itemprop="price"]')
    if elem:
        return BaseExtractor.clean_price(elem.get_text(strip=True))

    return None


def extract_title(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract title.

    Primary: Open Graph title meta tag
    Confidence: 0.95
    """
    # Primary selector: og:title
    elem = soup.select_one("meta[property='og:title']")
    if elem:
        value = elem.get("content")
        if value:
            return BaseExtractor.clean_text(value)

    # Fallback 1: itemprop="name"
    elem = soup.select_one('[itemprop="name"]')
    if elem:
        return BaseExtractor.clean_text(elem.get_text())

    # Fallback 2: h1
    elem = soup.select_one("h1")
    if elem:
        return BaseExtractor.clean_text(elem.get_text())

    return None


def extract_image(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract image.

    Primary: Open Graph image meta tag
    Confidence: 0.95
    """
    # Primary selector: og:image
    elem = soup.select_one("meta[property='og:image']")
    if elem:
        value = elem.get("content")
        if value and str(value).startswith("http"):
            return str(value).strip()

    # Fallback: itemprop="image"
    elem = soup.select_one('[itemprop="image"]')
    if elem:
        value = elem.get("content") or elem.get("src")
        if value and str(value).startswith("http"):
            return str(value).strip()

    return None


def extract_availability(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract availability.

    Primary: itemprop="availability" href attribute with schema.org value
    Confidence: 0.90
    """
    # Primary selector: itemprop="availability" link
    elem = soup.select_one('[itemprop="availability"]')
    if elem:
        href = elem.get("href")
        if href:
            # Parse schema.org availability values
            if "InStock" in str(href):
                return "In Stock"
            elif "OutOfStock" in str(href):
                return "Out of Stock"
            elif "PreOrder" in str(href):
                return "Preorder"

    # Fallback 1: .stockInfo text
    elem = soup.select_one(".stockInfo .Description_Productinfo")
    if elem:
        text = BaseExtractor.clean_text(elem.get_text())
        if text:
            # Normalize Norwegian availability text
            text_lower = text.lower()
            if "på lager" in text_lower or "lager" in text_lower:
                return "In Stock"
            elif "ikke på lager" in text_lower or "utsolgt" in text_lower:
                return "Out of Stock"
            return text

    # Fallback 2: Any element with availability text
    elem = soup.select_one(".stockInfo")
    if elem:
        text = BaseExtractor.clean_text(elem.get_text())
        if text and "lager" in text.lower():
            return "In Stock"

    return None


def extract_article_number(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract article_number (SKU).

    Primary: itemprop="sku" content attribute
    Confidence: 0.95
    """
    # Primary selector: itemprop="sku"
    elem = soup.select_one('[itemprop="sku"]')
    if elem:
        value = elem.get("content")
        if value:
            return BaseExtractor.clean_text(value)

    # Fallback: hidden input with ProductID
    elem = soup.select_one('input[name="ProductID"]')
    if elem:
        value = elem.get("value")
        if value:
            return BaseExtractor.clean_text(value)

    return None


def extract_model_number(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract model_number (manufacturer part number).

    Note: Model number not found in sample HTML.
    Confidence: 0.0
    """
    return None


def extract_currency(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract currency code.

    Primary: itemprop="priceCurrency" content attribute
    Confidence: 0.95
    """
    # Primary selector: itemprop="priceCurrency"
    elem = soup.select_one('[itemprop="priceCurrency"]')
    if elem:
        value = elem.get("content")
        if value:
            return BaseExtractor.clean_text(value)

    # Fallback: hardcoded NOK for Norwegian site
    return "NOK"
