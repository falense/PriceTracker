"""
Auto-generated extractor for netonnet.no

Converted from JSON pattern on 2025-12-17T16:02:31.859976
Original confidence: 0.00
Updated: 2025-12-17 - Improved extraction using JSON-LD structured data
"""
import re
import json
from decimal import Decimal
from typing import Optional
from bs4 import BeautifulSoup
from ._base import BaseExtractor


# Metadata (required for discovery)
PATTERN_METADATA = {
    'domain': 'netonnet.no',
    'generated_at': '2025-12-17T16:02:31.859979',
    'generator': 'JSON to Python converter',
    'version': '1.1',
    'confidence': 0.90,
    'fields': ['price', 'title', 'image', 'availability', 'article_number', 'model_number'],
    'notes': 'Updated to use JSON-LD structured data for better reliability'
}


def extract_price(soup: BeautifulSoup) -> Optional[Decimal]:
    """
    Extract price.

    Primary: JSON-LD structured data
    Fallback: CSS selectors
    Confidence: 0.95
    """
    # PRIMARY: JSON-LD structured data
    scripts = soup.find_all('script', type='application/ld+json')
    for script in scripts:
        if script.string and 'Product' in script.string:
            try:
                data = json.loads(script.string)
                if data.get('@type') == 'Product' and 'offers' in data:
                    price_str = data['offers'].get('price')
                    if price_str:
                        return BaseExtractor.clean_price(price_str)
            except (json.JSONDecodeError, KeyError):
                pass
    
    # FALLBACK 1: Price element with name attribute
    elem = soup.select_one('[name$="-price"]')
    if elem:
        text = elem.get_text(strip=True)
        if text:
            return BaseExtractor.clean_price(text)
    
    # FALLBACK 2: Generic price selector
    elem = soup.select_one(".font-bold.text-h1.text-text-price")
    if elem:
        return BaseExtractor.clean_price(elem.get_text(strip=True))

    return None


def extract_title(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract title.

    Primary: meta[property="og:title"]
    Confidence: 0.95
    """
    # Primary selector
    elem = soup.select_one("meta[property=\"og:title\"]")
    if elem:
        value = elem.get("content")
        if value:
            return value

    # Fallback 1: h1
    elem = soup.select_one("h1")
    if elem:
        return BaseExtractor.clean_text(elem.get_text())

    return None


def extract_image(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract image.

    Primary: meta[property="og:image:secure_url"]
    Confidence: 0.95
    """
    # Primary selector
    elem = soup.select_one("meta[property=\"og:image:secure_url\"]")
    if elem:
        value = elem.get("content")
        if value:
            return value

    # Fallback 1: meta[property="og:image"]
    elem = soup.select_one("meta[property=\"og:image\"]")
    if elem:
        value = elem.get("content")
        if value:
            return value

    return None


def extract_availability(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract availability (stock status).
    
    Primary: JSON-LD structured data
    Fallback: Stock status text
    Confidence: 0.85
    """
    # PRIMARY: JSON-LD structured data
    scripts = soup.find_all('script', type='application/ld+json')
    for script in scripts:
        if script.string and 'Product' in script.string:
            try:
                data = json.loads(script.string)
                if data.get('@type') == 'Product' and 'offers' in data:
                    availability = data['offers'].get('availability')
                    if availability:
                        # Normalize Schema.org values
                        if 'InStock' in availability:
                            return "In Stock"
                        elif 'OutOfStock' in availability:
                            return "Out of Stock"
                        elif 'BackOrder' in availability:
                            return "Back Order"
                        return availability.split('/')[-1]  # Get last part of URL
            except (json.JSONDecodeError, KeyError):
                pass
    
    # FALLBACK: Text-based stock status
    elem = soup.select_one(".text-error-dark, .text-info-dark")
    if elem:
        text = BaseExtractor.clean_text(elem.get_text())
        if text:
            # Normalize Norwegian text
            if re.search(r'ikke på lager|out of stock', text, re.IGNORECASE):
                return "Out of Stock"
            elif re.search(r'på lager|in stock', text, re.IGNORECASE):
                # Try to extract quantity if present
                match = re.search(r'(\d+)\s*(?:stk|på lager)', text, re.IGNORECASE)
                if match:
                    return f"{match.group(1)}"
                return "In Stock"
            return text
    
    return None


def extract_article_number(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract article_number (SKU).
    
    Primary: JSON-LD structured data
    Fallback: Article number text
    Confidence: 0.95
    """
    # PRIMARY: JSON-LD structured data
    scripts = soup.find_all('script', type='application/ld+json')
    for script in scripts:
        if script.string and 'Product' in script.string:
            try:
                data = json.loads(script.string)
                if data.get('@type') == 'Product':
                    sku = data.get('sku')
                    if sku:
                        return str(sku).strip()
            except (json.JSONDecodeError, KeyError):
                pass
    
    # FALLBACK: Article number from page text
    elem = soup.find(id='product-subheader-articleNumber')
    if elem:
        text = elem.get_text(strip=True)
        # Extract number from "Art.nr: 1027759"
        match = re.search(r'Art\.nr:\s*(\S+)', text)
        if match:
            return match.group(1).strip()
        # If no match, try to extract any number
        match = re.search(r'\d+', text)
        if match:
            return match.group(0).strip()
    
    return None


def extract_model_number(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract model_number (manufacturer part number).
    
    Primary: JSON-LD structured data
    Confidence: 0.95
    """
    # PRIMARY: JSON-LD structured data
    scripts = soup.find_all('script', type='application/ld+json')
    for script in scripts:
        if script.string and 'Product' in script.string:
            try:
                data = json.loads(script.string)
                if data.get('@type') == 'Product':
                    # Try mpn (manufacturer part number) first
                    mpn = data.get('mpn')
                    if mpn:
                        return str(mpn).strip()
                    # Try identifier as fallback
                    identifier = data.get('identifier')
                    if identifier:
                        return str(identifier).strip()
            except (json.JSONDecodeError, KeyError):
                pass
    
    return None


