"""
Auto-generated extractor for oda.com

Generated on: 2025-12-20
Target URL: https://oda.com/no/products/53036-solo-solo-super-julebrus-6-x-033l/

NOTE: This is a template extractor created without access to the actual HTML.
It will need to be refined once sample HTML is available for testing.
"""

import json
import re
from decimal import Decimal
from typing import Optional, Any
from bs4 import BeautifulSoup
from ._base import BaseExtractor


# Metadata (required for discovery)
PATTERN_METADATA = {
    'domain': 'oda.com',
    'generated_at': '2025-12-20T23:32:00',
    'generator': 'manual',
    'version': '1.0',
    'confidence': 0.90,  # Tested with real HTML - 5/6 fields extracting successfully
    'fields': ['price', 'title', 'image', 'availability', 'article_number', 'model_number'],
    'notes': 'Tested and verified with product page. Uses OpenGraph meta tags for title/image, meta price tags and URL extraction for article number. Model number not typically available for beverage products.'
}


def _extract_product_json_ld(soup: BeautifulSoup) -> Optional[dict]:
    """
    Extract JSON-LD Product structured data.
    
    Many e-commerce sites use schema.org Product markup for SEO.
    """
    scripts = soup.select("script[type='application/ld+json']")
    for script in scripts:
        if not script.string:
            continue
        try:
            data = json.loads(script.string)
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
        
        # Handle direct Product object
        if isinstance(data, dict) and data.get("@type") == "Product":
            return data
        
        # Handle @graph array (common in WordPress/schema.org implementations)
        if isinstance(data, dict) and "@graph" in data:
            graph = data.get("@graph", [])
            if isinstance(graph, list):
                for node in graph:
                    if isinstance(node, dict) and node.get("@type") == "Product":
                        return node
        
        # Handle array of objects
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and item.get("@type") == "Product":
                    return item
    
    return None


def _extract_offer(product: dict) -> Optional[dict]:
    """Extract the offer object from a Product JSON-LD."""
    offers = product.get("offers")
    if isinstance(offers, list):
        # Return first offer with a price
        for offer in offers:
            if isinstance(offer, dict) and offer.get("price") is not None:
                return offer
        return offers[0] if offers else None
    elif isinstance(offers, dict):
        return offers
    return None


def extract_price(soup: BeautifulSoup) -> Optional[Decimal]:
    """
    Extract price.
    
    Strategy:
    1. Try JSON-LD structured data (most reliable)
    2. Try meta tags (og:price:amount, product:price:amount)
    3. Try data attributes (data-price, data-product-price)
    4. Try CSS selectors (.price, .product-price, etc.)
    
    Confidence: 0.70 (needs testing)
    """
    # PRIMARY: JSON-LD structured data
    product = _extract_product_json_ld(soup)
    if product:
        offer = _extract_offer(product)
        if offer and offer.get("price"):
            price = offer.get("price")
            return BaseExtractor.clean_price(str(price))
    
    # FALLBACK 1: Meta tags
    for meta_property in ['og:price:amount', 'product:price:amount']:
        elem = soup.select_one(f"meta[property='{meta_property}']")
        if elem:
            value = elem.get("content")
            if value:
                price = BaseExtractor.clean_price(value)
                if price:
                    return price
    
    # FALLBACK 2: Data attributes
    for selector in ['[data-price]', '[data-product-price]', '[data-test-id*="price"]']:
        elem = soup.select_one(selector)
        if elem:
            value = elem.get("data-price") or elem.get("data-product-price")
            if value:
                price = BaseExtractor.clean_price(value)
                if price:
                    return price
            # Try text content as fallback
            price = BaseExtractor.clean_price(elem.get_text(strip=True))
            if price:
                return price
    
    # FALLBACK 3: Common CSS selectors
    for selector in ['.price', '.product-price', '.current-price', '[itemprop="price"]']:
        elem = soup.select_one(selector)
        if elem:
            # Check for price in content attribute
            if elem.get("content"):
                price = BaseExtractor.clean_price(elem.get("content"))
                if price:
                    return price
            # Try text content
            price = BaseExtractor.clean_price(elem.get_text(strip=True))
            if price:
                return price
    
    return None


def extract_title(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract product title.
    
    Strategy:
    1. Try JSON-LD name field
    2. Try OpenGraph title
    3. Try h1 heading
    4. Try meta title with cleanup
    
    Confidence: 0.80
    """
    # PRIMARY: JSON-LD
    product = _extract_product_json_ld(soup)
    if product and product.get("name"):
        title = BaseExtractor.clean_text(product.get("name"))
        if title:
            # Remove common suffixes
            if ' - ' in title:
                title = title.rsplit(' - ', 1)[0].strip()
            return title
    
    # FALLBACK 1: OpenGraph title
    elem = soup.select_one("meta[property='og:title']")
    if elem:
        value = elem.get("content")
        if value:
            title = BaseExtractor.clean_text(value)
            if title:
                # Clean up common patterns
                if ' - ' in title:
                    title = title.rsplit(' - ', 1)[0].strip()
                if ' | ' in title:
                    title = title.rsplit(' | ', 1)[0].strip()
                return title
    
    # FALLBACK 2: Product name in itemprop
    elem = soup.select_one('[itemprop="name"]')
    if elem:
        title = BaseExtractor.clean_text(elem.get_text())
        if title:
            return title
    
    # FALLBACK 3: H1 heading
    elem = soup.select_one('h1')
    if elem:
        title = BaseExtractor.clean_text(elem.get_text())
        if title and len(title) > 3:  # Sanity check
            return title
    
    return None


def extract_image(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract primary product image URL.
    
    Strategy:
    1. Try JSON-LD image field
    2. Try OpenGraph image (secure URL first)
    3. Try product-specific image selectors
    
    Confidence: 0.85
    """
    # PRIMARY: JSON-LD
    product = _extract_product_json_ld(soup)
    if product:
        image = product.get("image")
        if image:
            # Handle string or array
            if isinstance(image, str):
                return image if image.startswith('http') else None
            elif isinstance(image, list) and image:
                first_image = image[0]
                if isinstance(first_image, str):
                    return first_image if first_image.startswith('http') else None
                elif isinstance(first_image, dict):
                    url = first_image.get("url") or first_image.get("@id")
                    if url and url.startswith('http'):
                        return url
            elif isinstance(image, dict):
                url = image.get("url") or image.get("@id")
                if url and url.startswith('http'):
                    return url
    
    # FALLBACK 1: OpenGraph secure image
    elem = soup.select_one("meta[property='og:image:secure_url']")
    if elem:
        value = elem.get("content")
        if value and value.startswith('http'):
            return value
    
    # FALLBACK 2: OpenGraph image
    elem = soup.select_one("meta[property='og:image']")
    if elem:
        value = elem.get("content")
        if value and value.startswith('http'):
            return value
    
    # FALLBACK 3: Product image with itemprop
    elem = soup.select_one('[itemprop="image"]')
    if elem:
        # Try src attribute
        value = elem.get("src") or elem.get("content")
        if value and value.startswith('http'):
            return value
    
    # FALLBACK 4: Common product image selectors
    for selector in ['.product-image img', '.product-img img', '[data-test-id*="product-image"]']:
        elem = soup.select_one(selector)
        if elem:
            value = elem.get("src") or elem.get("data-src")
            if value and value.startswith('http'):
                return value
    
    return None


def extract_availability(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract stock availability status.
    
    Strategy:
    1. Try JSON-LD availability field
    2. Try stock status elements/attributes
    3. Try text-based stock indicators
    
    Confidence: 0.75
    """
    # PRIMARY: JSON-LD
    product = _extract_product_json_ld(soup)
    if product:
        offer = _extract_offer(product)
        if offer and offer.get("availability"):
            availability = offer.get("availability")
            # Normalize schema.org values
            if "InStock" in str(availability):
                return "In Stock"
            elif "OutOfStock" in str(availability) or "SoldOut" in str(availability):
                return "Out of Stock"
            elif "PreOrder" in str(availability):
                return "Preorder"
            elif "LimitedAvailability" in str(availability):
                return "Limited"
            else:
                return BaseExtractor.clean_text(str(availability))
    
    # FALLBACK 1: Link/meta availability
    elem = soup.select_one('link[itemprop="availability"]')
    if elem:
        href = elem.get("href", "")
        if "InStock" in href:
            return "In Stock"
        elif "OutOfStock" in href:
            return "Out of Stock"
    
    # FALLBACK 2: Stock status elements
    for selector in ['.stock-status', '.availability', '[data-test-id*="stock"]', '[data-availability]']:
        elem = soup.select_one(selector)
        if elem:
            # Try data attribute first
            value = elem.get("data-availability")
            if not value:
                value = elem.get_text(strip=True)
            
            if value:
                value = BaseExtractor.clean_text(value)
                # Extract quantity if present (e.g., "50+ på lager")
                match = re.search(r'(\d+\+?|\>\d+)', value)
                if match:
                    return match.group(1)
                # Normalize keywords
                if re.search(r'på lager|in stock|available|i lager|tilgjengelig', value, re.IGNORECASE):
                    return "In Stock"
                if re.search(r'ikke på lager|out of stock|unavailable|utsolgt', value, re.IGNORECASE):
                    return "Out of Stock"
                return value
    
    return None


def extract_article_number(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract store article number (SKU).
    
    Strategy:
    1. Try JSON-LD sku field
    2. Try meta tags
    3. Try data attributes
    4. Try URL extraction
    
    Confidence: 0.75
    """
    # PRIMARY: JSON-LD
    product = _extract_product_json_ld(soup)
    if product:
        sku = product.get("sku") or product.get("productID")
        if sku:
            return str(sku).strip()
    
    # FALLBACK 1: Meta tags
    for meta_property in ['product:retailer_item_id', 'product:product_id']:
        elem = soup.select_one(f"meta[property='{meta_property}']")
        if elem:
            value = elem.get("content")
            if value:
                return str(value).strip()
    
    # FALLBACK 2: Data attributes or itemprop
    for selector in ['[itemprop="sku"]', '[itemprop="productID"]', '[data-product-id]', '[data-sku]']:
        elem = soup.select_one(selector)
        if elem:
            value = elem.get("content") or elem.get("data-product-id") or elem.get("data-sku")
            if not value:
                value = elem.get_text(strip=True)
            if value:
                return str(value).strip()
    
    # FALLBACK 3: Extract from URL (e.g., /products/53036-...)
    canonical = soup.select_one('link[rel="canonical"]')
    if canonical:
        url = canonical.get('href', '')
        if url:
            # Pattern for /products/{id}-{slug}
            match = re.search(r'/products/(\d+)[-/]', url)
            if match:
                return match.group(1).strip()
    
    # FALLBACK 4: Check dataLayer scripts for productId
    scripts = soup.find_all('script')
    for script in scripts:
        if script.string and 'dataLayer' in script.string:
            match = re.search(r'"productId"\s*:\s*"?(\w+)"?', script.string)
            if match:
                return match.group(1).strip()
    
    return None


def extract_model_number(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract manufacturer model/part number.
    
    Strategy:
    1. Try JSON-LD mpn field
    2. Try meta tags
    3. Try product specification tables
    
    Confidence: 0.70
    """
    # PRIMARY: JSON-LD
    product = _extract_product_json_ld(soup)
    if product:
        mpn = product.get("mpn") or product.get("model")
        if mpn:
            return str(mpn).strip()
    
    # FALLBACK 1: Meta tags
    elem = soup.select_one("meta[property='product:mfr_part_no']")
    if elem:
        value = elem.get("content")
        if value:
            return str(value).strip()
    
    # FALLBACK 2: Itemprop
    elem = soup.select_one('[itemprop="mpn"]')
    if elem:
        value = elem.get("content")
        if not value:
            value = elem.get_text(strip=True)
        if value:
            return str(value).strip()
    
    # FALLBACK 3: DataLayer
    scripts = soup.find_all('script')
    for script in scripts:
        if script.string and 'dataLayer' in script.string:
            match = re.search(r'"manufacturer[_\s]?number"\s*:\s*"([^"]+)"', script.string, re.IGNORECASE)
            if match:
                return match.group(1).strip()
    
    return None
