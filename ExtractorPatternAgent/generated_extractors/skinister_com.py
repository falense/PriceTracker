"""
Extractor for skinister.com

Generated on: 2025-12-26
"""
import re
import json
from decimal import Decimal
from typing import Optional
from bs4 import BeautifulSoup
from ._base import BaseExtractor


# Metadata (required for discovery)
PATTERN_METADATA = {
    'domain': 'skinister.com',
    'generated_at': '2025-12-26T22:18:35',
    'generator': 'autonomous-agent',
    'version': '1.0',
    'confidence': 0.95,
    'fields': ['price', 'title', 'image', 'availability', 'article_number', 'model_number', 'currency'],
    'notes': 'Initial pattern using JSON-LD structured data'
}


def extract_price(soup: BeautifulSoup) -> Optional[Decimal]:
    """
    Extract price.

    Primary: JSON-LD offers.lowPrice (for variable products)
    Fallback 1: JSON-LD offers.price (for simple products)
    Fallback 2: OpenGraph meta tag

    Confidence: 0.95
    """
    # PRIMARY: JSON-LD Schema.org structured data
    scripts = soup.find_all('script', type='application/ld+json')
    for script in scripts:
        if script.string:
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and data.get('@type') == 'Product':
                    offers = data.get('offers')
                    if isinstance(offers, list) and len(offers) > 0:
                        offer = offers[0]
                        # Try lowPrice for AggregateOffer (variable products)
                        if offer.get('@type') == 'AggregateOffer':
                            low_price = offer.get('lowPrice')
                            if low_price:
                                return BaseExtractor.clean_price(low_price)
                        # Try regular price for single offer
                        price = offer.get('price')
                        if price:
                            return BaseExtractor.clean_price(price)
                    elif isinstance(offers, dict):
                        # Single offer object
                        price = offers.get('price') or offers.get('lowPrice')
                        if price:
                            return BaseExtractor.clean_price(price)
            except (json.JSONDecodeError, ValueError):
                continue

    # FALLBACK 1: OpenGraph price meta tag
    elem = soup.select_one('meta[property="og:price:amount"]')
    if elem:
        value = elem.get('content')
        if value:
            return BaseExtractor.clean_price(value)

    # FALLBACK 2: WooCommerce price element
    elem = soup.select_one('.price .woocommerce-Price-amount')
    if elem:
        return BaseExtractor.clean_price(elem.get_text(strip=True))

    return None


def extract_title(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract product title.

    Primary: JSON-LD name field
    Fallback 1: OpenGraph title
    Fallback 2: H1.product_title

    Confidence: 0.95
    """
    # PRIMARY: JSON-LD Schema.org
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

    # FALLBACK 1: OpenGraph title
    elem = soup.select_one('meta[property="og:title"]')
    if elem:
        value = elem.get('content')
        if value:
            value = BaseExtractor.clean_text(value)
            # Remove site suffix (e.g., "| Skinister")
            if value and '|' in value:
                value = value.split('|')[0].strip()
            return value if value else None

    # FALLBACK 2: H1 product title
    elem = soup.select_one('h1.product_title')
    if elem:
        value = BaseExtractor.clean_text(elem.get_text())
        return value if value else None

    return None


def extract_image(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract primary product image URL.

    Primary: JSON-LD image field
    Fallback 1: OpenGraph image (secure)
    Fallback 2: OpenGraph image (regular)

    Confidence: 0.95
    """
    # PRIMARY: JSON-LD Schema.org
    scripts = soup.find_all('script', type='application/ld+json')
    for script in scripts:
        if script.string:
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and data.get('@type') == 'Product':
                    image = data.get('image')
                    if image:
                        # Image can be a string or array
                        if isinstance(image, list) and len(image) > 0:
                            image = image[0]
                        if isinstance(image, str):
                            value = str(image).strip()
                            if value.startswith('http'):
                                return value
            except (json.JSONDecodeError, ValueError):
                continue

    # FALLBACK 1: OpenGraph secure image
    elem = soup.select_one('meta[property="og:image:secure_url"]')
    if elem:
        value = elem.get('content')
        if value:
            value = str(value).strip()
            if value.startswith('http'):
                return value

    # FALLBACK 2: OpenGraph image
    elem = soup.select_one('meta[property="og:image"]')
    if elem:
        value = elem.get('content')
        if value:
            value = str(value).strip()
            if value.startswith('http'):
                return value

    return None


def extract_availability(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract stock availability status.

    Primary: JSON-LD offers.availability
    Fallback 1: WooCommerce stock status element

    Confidence: 0.90
    """
    # PRIMARY: JSON-LD Schema.org
    scripts = soup.find_all('script', type='application/ld+json')
    for script in scripts:
        if script.string:
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and data.get('@type') == 'Product':
                    offers = data.get('offers')
                    if isinstance(offers, list) and len(offers) > 0:
                        offer = offers[0]
                        availability = offer.get('availability')
                        if availability:
                            # Normalize Schema.org availability to simple status
                            if 'InStock' in availability:
                                return 'In Stock'
                            elif 'OutOfStock' in availability:
                                return 'Out of Stock'
                            elif 'PreOrder' in availability:
                                return 'Pre-Order'
                    elif isinstance(offers, dict):
                        availability = offers.get('availability')
                        if availability:
                            if 'InStock' in availability:
                                return 'In Stock'
                            elif 'OutOfStock' in availability:
                                return 'Out of Stock'
                            elif 'PreOrder' in availability:
                                return 'Pre-Order'
            except (json.JSONDecodeError, ValueError):
                continue

    # FALLBACK: WooCommerce stock status
    elem = soup.select_one('.stock.in-stock')
    if elem:
        return 'In Stock'

    elem = soup.select_one('.stock.out-of-stock')
    if elem:
        return 'Out of Stock'

    return None


def extract_article_number(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract store article number (SKU).

    Primary: JSON-LD sku field
    Fallback 1: WooCommerce SKU element
    Fallback 2: itemprop="sku"

    Confidence: 0.95
    """
    # PRIMARY: JSON-LD Schema.org
    scripts = soup.find_all('script', type='application/ld+json')
    for script in scripts:
        if script.string:
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and data.get('@type') == 'Product':
                    sku = data.get('sku')
                    if sku:
                        return str(sku).strip()
                    # Also check in offers
                    offers = data.get('offers')
                    if isinstance(offers, list) and len(offers) > 0:
                        sku = offers[0].get('sku')
                        if sku:
                            return str(sku).strip()
                    elif isinstance(offers, dict):
                        sku = offers.get('sku')
                        if sku:
                            return str(sku).strip()
            except (json.JSONDecodeError, ValueError):
                continue

    # FALLBACK 1: WooCommerce SKU element
    elem = soup.select_one('.sku')
    if elem:
        value = BaseExtractor.clean_text(elem.get_text())
        if value:
            return value

    # FALLBACK 2: itemprop="sku"
    elem = soup.select_one('[itemprop="sku"]')
    if elem:
        value = elem.get('content') or BaseExtractor.clean_text(elem.get_text())
        if value:
            return value

    return None


def extract_model_number(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract manufacturer model/part number.

    Primary: JSON-LD mpn field
    Fallback 1: JSON-LD gtin12 field
    Fallback 2: Product meta table

    Confidence: 0.80
    """
    # PRIMARY: JSON-LD mpn (Manufacturer Part Number)
    scripts = soup.find_all('script', type='application/ld+json')
    for script in scripts:
        if script.string:
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and data.get('@type') == 'Product':
                    # Check for mpn
                    mpn = data.get('mpn')
                    if mpn:
                        return str(mpn).strip()

                    # Check in offers
                    offers = data.get('offers')
                    if isinstance(offers, list) and len(offers) > 0:
                        offer = offers[0]
                        # Try gtin12 as fallback
                        gtin = offer.get('gtin12') or offer.get('gtin13') or offer.get('gtin')
                        if gtin:
                            return str(gtin).strip()
                    elif isinstance(offers, dict):
                        gtin = offers.get('gtin12') or offers.get('gtin13') or offers.get('gtin')
                        if gtin:
                            return str(gtin).strip()
            except (json.JSONDecodeError, ValueError):
                continue

    # FALLBACK: Product meta table
    elem = soup.select_one('.product_meta .sku')
    if elem:
        value = BaseExtractor.clean_text(elem.get_text())
        if value:
            return value

    return None


def extract_currency(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract currency code.

    Primary: JSON-LD priceCurrency field
    Fallback 1: OpenGraph price:currency meta tag
    Fallback 2: WooCommerce currency symbol detection

    Confidence: 0.95
    """
    # PRIMARY: JSON-LD Schema.org
    scripts = soup.find_all('script', type='application/ld+json')
    for script in scripts:
        if script.string:
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and data.get('@type') == 'Product':
                    offers = data.get('offers')
                    if isinstance(offers, list) and len(offers) > 0:
                        currency = offers[0].get('priceCurrency')
                        if currency:
                            return str(currency).strip().upper()
                    elif isinstance(offers, dict):
                        currency = offers.get('priceCurrency')
                        if currency:
                            return str(currency).strip().upper()
            except (json.JSONDecodeError, ValueError):
                continue

    # FALLBACK 1: OpenGraph meta tag
    elem = soup.select_one('meta[property="og:price:currency"]')
    if elem:
        value = elem.get('content')
        if value:
            return str(value).strip().upper()

    # FALLBACK 2: Currency symbol detection from price element
    elem = soup.select_one('.price .woocommerce-Price-currencySymbol')
    if elem:
        symbol = elem.get_text(strip=True)
        # Map common symbols to currency codes
        symbol_map = {
            '$': 'USD',
            '€': 'EUR',
            '£': 'GBP',
            '¥': 'JPY',
            'kr': 'NOK',  # or SEK, DKK - ambiguous
        }
        return symbol_map.get(symbol, None)

    return None
