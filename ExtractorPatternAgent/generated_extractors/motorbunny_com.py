"""
Auto-generated extractor for motorbunny.com

Generated on 2025-12-22 for product extraction.
"""

import json
import re
from decimal import Decimal
from typing import Optional

from bs4 import BeautifulSoup

from ._base import BaseExtractor


PATTERN_METADATA = {
    "domain": "motorbunny.com",
    "generated_at": "2025-12-22T21:46:00",
    "generator": "generate-pattern",
    "version": "1.0",
    "confidence": 0.90,
    "fields": [
        "price",
        "title",
        "image",
        "availability",
        "article_number",
        "currency",
    ],
    "notes": "Shopify store with ShopifyAnalytics.meta JSON and Open Graph meta tags",
}


def _extract_shopify_meta_product(soup: BeautifulSoup) -> Optional[dict]:
    """Extract product data from ShopifyAnalytics.meta JavaScript variable."""
    scripts = soup.find_all("script")
    for script in scripts:
        if not script.string:
            continue
        if "ShopifyAnalytics.meta" in script.string and "var meta" in script.string:
            # Extract the JSON using regex
            match = re.search(r"var meta = ({.*?});", script.string, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(1))
                    product = data.get("product")
                    if isinstance(product, dict):
                        return product
                except (json.JSONDecodeError, TypeError, ValueError):
                    continue
    return None


def extract_price(soup: BeautifulSoup) -> Optional[Decimal]:
    """
    Extract price.

    Primary: ShopifyAnalytics.meta product.variants[0].price (in cents)
    Fallback: span.money[data-price]
    Confidence: 0.90
    """
    # Primary: ShopifyAnalytics.meta
    product = _extract_shopify_meta_product(soup)
    if product:
        variants = product.get("variants")
        if isinstance(variants, list) and variants:
            price_cents = variants[0].get("price")
            if price_cents is not None:
                try:
                    # Convert cents to dollars
                    price = Decimal(price_cents) / 100
                    if 0 < price < 1_000_000_000:
                        return price
                except (ValueError, ArithmeticError):
                    pass

    # Fallback: span.money with data-price attribute
    elem = soup.select_one("span.money[data-price]")
    if elem:
        price_text = elem.get_text(strip=True)
        if price_text:
            return BaseExtractor.clean_price(price_text)

    # Fallback 2: any span.money
    elem = soup.select_one("span.money")
    if elem:
        price_text = elem.get_text(strip=True)
        if price_text:
            return BaseExtractor.clean_price(price_text)

    return None


def extract_title(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract title.

    Primary: Open Graph og:title meta tag
    Fallback: h1.product-title
    Confidence: 0.95
    """
    # Primary: Open Graph meta tag
    elem = soup.select_one("meta[property='og:title']")
    if elem:
        title = elem.get("content")
        if title:
            return BaseExtractor.clean_text(title)

    # Fallback: h1 with product-title class
    elem = soup.select_one("h1.product-title")
    if elem:
        return BaseExtractor.clean_text(elem.get_text())

    # Fallback 2: any h1
    elem = soup.select_one("h1")
    if elem:
        return BaseExtractor.clean_text(elem.get_text())

    return None


def extract_image(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract image.

    Primary: Open Graph og:image:secure_url meta tag
    Fallback: og:image
    Confidence: 0.95
    """
    # Primary: Secure Open Graph image
    elem = soup.select_one("meta[property='og:image:secure_url']")
    if elem:
        image_url = elem.get("content")
        if image_url and image_url.startswith("http"):
            return image_url

    # Fallback: Regular Open Graph image
    elem = soup.select_one("meta[property='og:image']")
    if elem:
        image_url = elem.get("content")
        if image_url and image_url.startswith("http"):
            return image_url

    return None


def extract_availability(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract availability.

    Primary: Search for schema.org availability in page HTML
    Confidence: 0.85
    """
    # Look for schema.org availability in the page source
    html_text = str(soup)
    
    if "schema.org/InStock" in html_text:
        return "In Stock"
    
    if "schema.org/OutOfStock" in html_text or "schema.org/SoldOut" in html_text:
        return "Out of Stock"
    
    if "schema.org/PreOrder" in html_text:
        return "Preorder"

    return None


def extract_article_number(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract article_number (SKU).

    Primary: ShopifyAnalytics.meta product.variants[0].sku
    Confidence: 0.90
    """
    product = _extract_shopify_meta_product(soup)
    if product:
        variants = product.get("variants")
        if isinstance(variants, list) and variants:
            sku = variants[0].get("sku")
            if sku:
                return BaseExtractor.clean_text(str(sku))

    return None


def extract_model_number(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract model_number (MPN).

    Not available in motorbunny.com product pages.
    Confidence: N/A
    """
    return None


def extract_currency(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract currency code.

    Primary: ShopifyAnalytics.meta.currency
    Fallback: USD (default for motorbunny.com)
    
    Returns:
        Currency code (e.g., 'USD')
    
    Confidence: 0.95
    """
    # Try to extract from ShopifyAnalytics
    scripts = soup.find_all("script")
    for script in scripts:
        if not script.string:
            continue
        if "ShopifyAnalytics.meta.currency" in script.string:
            # Look for the currency assignment
            match = re.search(r"ShopifyAnalytics\.meta\.currency\s*=\s*['\"](\w+)['\"]", script.string)
            if match:
                return match.group(1)
    
    # Fallback: USD is the default currency for motorbunny.com
    return "USD"
