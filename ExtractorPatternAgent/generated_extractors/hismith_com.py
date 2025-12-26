"""
Extractor for hismith.com

Created on: 2025-12-26
"""
import re
import json
from decimal import Decimal
from typing import Optional
from bs4 import BeautifulSoup
from ._base import BaseExtractor


# Metadata (required for discovery)
PATTERN_METADATA = {
    'domain': 'hismith.com',
    'generated_at': '2025-12-26T20:56:34',
    'generator': 'autonomous-agent',
    'version': '1.0',
    'confidence': 0.95,
    'fields': ['price', 'title', 'image', 'availability', 'article_number', 'model_number', 'currency'],
    'notes': 'Initial pattern - extracts from JSON-LD structured data with OpenGraph fallbacks'
}


def extract_price(soup: BeautifulSoup) -> Optional[Decimal]:
    """
    Extract price.

    Primary: JSON-LD offers.price
    Fallback 1: OpenGraph meta tag product:price:amount
    Fallback 2: JavaScript btGapTag data

    Confidence: 0.95
    """
    # PRIMARY: JSON-LD structured data
    scripts = soup.find_all('script', type='application/ld+json')
    for script in scripts:
        if script.string:
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and data.get('@type') == 'Product':
                    offers = data.get('offers', {})
                    if isinstance(offers, dict):
                        price = offers.get('price')
                        if price:
                            return BaseExtractor.clean_price(str(price))
            except (json.JSONDecodeError, ValueError):
                continue

    # FALLBACK 1: OpenGraph meta tag
    elem = soup.select_one('meta[property="product:price:amount"]')
    if elem:
        value = elem.get('content')
        if value:
            return BaseExtractor.clean_price(value)

    # FALLBACK 2: JavaScript btGapTag data
    scripts = soup.find_all('script')
    for script in scripts:
        if script.string and 'btGapTag' in script.string:
            match = re.search(r'"price"[:\s]+([0-9.]+)', script.string)
            if match:
                return BaseExtractor.clean_price(match.group(1))

    return None


def extract_title(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract product title.

    Primary: JSON-LD name field
    Fallback 1: OpenGraph og:title
    Fallback 2: Page title tag

    Confidence: 0.95
    """
    # PRIMARY: JSON-LD structured data
    scripts = soup.find_all('script', type='application/ld+json')
    for script in scripts:
        if script.string:
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and data.get('@type') == 'Product':
                    name = data.get('name')
                    if name:
                        value = BaseExtractor.clean_text(name)
                        return value if value else None
            except (json.JSONDecodeError, ValueError):
                continue

    # FALLBACK 1: OpenGraph meta tag
    elem = soup.select_one('meta[property="og:title"]')
    if elem:
        value = elem.get('content')
        if value:
            value = BaseExtractor.clean_text(value)
            # Remove site name suffix after last dash if present
            if value and ' - ' in value:
                value = value.rsplit(' - ', 1)[0].strip()
            return value if value else None

    # FALLBACK 2: Page title
    elem = soup.select_one('title')
    if elem:
        value = BaseExtractor.clean_text(elem.get_text())
        if value and ' - ' in value:
            value = value.rsplit(' - ', 1)[0].strip()
        return value if value else None

    return None


def extract_image(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract primary product image URL.

    Primary: JSON-LD image field
    Fallback 1: OpenGraph og:image
    Fallback 2: JSON-LD offers.image array (first item)

    Confidence: 0.95
    """
    # PRIMARY: JSON-LD structured data - main image
    scripts = soup.find_all('script', type='application/ld+json')
    for script in scripts:
        if script.string:
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and data.get('@type') == 'Product':
                    image = data.get('image')
                    if image and isinstance(image, str):
                        image = image.strip()
                        if image.startswith('http'):
                            return image
            except (json.JSONDecodeError, ValueError):
                continue

    # FALLBACK 1: OpenGraph meta tag
    elem = soup.select_one('meta[property="og:image"]')
    if elem:
        value = elem.get('content')
        if value:
            value = str(value).strip()
            if value.startswith('http'):
                return value

    # FALLBACK 2: JSON-LD offers.image array (first item)
    scripts = soup.find_all('script', type='application/ld+json')
    for script in scripts:
        if script.string:
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and data.get('@type') == 'Product':
                    offers = data.get('offers', {})
                    if isinstance(offers, dict):
                        images = offers.get('image')
                        if isinstance(images, list) and len(images) > 0:
                            image = images[0]
                            if isinstance(image, str) and image.startswith('http'):
                                return image.strip()
            except (json.JSONDecodeError, ValueError):
                continue

    return None


def extract_availability(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract stock availability status.

    Primary: JSON-LD offers.availability
    Fallback: Look for stock status elements

    Confidence: 0.90
    """
    # PRIMARY: JSON-LD structured data
    scripts = soup.find_all('script', type='application/ld+json')
    for script in scripts:
        if script.string:
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and data.get('@type') == 'Product':
                    offers = data.get('offers', {})
                    if isinstance(offers, dict):
                        availability = offers.get('availability')
                        if availability:
                            # Normalize schema.org availability URLs
                            if 'InStock' in availability:
                                return 'In Stock'
                            elif 'OutOfStock' in availability:
                                return 'Out of Stock'
                            elif 'PreOrder' in availability:
                                return 'Pre-Order'
                            # Return cleaned text if not a schema.org URL
                            value = BaseExtractor.clean_text(availability)
                            return value if value else None
            except (json.JSONDecodeError, ValueError):
                continue

    # FALLBACK: Look for stock status elements
    elem = soup.select_one('.stock-status, .availability, [itemprop="availability"]')
    if elem:
        value = BaseExtractor.clean_text(elem.get_text())
        if value:
            # Normalize common patterns
            if re.search(r'in stock|available', value, re.IGNORECASE):
                return 'In Stock'
            if re.search(r'out of stock|unavailable', value, re.IGNORECASE):
                return 'Out of Stock'
            # Extract numeric quantity
            match = re.search(r'(\d+\+?|>\d+)', value)
            if match:
                return match.group(1)
        return value if value else None

    return None


def extract_article_number(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract store article number (SKU).

    Primary: JSON-LD sku field
    Fallback 1: JSON-LD offers.sku
    Fallback 2: URL pattern extraction

    Confidence: 0.95
    """
    # PRIMARY: JSON-LD structured data - main sku
    scripts = soup.find_all('script', type='application/ld+json')
    for script in scripts:
        if script.string:
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and data.get('@type') == 'Product':
                    sku = data.get('sku')
                    if sku:
                        value = str(sku).strip()
                        if value:
                            return value
            except (json.JSONDecodeError, ValueError):
                continue

    # FALLBACK 1: JSON-LD offers.sku
    scripts = soup.find_all('script', type='application/ld+json')
    for script in scripts:
        if script.string:
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and data.get('@type') == 'Product':
                    offers = data.get('offers', {})
                    if isinstance(offers, dict):
                        sku = offers.get('sku')
                        if sku:
                            value = str(sku).strip()
                            if value:
                                return value
            except (json.JSONDecodeError, ValueError):
                continue

    # FALLBACK 2: URL extraction from canonical link
    elem = soup.select_one('link[rel="canonical"]')
    if elem:
        url = elem.get('href', '')
        if url:
            # Pattern: /805-product-name.html -> extract 805
            match = re.search(r'/(\d+)-[^/]+\.html', url)
            if match:
                return match.group(1)

    return None


def extract_model_number(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract manufacturer model/part number.

    Primary: JSON-LD mpn field
    Fallback: JSON-LD offers.mpn

    Confidence: 0.95
    """
    # PRIMARY: JSON-LD structured data - main mpn
    scripts = soup.find_all('script', type='application/ld+json')
    for script in scripts:
        if script.string:
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and data.get('@type') == 'Product':
                    mpn = data.get('mpn')
                    if mpn:
                        value = str(mpn).strip()
                        if value:
                            return value
            except (json.JSONDecodeError, ValueError):
                continue

    # FALLBACK: JSON-LD offers.mpn
    scripts = soup.find_all('script', type='application/ld+json')
    for script in scripts:
        if script.string:
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and data.get('@type') == 'Product':
                    offers = data.get('offers', {})
                    if isinstance(offers, dict):
                        mpn = offers.get('mpn')
                        if mpn:
                            value = str(mpn).strip()
                            if value:
                                return value
            except (json.JSONDecodeError, ValueError):
                continue

    return None


def extract_currency(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract currency code.

    Primary: JSON-LD offers.priceCurrency
    Fallback 1: OpenGraph product:price:currency
    Fallback 2: JavaScript btGapTag currency

    Confidence: 0.95
    """
    # PRIMARY: JSON-LD structured data
    scripts = soup.find_all('script', type='application/ld+json')
    for script in scripts:
        if script.string:
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and data.get('@type') == 'Product':
                    offers = data.get('offers', {})
                    if isinstance(offers, dict):
                        currency = offers.get('priceCurrency')
                        if currency:
                            value = str(currency).strip().upper()
                            if value:
                                return value
            except (json.JSONDecodeError, ValueError):
                continue

    # FALLBACK 1: OpenGraph meta tag
    elem = soup.select_one('meta[property="product:price:currency"]')
    if elem:
        value = elem.get('content')
        if value:
            return str(value).strip().upper()

    # FALLBACK 2: JavaScript btGapTag data
    scripts = soup.find_all('script')
    for script in scripts:
        if script.string and 'btGapTag' in script.string:
            match = re.search(r'"currency"[:\s]+"([A-Z]{3})"', script.string)
            if match:
                return match.group(1).upper()

    return None
