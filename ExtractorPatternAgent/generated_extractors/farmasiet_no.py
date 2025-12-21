"""
Auto-generated extractor for farmasiet.no

Generated on 2025-12-21 for product extraction.
Uses JSON-LD structured data as primary source.
"""

import json
from decimal import Decimal
from typing import Optional, Any

from bs4 import BeautifulSoup

from ._base import BaseExtractor


PATTERN_METADATA = {
    "domain": "farmasiet.no",
    "generated_at": "2025-12-21T22:42:00",
    "generator": "generate-pattern",
    "version": "1.0",
    "confidence": 0.95,
    "fields": [
        "price",
        "title",
        "image",
        "availability",
        "article_number",
        "model_number",
    ],
    "notes": "JSON-LD Product schema with meta tag fallbacks. High confidence due to structured data.",
}


def _extract_product_json_ld(soup: BeautifulSoup) -> Optional[dict]:
    """Extract Product JSON-LD structured data from the page."""
    script = soup.select_one("script[type='application/ld+json']")
    if not script or not script.string:
        return None
    
    try:
        data = json.loads(script.string)
        # Check if this is a Product type
        if isinstance(data, dict) and data.get("@type") == "Product":
            return data
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    
    return None


def _normalize_availability(value: Optional[str]) -> Optional[str]:
    """Normalize availability status to standard format."""
    if not value:
        return None
    
    text = str(value).strip()
    
    # Schema.org availability values
    if "InStock" in text:
        return "In Stock"
    if "OutOfStock" in text or "SoldOut" in text:
        return "Out of Stock"
    if "PreOrder" in text:
        return "Preorder"
    if "LimitedAvailability" in text:
        return "Limited Stock"
    if "OnlineOnly" in text:
        return "Online Only"
    
    return BaseExtractor.clean_text(text)


def extract_price(soup: BeautifulSoup) -> Optional[Decimal]:
    """
    Extract price.

    Primary: JSON-LD offers.price
    Confidence: 0.95
    """
    product = _extract_product_json_ld(soup)
    if product:
        offers = product.get("offers")
        if isinstance(offers, dict):
            price = offers.get("price")
            if price is not None:
                return BaseExtractor.clean_price(str(price))
    
    # Fallback: Open Graph price meta tag
    elem = soup.select_one("meta[property='og:price:amount']")
    if elem:
        value = elem.get("content")
        if value:
            return BaseExtractor.clean_price(value)
    
    return None


def extract_title(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract title.

    Primary: JSON-LD product name
    Confidence: 0.95
    """
    product = _extract_product_json_ld(soup)
    if product:
        name = product.get("name")
        if name:
            return BaseExtractor.clean_text(name)
    
    # Fallback 1: Open Graph title meta tag
    elem = soup.select_one("meta[property='og:title']")
    if elem:
        value = elem.get("content")
        if value:
            value = BaseExtractor.clean_text(value)
            # Remove site suffix if present (e.g., " - Tannkrem - Farmasiet.no")
            if value and ' - ' in value:
                # Keep only the first part
                value = value.split(' - ')[0].strip()
            return value
    
    # Fallback 2: h1 heading
    elem = soup.select_one("h1")
    if elem:
        return BaseExtractor.clean_text(elem.get_text())
    
    return None


def extract_image(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract image.

    Primary: JSON-LD product image (first in array)
    Confidence: 0.95
    """
    product = _extract_product_json_ld(soup)
    if product:
        image = product.get("image")
        # Handle both list and string formats
        if isinstance(image, list) and image:
            image_url = image[0]
            if isinstance(image_url, str) and image_url.startswith("http"):
                return image_url
        elif isinstance(image, str) and image.startswith("http"):
            return image
    
    # Fallback: Open Graph image meta tag
    elem = soup.select_one("meta[property='og:image']")
    if elem:
        value = elem.get("content")
        if value and value.startswith("http"):
            return value
    
    return None


def extract_availability(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract availability.

    Primary: JSON-LD offers.availability
    Confidence: 0.95
    """
    product = _extract_product_json_ld(soup)
    if product:
        offers = product.get("offers")
        if isinstance(offers, dict):
            availability = offers.get("availability")
            if availability:
                return _normalize_availability(availability)
    
    return None


def extract_article_number(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract article_number (SKU).

    Primary: JSON-LD sku
    Confidence: 0.95
    """
    product = _extract_product_json_ld(soup)
    if product:
        sku = product.get("sku")
        if sku:
            return BaseExtractor.clean_text(str(sku))
        
        # Also try identifier field as fallback
        identifier = product.get("identifier")
        if identifier:
            return BaseExtractor.clean_text(str(identifier))
    
    return None


def extract_model_number(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract model_number (GTIN/barcode).

    Primary: JSON-LD gtin14 (or other gtin fields)
    Confidence: 0.90
    """
    product = _extract_product_json_ld(soup)
    if product:
        # Try various GTIN fields
        for field in ["gtin14", "gtin13", "gtin12", "gtin8", "gtin", "mpn"]:
            value = product.get(field)
            if value:
                return BaseExtractor.clean_text(str(value))
    
    return None
