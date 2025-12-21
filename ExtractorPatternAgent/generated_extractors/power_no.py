"""
Auto-generated extractor for power.no

Generated on 2025-12-20 for product extraction.
"""

import json
from decimal import Decimal
from typing import Optional, Any

from bs4 import BeautifulSoup

from ._base import BaseExtractor


PATTERN_METADATA = {
    "domain": "power.no",
    "generated_at": "2025-12-20T22:30:00",
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
        "currency",
    ],
    "notes": "JSON-LD Product offers with meta fallbacks",
}


def _extract_product_json_ld(soup: BeautifulSoup) -> Optional[dict]:
    scripts = soup.select("script[type='application/ld+json']")
    for script in scripts:
        if not script.string:
            continue
        try:
            data = json.loads(script.string)
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
        product = _find_product_node(data)
        if product:
            return product
    return None


def _find_product_node(data: Any) -> Optional[dict]:
    if isinstance(data, dict):
        if data.get("@type") == "Product":
            return data
        graph = data.get("@graph")
        if isinstance(graph, list):
            for node in graph:
                product = _find_product_node(node)
                if product:
                    return product
        return None
    if isinstance(data, list):
        for node in data:
            product = _find_product_node(node)
            if product:
                return product
    return None


def _extract_offer(product: dict) -> Optional[dict]:
    offers = product.get("offers")
    if isinstance(offers, list):
        for offer in offers:
            if isinstance(offer, dict) and offer.get("price") is not None:
                return offer
        return offers[0] if offers else None
    if isinstance(offers, dict):
        return offers
    return None


def _normalize_availability(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    text = str(value).strip()
    if "InStock" in text:
        return "In Stock"
    if "OutOfStock" in text or "SoldOut" in text:
        return "Out of Stock"
    if "PreOrder" in text:
        return "Preorder"
    return BaseExtractor.clean_text(text)


def extract_price(soup: BeautifulSoup) -> Optional[Decimal]:
    """
    Extract price.

    Primary: JSON-LD offers price
    Confidence: 0.95
    """
    product = _extract_product_json_ld(soup)
    if product:
        offer = _extract_offer(product)
        if offer and offer.get("price") is not None:
            return BaseExtractor.clean_price(str(offer.get("price")))

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
        value = BaseExtractor.clean_text(name)
        if value:
            return value

    elem = soup.select_one("meta[property='og:title']")
    if elem:
        value = BaseExtractor.clean_text(elem.get("content"))
        if value:
            return value

    elem = soup.select_one("h1")
    if elem:
        return BaseExtractor.clean_text(elem.get_text())

    return None


def extract_image(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract image.

    Primary: JSON-LD product image
    Confidence: 0.95
    """
    product = _extract_product_json_ld(soup)
    if product:
        image = product.get("image")
        if isinstance(image, list) and image:
            image = image[0]
        if isinstance(image, str) and image.startswith("http"):
            return image

    elem = soup.select_one("meta[property='og:image']")
    if elem:
        value = elem.get("content")
        if value and value.startswith("http"):
            return value

    return None


def extract_availability(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract availability.

    Primary: JSON-LD offers availability
    Confidence: 0.95
    """
    product = _extract_product_json_ld(soup)
    if product:
        offer = _extract_offer(product)
        if offer:
            availability = offer.get("availability")
            value = _normalize_availability(availability)
            if value:
                return value

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
        value = BaseExtractor.clean_text(sku)
        if value:
            return value

    return None


def extract_model_number(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract model_number (MPN).

    Primary: JSON-LD mpn
    Confidence: 0.90
    """
    product = _extract_product_json_ld(soup)
    if product:
        mpn = product.get("mpn")
        value = BaseExtractor.clean_text(mpn)
        if value:
            return value

    return None

def extract_currency(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract currency code.
    
    Returns:
        Currency code (e.g., 'NOK', 'USD', 'EUR')
    
    Confidence: 1.0 (hardcoded default)
    """
    return "NOK"

