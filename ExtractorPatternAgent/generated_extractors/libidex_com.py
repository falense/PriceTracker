"""
Auto-generated extractor for libidex.com

Generated on 2025-12-22
Confidence: 0.95 (JSON-LD structured data available)
"""
import json
import re
from decimal import Decimal
from typing import Optional
from bs4 import BeautifulSoup
from ._base import BaseExtractor


# Metadata (required for discovery)
PATTERN_METADATA = {
    'domain': 'libidex.com',
    'generated_at': '2025-12-22T22:59:52',
    'generator': 'Pattern Generation Agent',
    'version': '1.0',
    'confidence': 0.95,
    'fields': ['price', 'title', 'image', 'availability', 'article_number', 'model_number', 'currency'],
    'notes': 'Uses JSON-LD structured data as primary extraction method with meta tag fallbacks'
}


def _get_json_ld_product(soup: BeautifulSoup) -> Optional[dict]:
    """
    Extract JSON-LD Product structured data.
    
    Returns:
        Product JSON-LD object or None
    """
    scripts = soup.find_all('script', {'type': 'application/ld+json'})
    for script in scripts:
        if not script.string:
            continue
        try:
            data = json.loads(script.string)
            if isinstance(data, dict) and data.get('@type') == 'Product':
                return data
        except (json.JSONDecodeError, ValueError):
            continue
    return None


def extract_price(soup: BeautifulSoup) -> Optional[Decimal]:
    """
    Extract price.

    Primary: JSON-LD structured data offers.price
    Fallback 1: Meta tag product:price:amount
    Fallback 2: Price container data attribute
    Confidence: 0.95
    """
    # Primary: JSON-LD structured data
    json_ld = _get_json_ld_product(soup)
    if json_ld:
        offers = json_ld.get('offers', {})
        if isinstance(offers, dict):
            price = offers.get('price')
            if price:
                return BaseExtractor.clean_price(str(price))
    
    # Fallback 1: Meta tag
    elem = soup.select_one("meta[property='product:price:amount']")
    if elem:
        value = elem.get('content')
        if value:
            return BaseExtractor.clean_price(value)
    
    # Fallback 2: Price container with data attribute
    elem = soup.select_one("span[data-price-amount][data-price-type='finalPrice']")
    if elem:
        value = elem.get('data-price-amount')
        if value:
            return BaseExtractor.clean_price(value)
    
    # Fallback 3: Price display text
    elem = soup.select_one(".price-box .price-wrapper .price")
    if elem:
        return BaseExtractor.clean_price(elem.get_text())

    return None


def extract_title(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract title.

    Primary: JSON-LD structured data name field
    Fallback 1: Open Graph title meta tag
    Fallback 2: Page title h1
    Confidence: 0.95
    """
    # Primary: JSON-LD structured data
    json_ld = _get_json_ld_product(soup)
    if json_ld:
        name = json_ld.get('name')
        if name:
            return BaseExtractor.clean_text(name)
    
    # Fallback 1: Open Graph meta tag
    elem = soup.select_one("meta[property='og:title']")
    if elem:
        value = elem.get('content')
        if value:
            return BaseExtractor.clean_text(value)
    
    # Fallback 2: Page heading
    elem = soup.select_one("h1.page-title")
    if elem:
        return BaseExtractor.clean_text(elem.get_text())
    
    # Fallback 3: Any h1
    elem = soup.select_one("h1")
    if elem:
        return BaseExtractor.clean_text(elem.get_text())

    return None


def extract_image(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract image.

    Primary: JSON-LD structured data image field
    Fallback 1: Open Graph image meta tag
    Fallback 2: Main product image
    Confidence: 0.95
    """
    # Primary: JSON-LD structured data
    json_ld = _get_json_ld_product(soup)
    if json_ld:
        image = json_ld.get('image')
        if image:
            image_url = image if isinstance(image, str) else image[0] if isinstance(image, list) else None
            if image_url and image_url.startswith('http'):
                return image_url.strip()
    
    # Fallback 1: Open Graph image
    elem = soup.select_one("meta[property='og:image']")
    if elem:
        value = elem.get('content')
        if value and value.startswith('http'):
            return value.strip()
    
    # Fallback 2: Main product image
    elem = soup.select_one(".product.media img.gallery-placeholder__image")
    if elem:
        value = elem.get('src')
        if value and value.startswith('http'):
            return value.strip()
    
    # Fallback 3: Any product image
    elem = soup.select_one(".product-image-container img")
    if elem:
        value = elem.get('src')
        if value and value.startswith('http'):
            return value.strip()

    return None


def extract_availability(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract availability.

    Primary: JSON-LD structured data offers.availability
    Fallback 1: Meta tag product:availability
    Fallback 2: Stock status element
    Confidence: 0.90
    """
    # Primary: JSON-LD structured data
    json_ld = _get_json_ld_product(soup)
    if json_ld:
        offers = json_ld.get('offers', {})
        if isinstance(offers, dict):
            availability = offers.get('availability')
            if availability:
                # Convert schema.org URL to readable text
                if 'InStock' in availability:
                    return 'In Stock'
                elif 'OutOfStock' in availability:
                    return 'Out of Stock'
                elif 'PreOrder' in availability:
                    return 'Pre-Order'
                elif 'LimitedAvailability' in availability:
                    return 'Limited Stock'
                return BaseExtractor.clean_text(availability)
    
    # Fallback 1: Meta tag
    elem = soup.select_one("meta[property='product:availability']")
    if elem:
        value = elem.get('content')
        if value:
            value = BaseExtractor.clean_text(value)
            if value:
                # Normalize common values
                value_lower = value.lower()
                if 'in stock' in value_lower or 'available' in value_lower:
                    return 'In Stock'
                elif 'out of stock' in value_lower or 'unavailable' in value_lower:
                    return 'Out of Stock'
                return value
    
    # Fallback 2: Stock status element
    elem = soup.select_one(".stock.available, .product-info-stock-sku .stock")
    if elem:
        value = BaseExtractor.clean_text(elem.get_text())
        if value:
            value_lower = value.lower()
            if 'in stock' in value_lower or 'available' in value_lower:
                return 'In Stock'
            elif 'out of stock' in value_lower or 'unavailable' in value_lower:
                return 'Out of Stock'
            return value

    return None


def extract_article_number(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract article_number (SKU).
    
    Primary: JSON-LD structured data sku field
    Fallback 1: Form data-product-sku attribute
    Fallback 2: SKU display element
    Confidence: 0.95
    """
    # Primary: JSON-LD structured data
    json_ld = _get_json_ld_product(soup)
    if json_ld:
        sku = json_ld.get('sku')
        if sku:
            return BaseExtractor.clean_text(str(sku))
        
        # Also check in offers
        offers = json_ld.get('offers', {})
        if isinstance(offers, dict):
            sku = offers.get('sku')
            if sku:
                return BaseExtractor.clean_text(str(sku))
    
    # Fallback 1: Form data attribute
    elem = soup.select_one("form[data-product-sku]")
    if elem:
        value = elem.get('data-product-sku')
        if value:
            return BaseExtractor.clean_text(value)
    
    # Fallback 2: SKU display element
    elem = soup.select_one(".product.attribute.sku .value")
    if elem:
        return BaseExtractor.clean_text(elem.get_text())

    return None


def extract_model_number(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract model_number (manufacturer part number).
    
    Primary: JSON-LD structured data mpn field
    Fallback 1: JSON-LD model field
    Confidence: 0.90
    """
    # Primary: JSON-LD structured data MPN
    json_ld = _get_json_ld_product(soup)
    if json_ld:
        mpn = json_ld.get('mpn')
        if mpn:
            return BaseExtractor.clean_text(str(mpn))
        
        # Fallback: model field
        model = json_ld.get('model')
        if model:
            return BaseExtractor.clean_text(str(model))
    
    return None


def extract_currency(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract currency code.
    
    Primary: JSON-LD structured data offers.priceCurrency
    Fallback 1: Meta tag product:price:currency
    Fallback 2: Price meta tag currency
    
    Returns:
        Currency code (e.g., 'GBP', 'USD', 'EUR')
    
    Confidence: 0.95
    """
    # Primary: JSON-LD structured data
    json_ld = _get_json_ld_product(soup)
    if json_ld:
        offers = json_ld.get('offers', {})
        if isinstance(offers, dict):
            currency = offers.get('priceCurrency')
            if currency:
                return currency.strip().upper()
    
    # Fallback 1: Meta tag
    elem = soup.select_one("meta[property='product:price:currency']")
    if elem:
        value = elem.get('content')
        if value:
            return value.strip().upper()
    
    # Fallback 2: Price container meta
    elem = soup.select_one(".price-box meta[content]")
    if elem:
        # Look for currency meta near price
        parent = elem.parent
        if parent:
            currency_meta = parent.find('meta', attrs={'content': re.compile(r'^[A-Z]{3}$')})
            if currency_meta:
                value = currency_meta.get('content')
                if value:
                    return value.strip().upper()
    
    # Default to GBP (libidex.com is UK-based)
    return "GBP"
