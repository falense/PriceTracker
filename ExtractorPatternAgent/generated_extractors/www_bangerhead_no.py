"""
Auto-generated extractor for www.bangerhead.no

Generated: 2025-12-27
Confidence: 0.95
"""
import json
import re
from decimal import Decimal
from typing import Optional
from bs4 import BeautifulSoup
from ._base import BaseExtractor


# Metadata (required for discovery)
PATTERN_METADATA = {
    'domain': 'bangerhead.no',
    'generated_at': '2025-12-27T17:33:00',
    'generator': 'Manual extractor creation',
    'version': '1.0',
    'confidence': 0.95,
    'fields': ['price', 'title', 'image', 'availability', 'article_number', 'currency'],
    'notes': 'Uses microdata (itemprop) and Open Graph meta tags for reliable extraction. Norwegian beauty e-commerce site.'
}


def extract_price(soup: BeautifulSoup) -> Optional[Decimal]:
    """
    Extract price.

    Primary: Microdata itemprop="price"
    Fallback 1: CSS selector div.product-price span.PrisBOLD
    Fallback 2: Open Graph meta tag (if available)
    Confidence: 0.95
    """
    # Primary: Microdata itemprop="price"
    meta = soup.find('meta', itemprop='price')
    if meta:
        price_value = meta.get('content')
        if price_value:
            return BaseExtractor.clean_price(str(price_value))

    # Fallback 1: CSS selector for displayed price
    price_span = soup.select_one('div.product-price span.PrisBOLD')
    if price_span:
        price_text = price_span.get_text(strip=True)
        if price_text:
            return BaseExtractor.clean_price(price_text)

    # Fallback 2: Try the price container div
    price_div = soup.select_one('div.product-price.update_pris')
    if price_div:
        price_text = price_div.get_text(strip=True)
        if price_text:
            return BaseExtractor.clean_price(price_text)

    return None


def extract_title(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract title.

    Primary: Open Graph title meta tag
    Fallback 1: H1 element
    Confidence: 0.95
    """
    # Primary: Open Graph title
    meta = soup.find('meta', property='og:title')
    if meta:
        title = meta.get('content')
        if title:
            return BaseExtractor.clean_text(title)

    # Fallback 1: H1 element (note: may include article number)
    h1 = soup.find('h1')
    if h1:
        title = h1.get_text(strip=True)
        if title:
            # Clean up: remove article number if present
            # Format: "CutrinBio+ Special Anti-Dandruff Shampoo (250ml)B050452"
            title = re.sub(r'B\d{6}$', '', title).strip()
            # Also clean up "Artnr:" prefix if present
            title = re.sub(r'Artnr:\s*', '', title, flags=re.IGNORECASE).strip()
            return BaseExtractor.clean_text(title)

    return None


def extract_image(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract image.

    Primary: Open Graph image meta tag
    Fallback 1: Product image with artiklar in src
    Confidence: 0.95
    """
    # Primary: Open Graph image
    meta = soup.find('meta', property='og:image')
    if meta:
        image_url = meta.get('content')
        if image_url:
            image_url = str(image_url).strip()
            # Ensure it's a full URL
            if image_url.startswith('http'):
                return image_url
            elif image_url.startswith('/'):
                return f'https://www.bangerhead.no{image_url}'
            else:
                return f'https://www.bangerhead.no/{image_url}'

    # Fallback 1: Find product image (artiklar pattern)
    img = soup.select_one('img[src*="artiklar"]')
    if img:
        image_url = img.get('src')
        if image_url:
            image_url = str(image_url).strip()
            if image_url.startswith('http'):
                return image_url
            elif image_url.startswith('/'):
                return f'https://www.bangerhead.no{image_url}'
            else:
                return f'https://www.bangerhead.no/{image_url}'

    return None


def extract_availability(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract availability.

    Primary: Microdata itemprop="availability"
    Fallback 1: Stock status div
    Confidence: 0.95
    """
    # Primary: Microdata itemprop="availability"
    meta = soup.find('meta', itemprop='availability')
    if meta:
        availability = meta.get('content')
        if availability:
            # Convert schema.org URL or value to readable status
            availability = str(availability).strip()
            if 'InStock' in availability:
                return "In Stock"
            elif 'OutOfStock' in availability:
                return "Out of Stock"
            elif 'PreOrder' in availability:
                return "Pre-Order"
            elif 'Discontinued' in availability:
                return "Discontinued"
            else:
                return BaseExtractor.clean_text(availability)

    # Fallback 1: Stock status div
    stock_div = soup.select_one('div.stock_status')
    if stock_div:
        stock_text = stock_div.get_text(strip=True)
        if stock_text:
            return BaseExtractor.clean_text(stock_text)

    # Fallback 2: Check for buy button presence (if button exists, likely in stock)
    buy_button = soup.find('button', class_=lambda x: x and 'buy' in str(x).lower())
    if buy_button and not buy_button.get('disabled'):
        return "In Stock"

    return None


def extract_article_number(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract article_number (SKU).

    Primary: data-product-id attribute
    Fallback 1: Extract from text (pattern: B + 6 digits)
    Confidence: 0.95
    """
    # Primary: data-product-id attribute
    elem = soup.find(attrs={'data-product-id': True})
    if elem:
        article_id = elem.get('data-product-id')
        if article_id:
            return str(article_id).strip()

    # Fallback 1: Find article number in text (pattern: B + 6 digits)
    text_with_artnr = soup.find(string=re.compile(r'B\d{6}'))
    if text_with_artnr:
        match = re.search(r'(B\d{6})', text_with_artnr)
        if match:
            return match.group(1).strip()

    # Fallback 2: Check for span.artnr
    artnr_span = soup.find('span', class_='artnr')
    if artnr_span:
        artnr = artnr_span.get_text(strip=True)
        if artnr:
            # Extract just the article number (remove "Artnr:" prefix if present)
            artnr = re.sub(r'Artnr:\s*', '', artnr, flags=re.IGNORECASE).strip()
            return artnr

    return None


def extract_model_number(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract model_number (manufacturer part number).

    Note: Bangerhead.no doesn't seem to consistently display manufacturer part numbers
    separate from their internal article numbers.
    Confidence: 0.70
    """
    # Check if there's any manufacturer info in specs/details
    # This site appears to use internal article numbers (B050452 format)
    # rather than manufacturer model numbers
    return None


def extract_currency(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract currency code.

    Primary: Microdata itemprop="priceCurrency"
    Fallback: Hardcoded default (NOK for Norwegian site)
    Confidence: 1.0
    """
    # Primary: Microdata itemprop="priceCurrency"
    meta = soup.find('meta', itemprop='priceCurrency')
    if meta:
        currency = meta.get('content')
        if currency:
            return str(currency).strip()

    # Fallback: Norwegian site default
    return "NOK"
