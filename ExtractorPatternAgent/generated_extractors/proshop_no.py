"""
Auto-generated extractor for www.proshop.no

Generated on 2025-12-22
Strategy: JSON-LD structured data + meta tags fallback
"""
import json
from decimal import Decimal
from typing import Optional
from bs4 import BeautifulSoup
from ._base import BaseExtractor


# Metadata (required for discovery)
PATTERN_METADATA = {
    'domain': 'proshop.no',
    'generated_at': '2025-12-22T21:03:19',
    'generator': 'Manual extraction pattern creation',
    'version': '1.0',
    'confidence': 0.95,
    'fields': ['price', 'title', 'image', 'availability', 'article_number', 'model_number', 'currency'],
    'notes': 'Uses JSON-LD structured data as primary source with meta tag fallbacks'
}


def _extract_json_ld(soup: BeautifulSoup) -> Optional[dict]:
    """
    Extract and parse JSON-LD structured data.
    
    Returns:
        Parsed JSON-LD data or None
    """
    script = soup.select_one('script[type="application/ld+json"]')
    if not script or not script.string:
        return None
    
    try:
        # Clean up the JSON string
        json_str = script.string.strip()
        data = json.loads(json_str)
        return data if isinstance(data, dict) else None
    except (json.JSONDecodeError, ValueError):
        return None


def extract_price(soup: BeautifulSoup) -> Optional[Decimal]:
    """
    Extract price.
    
    Primary: JSON-LD offers.price
    Fallback: CSS selector .site-currency-attention
    Confidence: 0.95
    """
    # Primary: JSON-LD structured data
    json_ld = _extract_json_ld(soup)
    if json_ld:
        offers = json_ld.get('offers', {})
        price_value = offers.get('price')
        if price_value:
            return BaseExtractor.clean_price(str(price_value))
    
    # Fallback 1: Price display element
    elem = soup.select_one('.site-currency-attention')
    if elem:
        return BaseExtractor.clean_price(elem.get_text())
    
    # Fallback 2: Price from meta description
    meta = soup.select_one('meta[name="description"]')
    if meta:
        content = meta.get('content', '')
        if 'kr' in content:
            # Extract first price-like pattern
            import re
            match = re.search(r'([\d\s.,]+)\s*kr', content)
            if match:
                return BaseExtractor.clean_price(match.group(1))
    
    return None


def extract_title(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract title.
    
    Primary: JSON-LD name
    Fallback: Open Graph title
    Confidence: 0.95
    """
    # Primary: JSON-LD structured data
    json_ld = _extract_json_ld(soup)
    if json_ld:
        name = json_ld.get('name')
        if name:
            return BaseExtractor.clean_text(str(name))
    
    # Fallback 1: Open Graph title (without availability suffix)
    elem = soup.select_one('meta[property="og:title"]')
    if elem:
        title = elem.get('content')
        if title:
            title = BaseExtractor.clean_text(title)
            # Remove " | På lager" or similar suffixes
            if title and ' | ' in title:
                title = title.split(' | ')[0].strip()
            return title if title else None
    
    # Fallback 2: Page title
    title_tag = soup.find('title')
    if title_tag:
        title = BaseExtractor.clean_text(title_tag.get_text())
        if title and ' | ' in title:
            title = title.split(' | ')[0].strip()
        return title if title else None
    
    return None


def extract_image(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract image.
    
    Primary: JSON-LD image
    Fallback: Open Graph image
    Confidence: 0.95
    """
    # Primary: JSON-LD structured data
    json_ld = _extract_json_ld(soup)
    if json_ld:
        image_url = json_ld.get('image')
        if image_url:
            image_url = str(image_url).strip()
            # Fix relative URLs or malformed URLs
            if image_url.startswith('https://') or image_url.startswith('http://'):
                # Properly formed URL, return as-is
                return image_url
            elif image_url.startswith('https:/') and not image_url.startswith('https://'):
                # Handle malformed URL like "https:/Images/..." (missing one slash)
                image_url = 'https://www.proshop.no/' + image_url[7:]
                return image_url
            elif image_url.startswith('/'):
                # Relative URL starting with /
                image_url = 'https://www.proshop.no' + image_url
                return image_url
            elif image_url.startswith('Images/'):
                # Relative URL without leading /
                image_url = 'https://www.proshop.no/' + image_url
                return image_url
            else:
                # Other cases - prepend https://
                image_url = 'https://' + image_url
                return image_url if '.' in image_url else None
    
    # Fallback 1: Open Graph image
    elem = soup.select_one('meta[property="og:image"]')
    if elem:
        image_url = elem.get('content')
        if image_url:
            image_url = str(image_url).strip()
            # Fix relative URLs
            if image_url.startswith('/'):
                image_url = 'https://www.proshop.no' + image_url
            return image_url if image_url.startswith('http') else None
    
    return None


def extract_availability(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract availability.
    
    Primary: JSON-LD offers.availability
    Fallback: Page title
    Confidence: 0.90
    """
    # Primary: JSON-LD structured data
    json_ld = _extract_json_ld(soup)
    if json_ld:
        offers = json_ld.get('offers', {})
        availability_url = offers.get('availability')
        if availability_url:
            # Convert schema.org URL to readable status
            if 'InStock' in availability_url:
                return 'In Stock'
            elif 'OutOfStock' in availability_url:
                return 'Out of Stock'
            elif 'PreOrder' in availability_url:
                return 'Pre-Order'
            elif 'LimitedAvailability' in availability_url:
                return 'Limited Availability'
    
    # Fallback 1: Check title for availability
    elem = soup.select_one('meta[property="og:title"]')
    if elem:
        title = elem.get('content', '')
        if 'På lager' in title:
            return 'In Stock'
        elif 'Ikke på lager' in title or 'Utsolgt' in title:
            return 'Out of Stock'
    
    # Fallback 2: Look for stock indicator elements
    title_tag = soup.find('title')
    if title_tag:
        title_text = title_tag.get_text()
        if 'På lager' in title_text:
            return 'In Stock'
        elif 'Ikke på lager' in title_text or 'Utsolgt' in title_text:
            return 'Out of Stock'
    
    return None


def extract_article_number(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract article_number (SKU).
    
    Primary: JSON-LD sku
    Fallback: CSS selector for Varenummer
    Confidence: 0.95
    """
    # Primary: JSON-LD structured data
    json_ld = _extract_json_ld(soup)
    if json_ld:
        sku = json_ld.get('sku')
        if sku:
            return str(sku).strip()
    
    # Fallback 1: Look for Varenummer in spec list
    spec_titles = soup.find_all(class_='specItemTitle')
    for spec_title in spec_titles:
        if 'Varenummer' in spec_title.get_text():
            # Get the next div sibling
            value_div = spec_title.find_next_sibling('div')
            if value_div:
                value = BaseExtractor.clean_text(value_div.get_text())
                if value:
                    return value
    
    # Fallback 2: Extract from small tag with "Varenummer:"
    import re
    small_tags = soup.find_all('small')
    for small_tag in small_tags:
        text = small_tag.get_text()
        if 'Varenummer:' in text:
            match = re.search(r'Varenummer:\s*(\d+)', text)
            if match:
                return match.group(1)
    
    return None


def extract_model_number(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract model_number (manufacturer part number).
    
    Primary: JSON-LD mpn
    Confidence: 0.95
    """
    # Primary: JSON-LD structured data
    json_ld = _extract_json_ld(soup)
    if json_ld:
        mpn = json_ld.get('mpn')
        if mpn:
            return str(mpn).strip()
    
    return None


def extract_currency(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract currency code.
    
    Primary: JSON-LD offers.priceCurrency
    Confidence: 1.0
    """
    # Primary: JSON-LD structured data
    json_ld = _extract_json_ld(soup)
    if json_ld:
        offers = json_ld.get('offers', {})
        currency = offers.get('priceCurrency')
        if currency:
            return str(currency).strip()
    
    # Fallback: Default to NOK for proshop.no
    return 'NOK'
