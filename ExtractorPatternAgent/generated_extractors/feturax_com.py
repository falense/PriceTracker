"""
Auto-generated extractor for feturax.com

Created on 2025-12-20T23:09:05Z
WooCommerce site with Woodmart theme, variable products
"""

import re
from decimal import Decimal
from typing import Optional
from bs4 import BeautifulSoup
from ._base import BaseExtractor


# Metadata (required for discovery)
PATTERN_METADATA = {
    "domain": "feturax.com",
    "generated_at": "2025-12-21T00:14:00",
    "generator": "manual",
    "version": "1.0",
    "confidence": 0.90,
    "fields": [
        "price",
        "title",
        "image",
        "availability",
        "article_number",
        "model_number",
        "currency",
    ],
    "notes": "WooCommerce site with Woodmart theme, variable products with price ranges",
}


def extract_price(soup: BeautifulSoup) -> Optional[Decimal]:
    """
    Extract price from WooCommerce price elements.

    Primary: span.woocs_price_code (handles variable products with price ranges)
    Fallback 1: p.price ins .woocommerce-Price-amount
    Fallback 2: p.price .woocommerce-Price-amount
    Fallback 3: meta[property="product:price:amount"]

    Confidence: 0.90

    Note: For variable products with price ranges, extracts the minimum price.
    """
    # Primary: WOOCS price code (handles currency switcher)
    # For variable products with price ranges, get the first woocommerce-Price-amount (minimum price)
    elem = soup.select_one("span.woocs_price_code .woocommerce-Price-amount bdi")
    if elem:
        price = BaseExtractor.clean_price(elem.get_text())
        if price:
            return price

    # Fallback 1: WooCommerce sale price (ins tag indicates sale)
    elem = soup.select_one("p.price ins .woocommerce-Price-amount")
    if elem:
        price = BaseExtractor.clean_price(elem.get_text())
        if price:
            return price

    # Fallback 2: Regular WooCommerce price
    elem = soup.select_one("p.price .woocommerce-Price-amount")
    if elem:
        price = BaseExtractor.clean_price(elem.get_text())
        if price:
            return price

    # Fallback 3: OpenGraph meta tag
    meta = soup.select_one('meta[property="product:price:amount"]')
    if meta and meta.get("content"):
        try:
            return Decimal(meta["content"])
        except:
            pass

    return None


def extract_title(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract product title.

    Primary: h1.product_title.entry-title
    Fallback 1: h1.product_title
    Fallback 2: meta[property="og:title"]

    Confidence: 0.95
    """
    # Primary: WooCommerce product title
    elem = soup.select_one("h1.product_title.entry-title")
    if elem:
        return BaseExtractor.clean_text(elem.get_text())

    # Fallback 1: Any product_title h1
    elem = soup.select_one("h1.product_title")
    if elem:
        return BaseExtractor.clean_text(elem.get_text())

    # Fallback 2: OpenGraph title
    meta = soup.select_one('meta[property="og:title"]')
    if meta and meta.get("content"):
        return BaseExtractor.clean_text(meta["content"])

    return None


def extract_image(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract product image URL.

    Primary: div.woocommerce-product-gallery__image img (first gallery image)
    Fallback 1: img.wp-post-image
    Fallback 2: meta[property="og:image"]

    Confidence: 0.92
    """
    # Primary: First image in WooCommerce gallery
    elem = soup.select_one("div.woocommerce-product-gallery__image img")
    if elem:
        # Try data-large_image first (full resolution), then data-src, then src
        url = elem.get("data-large_image") or elem.get("data-src") or elem.get("src")
        if url and url.startswith("http"):
            return url

    # Fallback 1: WordPress post image
    elem = soup.select_one("img.wp-post-image")
    if elem:
        url = elem.get("data-large_image") or elem.get("data-src") or elem.get("src")
        if url and url.startswith("http"):
            return url

    # Fallback 2: OpenGraph image
    meta = soup.select_one('meta[property="og:image"]')
    if meta and meta.get("content"):
        url = meta["content"]
        if url.startswith("http"):
            return url

    return None


def extract_availability(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract availability status.

    Primary: Check for 'instock' or 'outofstock' in product classes
    Fallback 1: link[itemprop="availability"]
    Fallback 2: meta[property="product:availability"]

    Confidence: 0.88

    Returns: 'in_stock', 'out_of_stock', or None
    """
    # Primary: WooCommerce stock status classes
    product_div = soup.select_one("div.product")
    if product_div:
        classes = product_div.get("class", [])
        if "instock" in classes:
            return "in_stock"
        elif "outofstock" in classes or "out-of-stock" in classes:
            return "out_of_stock"

    # Fallback 1: Schema.org availability link
    elem = soup.select_one('link[itemprop="availability"]')
    if elem and elem.get("href"):
        href = elem["href"].lower()
        if "instock" in href:
            return "in_stock"
        elif "outofstock" in href:
            return "out_of_stock"

    # Fallback 2: OpenGraph availability
    meta = soup.select_one('meta[property="product:availability"]')
    if meta and meta.get("content"):
        content = meta["content"].lower()
        if "instock" in content or "in stock" in content:
            return "in_stock"
        elif "outofstock" in content or "out of stock" in content:
            return "out_of_stock"

    return None


def extract_article_number(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract article/product number.

    Primary: button[data-product_id] attribute
    Fallback 1: div.product[id] attribute (format: product-1481)
    Fallback 2: Search for product ID in scripts

    Confidence: 0.85
    """
    # Primary: WooCommerce add-to-cart button product_id
    elem = soup.select_one("button[data-product_id]")
    if elem and elem.get("data-product_id"):
        return elem["data-product_id"]

    # Also check anchor tags with data-product_id
    elem = soup.select_one("a[data-product_id]")
    if elem and elem.get("data-product_id"):
        return elem["data-product_id"]

    # Fallback 1: Product div ID (format: product-1481)
    elem = soup.select_one("div.product[id]")
    if elem and elem.get("id"):
        product_id = elem["id"]
        # Extract numeric ID from "product-1481"
        match = re.search(r"product-(\d+)", product_id)
        if match:
            return match.group(1)

    # Fallback 2: Look for product_id in inline scripts
    scripts = soup.find_all("script")
    for script in scripts:
        if script.string:
            match = re.search(r'"product_id":\s*(\d+)', script.string)
            if match:
                return match.group(1)

    return None


def extract_model_number(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract model/SKU number.

    Primary: span.sku (WooCommerce SKU display)
    Fallback 1: button[data-product_sku] attribute
    Fallback 2: meta[itemprop="sku"]

    Confidence: 0.82
    """
    # Primary: WooCommerce SKU span
    elem = soup.select_one("span.sku")
    if elem:
        sku = BaseExtractor.clean_text(elem.get_text())
        if sku and sku.lower() != "n/a":
            return sku

    # Fallback 1: Add-to-cart button SKU attribute
    elem = soup.select_one("button[data-product_sku]")
    if elem and elem.get("data-product_sku"):
        return elem["data-product_sku"]

    # Also check anchor tags
    elem = soup.select_one("a[data-product_sku]")
    if elem and elem.get("data-product_sku"):
        return elem["data-product_sku"]

    # Fallback 2: Schema.org SKU meta
    meta = soup.select_one('meta[itemprop="sku"]')
    if meta and meta.get("content"):
        sku = meta["content"]
        if sku and sku.lower() != "n/a":
            return sku

    return None


def extract_currency(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract currency code.

    Returns:
        Currency code (e.g., 'NOK', 'USD', 'EUR')

    Confidence: 1.0 (hardcoded default)
    """
    return "USD"
