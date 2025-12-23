"""
Auto-generated extractor for www.dreammask.net

Generated on 2025-12-22 for product extraction.
Wix-based e-commerce site with JSON-LD structured data.
"""

import json
from decimal import Decimal
from typing import Optional, Any

from bs4 import BeautifulSoup

from ._base import BaseExtractor


PATTERN_METADATA = {
    "domain": "dreammask.net",
    "generated_at": "2025-12-22T23:00:00",
    "generator": "pattern-generator",
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
    "notes": "Wix-based store with JSON-LD Product schema and Open Graph meta tags",
}


def _extract_product_json_ld(soup: BeautifulSoup) -> Optional[dict]:
    """Extract Product structured data from JSON-LD."""
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
    """Recursively find Product node in JSON-LD data."""
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
    """Extract Offer/Offers from Product schema."""
    # Try "Offers" (capitalized) first - this is what dreammask.net uses
    offers = product.get("Offers")
    if not offers:
        # Fallback to lowercase "offers"
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
    """Normalize availability string to common format."""
    if not value:
        return None
    text = str(value).strip()
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
    if "InStoreOnly" in text:
        return "In Store Only"
    if "PreSale" in text:
        return "Pre-Sale"
    if "Discontinued" in text:
        return "Discontinued"
    return BaseExtractor.clean_text(text)


def extract_price(soup: BeautifulSoup) -> Optional[Decimal]:
    """
    Extract price.

    Primary: JSON-LD Offers price
    Fallback: Open Graph product:price:amount meta tag
    Confidence: 0.95
    """
    # Primary: JSON-LD
    product = _extract_product_json_ld(soup)
    if product:
        offer = _extract_offer(product)
        if offer and offer.get("price") is not None:
            return BaseExtractor.clean_price(str(offer.get("price")))

    # Fallback: Open Graph meta tag
    elem = soup.select_one("meta[property='product:price:amount']")
    if elem:
        content = elem.get("content")
        if content:
            return BaseExtractor.clean_price(str(content))

    return None


def extract_title(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract title.

    Primary: JSON-LD product name
    Fallback 1: Open Graph og:title meta tag
    Fallback 2: h1 tag
    Confidence: 0.95
    """
    # Primary: JSON-LD
    product = _extract_product_json_ld(soup)
    if product:
        name = product.get("name")
        value = BaseExtractor.clean_text(name)
        if value:
            return value

    # Fallback 1: Open Graph
    elem = soup.select_one("meta[property='og:title']")
    if elem:
        content = elem.get("content")
        value = BaseExtractor.clean_text(content)
        if value:
            # Remove site name suffix if present (e.g., " | DreammaskStudio")
            if " | " in value:
                value = value.split(" | ")[0].strip()
            return value

    # Fallback 2: h1
    elem = soup.select_one("h1")
    if elem:
        return BaseExtractor.clean_text(elem.get_text())

    return None


def extract_image(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract image.

    Primary: JSON-LD product image (first image)
    Fallback: Open Graph og:image meta tag
    Confidence: 0.95
    """
    # Primary: JSON-LD
    product = _extract_product_json_ld(soup)
    if product:
        image = product.get("image")
        # Handle list of images (take first one)
        if isinstance(image, list) and image:
            # Each image is an ImageObject with contentUrl
            first_image = image[0]
            if isinstance(first_image, dict):
                url = first_image.get("contentUrl")
                if url and isinstance(url, str) and url.startswith("http"):
                    return url
            elif isinstance(first_image, str) and first_image.startswith("http"):
                return first_image
        # Handle single image string
        elif isinstance(image, str) and image.startswith("http"):
            return image
        # Handle single ImageObject
        elif isinstance(image, dict):
            url = image.get("contentUrl") or image.get("url")
            if url and isinstance(url, str) and url.startswith("http"):
                return url

    # Fallback: Open Graph
    elem = soup.select_one("meta[property='og:image']")
    if elem:
        value = elem.get("content")
        if value and value.startswith("http"):
            return value

    return None


def extract_availability(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract availability.

    Primary: JSON-LD Offers availability
    Fallback: Open Graph og:availability meta tag
    Confidence: 0.95
    """
    # Primary: JSON-LD
    product = _extract_product_json_ld(soup)
    if product:
        offer = _extract_offer(product)
        if offer:
            # Try "Availability" (capitalized) first
            availability = offer.get("Availability")
            if not availability:
                # Fallback to lowercase
                availability = offer.get("availability")
            value = _normalize_availability(availability)
            if value:
                return value

    # Fallback: Open Graph meta tag
    elem = soup.select_one("meta[property='og:availability']")
    if elem:
        content = elem.get("content")
        value = _normalize_availability(content)
        if value:
            return value

    return None


def extract_article_number(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract article_number (SKU).

    Primary: JSON-LD sku
    Confidence: 0.90
    """
    # Primary: JSON-LD
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
    Confidence: 0.85
    """
    # Primary: JSON-LD
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

    Primary: JSON-LD Offers priceCurrency
    Fallback: Open Graph product:price:currency meta tag
    
    Returns:
        Currency code (e.g., 'USD', 'EUR', 'NOK')
    
    Confidence: 0.95
    """
    # Primary: JSON-LD
    product = _extract_product_json_ld(soup)
    if product:
        offer = _extract_offer(product)
        if offer:
            currency = offer.get("priceCurrency")
            if currency:
                return str(currency).upper()

    # Fallback: Open Graph meta tag
    elem = soup.select_one("meta[property='product:price:currency']")
    if elem:
        content = elem.get("content")
        if content:
            return str(content).upper()

    # Default fallback
    return "USD"
