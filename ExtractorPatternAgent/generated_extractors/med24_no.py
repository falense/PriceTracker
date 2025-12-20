"""
Auto-generated extractor for med24.no

Converted from JSON-LD pattern on 2025-12-20T22:03:02+01:00
Original confidence: 0.95
"""

import json
import re
from decimal import Decimal
from typing import Optional, Any

from bs4 import BeautifulSoup

from ._base import BaseExtractor


# Metadata (required for discovery)
PATTERN_METADATA = {
    "domain": "med24.no",
    "generated_at": "2025-12-20T22:03:02+01:00",
    "generator": "JSON-LD pattern",
    "version": "1.1",
    "confidence": 0.95,
    "fields": [
        "price",
        "title",
        "availability",
        "image",
        "article_number",
        "model_number",
    ],
    "notes": "JSON-LD Product offers with Open Graph fallbacks",
}


def _find_product_json_ld(soup: BeautifulSoup) -> Optional[dict[str, Any]]:
    scripts = soup.select("script[type='application/ld+json']")
    for script in scripts:
        if not script.string:
            continue
        try:
            data = json.loads(script.string)
        except json.JSONDecodeError:
            continue

        items = data if isinstance(data, list) else [data]
        for item in items:
            if isinstance(item, dict) and item.get("@type") == "Product":
                return item
    return None


def _extract_offer_value(product: dict[str, Any], field: str) -> Optional[str]:
    offers = product.get("offers") if product else None
    if isinstance(offers, dict):
        value = offers.get(field)
        return str(value) if value is not None else None
    if isinstance(offers, list) and offers:
        value = offers[0].get(field) if isinstance(offers[0], dict) else None
        return str(value) if value is not None else None
    return None


def extract_price(soup: BeautifulSoup) -> Optional[Decimal]:
    """
    Extract price.

    Primary: JSON-LD Product offers.price
    Confidence: 0.95
    """
    product = _find_product_json_ld(soup)
    if product:
        value = _extract_offer_value(product, "price")
        if value:
            return BaseExtractor.clean_price(value)

    elem = soup.select_one("meta[property='og:price:amount']")
    if elem:
        value = elem.get("content")
        if value:
            return BaseExtractor.clean_price(value)

    return None


def extract_title(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract title.

    Primary: JSON-LD Product name
    Confidence: 0.95
    """
    product = _find_product_json_ld(soup)
    if product:
        value = product.get("name")
        if value:
            return BaseExtractor.clean_text(str(value))

    elem = soup.select_one("meta[property='og:title']")
    if elem:
        value = elem.get("content")
        if value:
            return BaseExtractor.clean_text(value)

    elem = soup.select_one("h1")
    if elem:
        return BaseExtractor.clean_text(elem.get_text())

    return None


def extract_image(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract image.

    Primary: JSON-LD Product image
    Confidence: 0.95
    """
    product = _find_product_json_ld(soup)
    if product:
        value = product.get("image")
        if isinstance(value, list) and value:
            value = value[0]
        if value:
            value = str(value).strip()
            if value.startswith("http"):
                return value

    elem = soup.select_one("meta[property='og:image']")
    if elem:
        value = elem.get("content")
        if value:
            value = str(value).strip()
            if value.startswith("http"):
                return value

    return None


def extract_availability(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract availability.

    Primary: JSON-LD Product offers.availability
    Confidence: 0.95
    """
    product = _find_product_json_ld(soup)
    if product:
        value = _extract_offer_value(product, "availability")
        if value:
            value = BaseExtractor.clean_text(value)
            if value:
                if value.endswith("/InStock"):
                    return "In Stock"
                if value.endswith("/OutOfStock"):
                    return "Out of Stock"
                return value

    elem = soup.select_one("[data-availability]")
    if elem:
        value = elem.get("data-availability")
        if value:
            return BaseExtractor.clean_text(value)

    return None


def extract_article_number(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract article_number (product ID/SKU).

    Primary: JSON-LD Product sku
    Confidence: 0.90
    """
    product = _find_product_json_ld(soup)
    if product:
        value = product.get("sku")
        if value is not None:
            return str(value).strip()

    body = soup.select_one("body[data-internal-path]")
    if body:
        value = body.get("data-internal-path")
        if value:
            match = re.search(r"product/(\d+)", value)
            if match:
                return match.group(1)

    return None


def extract_model_number(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract model_number (manufacturer part number).

    Primary: JSON-LD Product mpn
    Confidence: 0.90
    """
    product = _find_product_json_ld(soup)
    if product:
        value = product.get("mpn")
        if value is not None:
            return str(value).strip()

    return None
