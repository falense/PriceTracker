"""
Auto-generated extractor for www.uniqso.com

Generated on 2025-12-26 for product extraction.
Utilizes JSON-LD ProductGroup structured data with multiple product variants.
"""

import json
from decimal import Decimal
from typing import Optional, Any

from bs4 import BeautifulSoup

from ._base import BaseExtractor


PATTERN_METADATA = {
    "domain": "uniqso.com",
    "generated_at": "2025-12-26T12:48:00",
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
    "notes": "JSON-LD ProductGroup with Product variants, meta tag fallbacks",
}


def _extract_product_group_json_ld(soup: BeautifulSoup) -> Optional[dict]:
    """Extract ProductGroup JSON-LD structured data."""
    scripts = soup.select("script[type='application/ld+json']")
    for script in scripts:
        if not script.string:
            continue
        try:
            data = json.loads(script.string)
            if isinstance(data, dict) and data.get("@type") == "ProductGroup":
                return data
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
    return None


def _get_first_available_variant(product_group: dict) -> Optional[dict]:
    """
    Get the first available product variant from ProductGroup.
    
    Returns first variant with InStock availability, or first variant if none in stock.
    """
    if not product_group:
        return None
    
    variants = product_group.get("hasVariant")
    if not isinstance(variants, list) or not variants:
        return None
    
    # Try to find first in-stock variant
    for variant in variants:
        if isinstance(variant, dict) and variant.get("@type") == "Product":
            offers = variant.get("offers")
            if isinstance(offers, dict):
                availability = offers.get("availability", "")
                if "InStock" in availability:
                    return variant
    
    # Fallback to first variant
    for variant in variants:
        if isinstance(variant, dict) and variant.get("@type") == "Product":
            return variant
    
    return None


def _normalize_availability(value: Optional[str]) -> Optional[str]:
    """Normalize availability status to standard values."""
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

    Primary: JSON-LD ProductGroup first available variant price
    Fallback 1: og:price:amount meta tag
    Fallback 2: .money element in price block
    Confidence: 0.95
    """
    # Primary: JSON-LD ProductGroup variant price
    product_group = _extract_product_group_json_ld(soup)
    if product_group:
        variant = _get_first_available_variant(product_group)
        if variant:
            offers = variant.get("offers")
            if isinstance(offers, dict):
                price = offers.get("price")
                if price is not None:
                    return BaseExtractor.clean_price(str(price))
    
    # Fallback 1: Open Graph price meta tag
    price_meta = soup.select_one("meta[property='og:price:amount']")
    if price_meta:
        content = price_meta.get("content")
        if content:
            return BaseExtractor.clean_price(content)
    
    # Fallback 2: .money element in price block
    price_current = soup.select_one(".price__current .money")
    if price_current:
        return BaseExtractor.clean_price(price_current.get_text())
    
    return None


def extract_title(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract title.

    Primary: JSON-LD ProductGroup name
    Fallback 1: og:title meta tag
    Fallback 2: h1 element
    Confidence: 0.95
    """
    # Primary: JSON-LD ProductGroup name
    product_group = _extract_product_group_json_ld(soup)
    if product_group:
        name = product_group.get("name")
        if name:
            return BaseExtractor.clean_text(name)
    
    # Fallback 1: Open Graph title
    title_meta = soup.select_one("meta[property='og:title']")
    if title_meta:
        content = title_meta.get("content")
        if content:
            return BaseExtractor.clean_text(content)
    
    # Fallback 2: h1 element
    h1 = soup.select_one("h1")
    if h1:
        return BaseExtractor.clean_text(h1.get_text())
    
    return None


def extract_image(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract image.

    Primary: JSON-LD ProductGroup first variant image
    Fallback 1: og:image:secure_url meta tag
    Fallback 2: og:image meta tag
    Confidence: 0.95
    """
    # Primary: JSON-LD ProductGroup variant image
    product_group = _extract_product_group_json_ld(soup)
    if product_group:
        variant = _get_first_available_variant(product_group)
        if variant:
            image = variant.get("image")
            if isinstance(image, str) and image.startswith("http"):
                return image
    
    # Fallback 1: Secure Open Graph image
    og_image_secure = soup.select_one("meta[property='og:image:secure_url']")
    if og_image_secure:
        content = og_image_secure.get("content")
        if content and content.startswith("http"):
            return content
    
    # Fallback 2: Open Graph image
    og_image = soup.select_one("meta[property='og:image']")
    if og_image:
        content = og_image.get("content")
        if content and content.startswith("http"):
            return content
    
    return None


def extract_availability(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract availability.

    Primary: JSON-LD ProductGroup first available variant availability
    Fallback 1: Variant selector text (check for "Sold out")
    Fallback 2: Add to cart button state
    Confidence: 0.90
    """
    # Primary: JSON-LD ProductGroup variant availability
    product_group = _extract_product_group_json_ld(soup)
    if product_group:
        variant = _get_first_available_variant(product_group)
        if variant:
            offers = variant.get("offers")
            if isinstance(offers, dict):
                availability = offers.get("availability")
                normalized = _normalize_availability(availability)
                if normalized:
                    return normalized
    
    # Fallback 1: Check variant selector for sold out indication
    variant_select = soup.select_one('select[name="id"]')
    if variant_select:
        # Check first option
        first_option = variant_select.select_one('option')
        if first_option:
            option_text = first_option.get_text().strip()
            if "Sold out" in option_text:
                # Check if any options are available
                all_options = variant_select.select('option')
                for option in all_options:
                    if "Sold out" not in option.get_text():
                        return "In Stock"
                return "Out of Stock"
            else:
                return "In Stock"
    
    # Fallback 2: Check add to cart button
    add_button = soup.select_one('button[name="add"]')
    if add_button:
        is_disabled = add_button.has_attr('disabled')
        if is_disabled:
            return "Out of Stock"
        else:
            return "In Stock"
    
    return None


def extract_article_number(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract article_number (SKU).

    Primary: JSON-LD ProductGroup first available variant SKU
    Confidence: 0.95
    """
    product_group = _extract_product_group_json_ld(soup)
    if product_group:
        variant = _get_first_available_variant(product_group)
        if variant:
            sku = variant.get("sku")
            if sku:
                return BaseExtractor.clean_text(sku)
    
    return None


def extract_model_number(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract model_number.
    
    Note: Model number not typically available for this site.
    Brand is available in JSON-LD but that's not the model number.
    Confidence: 0.00
    """
    return None


def extract_currency(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract currency code.

    Primary: JSON-LD ProductGroup first variant priceCurrency
    Fallback: og:price:currency meta tag
    
    Returns:
        Currency code (e.g., 'USD', 'EUR')
    
    Confidence: 0.95
    """
    # Primary: JSON-LD priceCurrency
    product_group = _extract_product_group_json_ld(soup)
    if product_group:
        variant = _get_first_available_variant(product_group)
        if variant:
            offers = variant.get("offers")
            if isinstance(offers, dict):
                currency = offers.get("priceCurrency")
                if currency:
                    return BaseExtractor.clean_text(currency)
    
    # Fallback: Open Graph price currency
    currency_meta = soup.select_one("meta[property='og:price:currency']")
    if currency_meta:
        content = currency_meta.get("content")
        if content:
            return BaseExtractor.clean_text(content)
    
    # Default fallback
    return "USD"
