"""
Auto-generated extractor for www.aliexpress.com

Generated on 2024-12-26 based on product page analysis.
Extraction confidence: 0.85
"""
import re
from decimal import Decimal
from typing import Optional
from bs4 import BeautifulSoup
from ._base import BaseExtractor


# Metadata (required for discovery)
PATTERN_METADATA = {
    'domain': 'aliexpress.com',
    'generated_at': '2024-12-26T17:30:00',
    'generator': 'Pattern Generator Agent',
    'version': '1.0',
    'confidence': 0.85,
    'fields': ['price', 'title', 'image', 'availability', 'currency'],
    'notes': 'Uses CSS selectors with Open Graph meta tag fallbacks'
}


def extract_price(soup: BeautifulSoup) -> Optional[Decimal]:
    """
    Extract current price from AliExpress product page.
    
    Strategy:
    1. Try price display span: .price-default--current--*
    2. Fallback to og:price:amount meta tag
    
    Sample value: NOK260.09
    Confidence: 0.90
    """
    # Primary selector - current display price
    elem = soup.select_one('span[class*="price-default--current--"]')
    if elem:
        text = elem.get_text()
        # Remove currency code prefix if present (e.g., "NOK260.09")
        text = re.sub(r'^[A-Z]{3}\s*', '', text)
        return BaseExtractor.clean_price(text)
    
    # Fallback to Open Graph price meta tag
    meta = soup.select_one('meta[property="og:price:amount"]')
    if meta and meta.get('content'):
        return BaseExtractor.clean_price(meta['content'])
    
    # Fallback to data-price attribute
    elem_data = soup.select_one('[data-price]')
    if elem_data and elem_data.get('data-price'):
        return BaseExtractor.clean_price(elem_data['data-price'])
    
    return None


def extract_title(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract product title.
    
    Strategy:
    1. Try h1 with data-pl="product-title"
    2. Fallback to og:title meta tag
    3. Fallback to any h1 on the page
    
    Sample: "UGREEN 65W GaN Charger Quick Charge 4.0 3.0 Type C PD Fast Phone Charger USB Charger For Macbook Pro Laptop iPhone 17 15 15 Pro"
    Confidence: 0.95
    """
    # Primary selector - h1 with data attribute
    elem = soup.select_one('h1[data-pl="product-title"]')
    if elem:
        return BaseExtractor.clean_text(elem.get_text())
    
    # Fallback to Open Graph title
    meta = soup.select_one('meta[property="og:title"]')
    if meta and meta.get('content'):
        return BaseExtractor.clean_text(meta['content'])
    
    # Last fallback - any h1
    elem = soup.select_one('h1')
    if elem:
        return BaseExtractor.clean_text(elem.get_text())
    
    return None


def extract_image(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract primary product image URL.
    
    Strategy:
    1. Try og:image:secure_url meta tag (preferred - HTTPS)
    2. Fallback to og:image meta tag
    3. Fallback to main product image selector
    
    Sample: "https://ae-pic-a1.aliexpress-media.com/kf/S81584d9529a649faa86e3280dfd55b66h.jpg_960x960q75.jpg_.avif"
    Confidence: 0.95
    """
    # Primary - secure Open Graph image
    meta = soup.select_one('meta[property="og:image:secure_url"]')
    if meta and meta.get('content'):
        return meta['content']
    
    # Fallback to regular og:image
    meta = soup.select_one('meta[property="og:image"]')
    if meta and meta.get('content'):
        return meta['content']
    
    # Fallback to main product image
    img = soup.select_one('.magnifier--image--RM17RL2, .image-view-v2--previewBox img')
    if img and img.get('src'):
        return img['src']
    
    return None


def extract_availability(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract availability status.
    
    Strategy:
    1. Check if selected SKU has soldOut class
    2. Check for availability text/indicators
    3. Default to "In Stock" if product page loads successfully
    
    AliExpress shows sold out variants with class "sku-item--soldOut"
    The selected variant has class "sku-item--selected"
    
    Sample values: "In Stock", "Out of Stock"
    Confidence: 0.80
    """
    # Check if the currently selected SKU is sold out
    selected_sold_out = soup.select_one('.sku-item--selected.sku-item--soldOut')
    if selected_sold_out:
        return "Out of Stock"
    
    # Check for any availability indicators
    availability_text = soup.select_one('[class*="availability"], [data-availability]')
    if availability_text:
        text = BaseExtractor.clean_text(availability_text.get_text())
        if text:
            return text
    
    # If the product page loaded and no sold-out indicator, assume in stock
    # (AliExpress typically removes completely unavailable items)
    title_elem = soup.select_one('h1[data-pl="product-title"]')
    if title_elem:
        return "In Stock"
    
    return None


def extract_article_number(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract article/SKU number.
    
    AliExpress uses product IDs in the URL rather than visible SKUs.
    May be available in JSON data or meta tags.
    
    Confidence: 0.60
    """
    # Try to extract from URL pattern in canonical link
    canonical = soup.select_one('link[rel="canonical"]')
    if canonical and canonical.get('href'):
        url = canonical['href']
        # AliExpress URLs like: /item/1005003413514494.html
        match = re.search(r'/item/(\d+)\.html', url)
        if match:
            return match.group(1)
    
    # Try og:url as well
    meta = soup.select_one('meta[property="og:url"]')
    if meta and meta.get('content'):
        url = meta['content']
        match = re.search(r'/item/(\d+)\.html', url)
        if match:
            return match.group(1)
    
    return None


def extract_model_number(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract manufacturer model number.
    
    AliExpress doesn't consistently show manufacturer model numbers.
    This information is usually in the specifications section if available.
    
    Confidence: 0.50
    """
    # Look in specifications section
    specs = soup.select('.specification--desc--Dxx6W0W')
    for spec in specs:
        text = spec.get_text()
        # Look for patterns like model numbers (alphanumeric with dashes/dots)
        if re.match(r'^[A-Z0-9][A-Z0-9\-\.]{3,20}$', text):
            return text
    
    return None


def extract_currency(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract currency code.
    
    Strategy:
    1. Extract from price display text prefix
    2. Fallback to og:price:currency meta tag
    3. Default to common currency for region
    
    Sample: "NOK" (Norwegian Krone)
    Confidence: 0.90
    """
    # Try to extract from price text
    elem = soup.select_one('span[class*="price-default--current--"]')
    if elem:
        text = elem.get_text()
        match = re.match(r'^([A-Z]{3})\s*[\d\.,]+', text)
        if match:
            return match.group(1)
    
    # Fallback to Open Graph currency
    meta = soup.select_one('meta[property="og:price:currency"]')
    if meta and meta.get('content'):
        return meta['content']
    
    # If we can't determine, return None rather than guessing
    return None
