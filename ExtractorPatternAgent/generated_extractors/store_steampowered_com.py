"""
Extractor for store.steampowered.com

Created on: 2025-12-26
"""
import re
from decimal import Decimal
from typing import Optional
from bs4 import BeautifulSoup
from ._base import BaseExtractor


# Metadata (required for discovery)
PATTERN_METADATA = {
    'domain': 'store.steampowered.com',
    'generated_at': '2025-12-26T21:01:42',
    'generator': 'autonomous-agent',
    'version': '1.1',
    'confidence': 0.95,
    'fields': ['price', 'title', 'image', 'availability', 'article_number', 'model_number', 'currency'],
    'notes': 'Initial pattern for Steam store product pages. Fixed availability detection to avoid false positives from recommended games.'
}


def extract_price(soup: BeautifulSoup) -> Optional[Decimal]:
    """
    Extract price.

    Primary: meta[itemprop="price"] content attribute
    Fallback 1: data-price-final attribute (price in cents)
    Fallback 2: .discount_final_price text content

    Confidence: 0.95
    """
    # PRIMARY: Schema.org microdata (most reliable)
    elem = soup.select_one('meta[itemprop="price"]')
    if elem:
        value = elem.get('content')
        if value:
            # Steam uses comma as decimal separator (e.g., "123,20")
            return BaseExtractor.clean_price(value)

    # FALLBACK 1: data-price-final attribute (in cents, e.g., "12320" = 123.20)
    elem = soup.select_one('.discount_block[data-price-final]')
    if elem:
        value = elem.get('data-price-final')
        if value:
            try:
                # Convert cents to decimal
                price_cents = int(value)
                return Decimal(price_cents) / 100
            except (ValueError, TypeError):
                pass

    # FALLBACK 2: Final price text
    elem = soup.select_one('.discount_final_price')
    if elem:
        return BaseExtractor.clean_price(elem.get_text(strip=True))

    return None


def extract_title(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract product title.

    Primary: og:title meta tag (cleaned)
    Fallback 1: Twitter title meta tag
    Fallback 2: Page title tag

    Confidence: 0.95

    Note: Removes "Save X% on" prefix and "on Steam" suffix
    """
    # PRIMARY: OpenGraph title
    elem = soup.select_one('meta[property="og:title"]')
    if elem:
        value = elem.get('content')
        if value:
            value = BaseExtractor.clean_text(value)
            if value:
                # Remove "Save X% on " prefix
                value = re.sub(r'^Save\s+\d+%\s+on\s+', '', value, flags=re.IGNORECASE).strip()
                # Remove " on Steam" suffix
                value = re.sub(r'\s+on\s+Steam$', '', value, flags=re.IGNORECASE).strip()
                return value if value else None

    # FALLBACK 1: Twitter title
    elem = soup.select_one('meta[property="twitter:title"]')
    if elem:
        value = elem.get('content')
        if value:
            value = BaseExtractor.clean_text(value)
            if value:
                value = re.sub(r'^Save\s+\d+%\s+on\s+', '', value, flags=re.IGNORECASE).strip()
                value = re.sub(r'\s+on\s+Steam$', '', value, flags=re.IGNORECASE).strip()
                return value if value else None

    # FALLBACK 2: Page title
    elem = soup.select_one('title')
    if elem:
        value = BaseExtractor.clean_text(elem.get_text())
        if value:
            value = re.sub(r'^Save\s+\d+%\s+on\s+', '', value, flags=re.IGNORECASE).strip()
            value = re.sub(r'\s+on\s+Steam$', '', value, flags=re.IGNORECASE).strip()
            return value if value else None

    return None


def extract_image(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract primary product image URL.

    Primary: og:image meta tag
    Fallback 1: twitter:image meta tag
    Fallback 2: link[rel="image_src"] href

    Confidence: 0.95
    """
    # PRIMARY: OpenGraph image
    elem = soup.select_one('meta[property="og:image"]')
    if elem:
        value = elem.get('content')
        if value:
            value = str(value).strip()
            if value.startswith('http'):
                return value

    # FALLBACK 1: Twitter image
    elem = soup.select_one('meta[name="twitter:image"]')
    if elem:
        value = elem.get('content')
        if value:
            value = str(value).strip()
            if value.startswith('http'):
                return value

    # FALLBACK 2: Image source link
    elem = soup.select_one('link[rel="image_src"]')
    if elem:
        value = elem.get('href')
        if value:
            value = str(value).strip()
            if value.startswith('http'):
                return value

    return None


def extract_availability(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract stock availability status.

    Note: Steam games are generally always available digitally.
    This may return "Available" or None.

    Confidence: 0.80
    """
    # Check for "Coming Soon" indicator in main game area
    elem = soup.select_one('.game_area_comingsoon')
    if elem:
        return "Coming Soon"

    # Check for specific release date area (more targeted than global JSON search)
    elem = soup.select_one('.game_area_purchase .game_area_comingsoon')
    if elem:
        return "Coming Soon"

    # If we found a price, assume it's available for purchase
    price = extract_price(soup)
    if price is not None:
        if price > 0:
            return "Available"
        else:
            # Free games are also available
            elem = soup.select_one('.discount_final_price')
            if elem:
                text = elem.get_text(strip=True)
                if text and re.search(r'free', text, re.IGNORECASE):
                    return "Available"

    return None


def extract_article_number(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract Steam App ID from URL.

    Primary: Extract from canonical URL
    Fallback 1: Extract from og:url meta tag
    Fallback 2: Extract from current page URL in JSON data

    Confidence: 0.95
    """
    # PRIMARY: Canonical URL
    elem = soup.select_one('link[rel="canonical"]')
    if elem:
        url = elem.get('href', '')
        if url:
            # Extract app ID from URL pattern: /app/1178780/
            match = re.search(r'/app/(\d+)/', url)
            if match:
                return match.group(1)

    # FALLBACK 1: OpenGraph URL
    elem = soup.select_one('meta[property="og:url"]')
    if elem:
        url = elem.get('content', '')
        if url:
            match = re.search(r'/app/(\d+)/', url)
            if match:
                return match.group(1)

    # FALLBACK 2: Search in page data attributes
    elem = soup.select_one('[data-appid]')
    if elem:
        value = elem.get('data-appid')
        if value:
            return str(value).strip()

    return None


def extract_model_number(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract manufacturer model/part number.

    Note: Not applicable for digital game stores.
    Steam games don't have manufacturer model numbers.

    Confidence: 0.0
    """
    return None


def extract_currency(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract currency code.

    Primary: meta[itemprop="priceCurrency"] content attribute
    Fallback 1: Detect from price text format

    Confidence: 0.95
    """
    # PRIMARY: Schema.org priceCurrency
    elem = soup.select_one('meta[itemprop="priceCurrency"]')
    if elem:
        value = elem.get('content')
        if value:
            value = str(value).strip().upper()
            if value:
                return value

    # FALLBACK: Try to detect from price text
    elem = soup.select_one('.discount_final_price')
    if elem:
        text = elem.get_text(strip=True)
        # Common patterns: "kr", "€", "$", "£", "¥"
        if 'kr' in text.lower():
            return 'NOK'  # or SEK/DKK - default to NOK
        elif '€' in text:
            return 'EUR'
        elif '$' in text:
            return 'USD'
        elif '£' in text:
            return 'GBP'
        elif '¥' in text:
            return 'JPY'

    return None
