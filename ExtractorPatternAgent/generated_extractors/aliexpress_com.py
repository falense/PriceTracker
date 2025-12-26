"""
Extractor for aliexpress.com

Created on: 2025-12-26
Note: AliExpress has strong anti-bot protection. This extractor is designed for
      HTML obtained through authenticated sessions or manual browsing.
"""
import re
import json
from decimal import Decimal
from typing import Optional
from bs4 import BeautifulSoup
from ._base import BaseExtractor


# Metadata (required for discovery)
PATTERN_METADATA = {
    'domain': 'aliexpress.com',
    'created_at': '2025-12-26T12:48:00',
    'created_by': 'manual',
    'version': '1.0',
    'confidence': 0.85,
    'fields': ['price', 'title', 'image', 'availability', 'article_number', 'model_number', 'currency'],
    'notes': 'AliExpress pattern - requires authenticated/non-bot HTML. Site uses runParams JSON data.'
}


def extract_price(soup: BeautifulSoup) -> Optional[Decimal]:
    """
    Extract price from AliExpress product page.
    
    Primary: window.runParams JSON data
    Fallback 1: Meta tags (og:price)
    Fallback 2: Price display elements
    
    Confidence: 0.85
    """
    # Primary: Extract from window.runParams JavaScript object
    scripts = soup.find_all('script')
    for script in scripts:
        if script.string and 'window.runParams' in script.string:
            # Try to extract price from runParams JSON
            match = re.search(r'window\.runParams\s*=\s*({.+?});', script.string, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(1))
                    # Try different possible price locations in runParams
                    price_value = BaseExtractor.extract_json_field(data, 'data.priceModule.minActivityAmount.value')
                    if price_value:
                        return BaseExtractor.clean_price(str(price_value))
                    
                    price_value = BaseExtractor.extract_json_field(data, 'data.priceModule.minAmount.value')
                    if price_value:
                        return BaseExtractor.clean_price(str(price_value))
                    
                    # Try formatted price
                    price_value = BaseExtractor.extract_json_field(data, 'data.priceModule.formattedPrice')
                    if price_value:
                        return BaseExtractor.clean_price(str(price_value))
                except:
                    pass
    
    # Fallback 1: OpenGraph price meta tag
    elem = soup.select_one("meta[property='og:price:amount']")
    if elem:
        value = elem.get("content")
        if value:
            return BaseExtractor.clean_price(value)
    
    elem = soup.select_one("meta[property='product:price:amount']")
    if elem:
        value = elem.get("content")
        if value:
            return BaseExtractor.clean_price(value)
    
    # Fallback 2: Price display elements
    elem = soup.select_one(".product-price-value")
    if elem:
        return BaseExtractor.clean_price(elem.get_text(strip=True))
    
    elem = soup.select_one("[class*='price'] [class*='value']")
    if elem:
        return BaseExtractor.clean_price(elem.get_text(strip=True))
    
    return None


def extract_title(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract product title.
    
    Primary: window.runParams data
    Fallback 1: OpenGraph title
    Fallback 2: H1 or title tag
    
    Confidence: 0.90
    """
    # Primary: Extract from window.runParams
    scripts = soup.find_all('script')
    for script in scripts:
        if script.string and 'window.runParams' in script.string:
            match = re.search(r'window\.runParams\s*=\s*({.+?});', script.string, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(1))
                    title = BaseExtractor.extract_json_field(data, 'data.titleModule.subject')
                    if title:
                        return BaseExtractor.clean_text(str(title))
                    
                    title = BaseExtractor.extract_json_field(data, 'data.pageModule.title')
                    if title:
                        return BaseExtractor.clean_text(str(title))
                except:
                    pass
    
    # Fallback 1: OpenGraph title
    elem = soup.select_one("meta[property='og:title']")
    if elem:
        value = elem.get("content")
        if value:
            return BaseExtractor.clean_text(value)
    
    # Fallback 2: H1 heading
    elem = soup.select_one("h1")
    if elem:
        return BaseExtractor.clean_text(elem.get_text())
    
    # Fallback 3: Page title
    elem = soup.select_one("title")
    if elem:
        title = BaseExtractor.clean_text(elem.get_text())
        # Remove common suffixes
        if title and ' - AliExpress' in title:
            title = title.split(' - AliExpress')[0].strip()
        return title
    
    return None


def extract_image(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract primary product image URL.
    
    Primary: window.runParams image data
    Fallback 1: OpenGraph image
    Fallback 2: Main product image element
    
    Confidence: 0.85
    """
    # Primary: Extract from window.runParams
    scripts = soup.find_all('script')
    for script in scripts:
        if script.string and 'window.runParams' in script.string:
            match = re.search(r'window\.runParams\s*=\s*({.+?});', script.string, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(1))
                    # Try to get first image from imageModule
                    image_list = BaseExtractor.extract_json_field(data, 'data.imageModule.imagePathList')
                    if image_list and isinstance(image_list, list) and len(image_list) > 0:
                        image_url = str(image_list[0])
                        # Add protocol if missing
                        if image_url.startswith('//'):
                            image_url = 'https:' + image_url
                        if image_url.startswith('http'):
                            return image_url
                except:
                    pass
    
    # Fallback 1: OpenGraph image
    elem = soup.select_one("meta[property='og:image']")
    if elem:
        value = elem.get("content")
        if value:
            value = str(value).strip()
            if value.startswith('//'):
                value = 'https:' + value
            if value.startswith('http'):
                return value
    
    # Fallback 2: Main product image
    elem = soup.select_one(".magnifier-image img")
    if elem:
        value = elem.get("src") or elem.get("data-src")
        if value:
            value = str(value).strip()
            if value.startswith('//'):
                value = 'https:' + value
            if value.startswith('http'):
                return value
    
    return None


def extract_availability(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract stock availability status.
    
    Primary: window.runParams stock data
    Fallback: Availability indicators on page
    
    Confidence: 0.80
    """
    # Primary: Extract from window.runParams
    scripts = soup.find_all('script')
    for script in scripts:
        if script.string and 'window.runParams' in script.string:
            match = re.search(r'window\.runParams\s*=\s*({.+?});', script.string, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(1))
                    # Check totalAvailQuantity
                    quantity = BaseExtractor.extract_json_field(data, 'data.quantityModule.totalAvailQuantity')
                    if quantity is not None:
                        quantity = int(quantity)
                        if quantity > 0:
                            # Return stock level indicator
                            if quantity >= 1000:
                                return "In Stock"
                            else:
                                return f"{quantity}+"
                        else:
                            return "Out of Stock"
                except:
                    pass
    
    # Fallback 1: Check for availability elements
    elem = soup.select_one("[class*='stock']")
    if elem:
        text = BaseExtractor.clean_text(elem.get_text())
        if text:
            # Normalize stock status
            if re.search(r'in stock|available|pieces available', text, re.IGNORECASE):
                # Try to extract quantity
                match = re.search(r'(\d+)\s*(?:pieces|pcs|items)?', text, re.IGNORECASE)
                if match:
                    return f"{match.group(1)}+"
                return "In Stock"
            if re.search(r'out of stock|unavailable|sold out', text, re.IGNORECASE):
                return "Out of Stock"
    
    # Default: Assume in stock (AliExpress typically shows products that are available)
    return "In Stock"


def extract_article_number(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract store article number (product ID).
    
    Primary: window.runParams productId
    Fallback 1: URL extraction
    Fallback 2: Meta tags
    
    Confidence: 0.90
    """
    # Primary: Extract from window.runParams
    scripts = soup.find_all('script')
    for script in scripts:
        if script.string and 'window.runParams' in script.string:
            match = re.search(r'window\.runParams\s*=\s*({.+?});', script.string, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(1))
                    product_id = BaseExtractor.extract_json_field(data, 'data.productId')
                    if product_id:
                        return str(product_id).strip()
                    
                    # Try alternative field
                    product_id = BaseExtractor.extract_json_field(data, 'data.actionModule.productId')
                    if product_id:
                        return str(product_id).strip()
                except:
                    pass
    
    # Fallback 1: Extract from canonical URL
    elem = soup.select_one('link[rel="canonical"]')
    if elem:
        url = elem.get('href', '')
        if url:
            # AliExpress URLs: /item/1005003413514494.html
            match = re.search(r'/item/(\d+)', url)
            if match:
                return match.group(1).strip()
    
    # Fallback 2: Extract from current page URL (check meta)
    elem = soup.select_one("meta[property='og:url']")
    if elem:
        url = elem.get("content", "")
        if url:
            match = re.search(r'/item/(\d+)', url)
            if match:
                return match.group(1).strip()
    
    return None


def extract_model_number(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract manufacturer model/part number.
    
    Primary: Product specifications in runParams or page
    Fallback: Specification table
    
    Confidence: 0.70
    """
    # Primary: Extract from window.runParams specs
    scripts = soup.find_all('script')
    for script in scripts:
        if script.string and 'window.runParams' in script.string:
            match = re.search(r'window\.runParams\s*=\s*({.+?});', script.string, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(1))
                    # Try to find model number in specifications
                    specs = BaseExtractor.extract_json_field(data, 'data.specsModule.props')
                    if specs and isinstance(specs, list):
                        for spec in specs:
                            if isinstance(spec, dict):
                                key = spec.get('attrName', '').lower()
                                if 'model' in key or 'part number' in key or 'mpn' in key:
                                    value = spec.get('attrValue')
                                    if value:
                                        return BaseExtractor.clean_text(str(value))
                except:
                    pass
    
    # Fallback: Look for specification table
    # AliExpress often has specs in various formats
    spec_elements = soup.select("[class*='specification'], [class*='property']")
    for elem in spec_elements:
        text = elem.get_text()
        if text and ('model' in text.lower() or 'part number' in text.lower()):
            # Try to extract value after the label
            match = re.search(r'(?:model|part\s*number|mpn)\s*:?\s*([A-Z0-9\-]+)', text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
    
    return None


def extract_currency(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract currency code.
    
    Primary: window.runParams currency
    Fallback 1: Meta tags
    Fallback 2: Default to USD
    
    Confidence: 0.90
    """
    # Primary: Extract from window.runParams
    scripts = soup.find_all('script')
    for script in scripts:
        if script.string and 'window.runParams' in script.string:
            match = re.search(r'window\.runParams\s*=\s*({.+?});', script.string, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(1))
                    currency = BaseExtractor.extract_json_field(data, 'data.priceModule.minActivityAmount.currency')
                    if currency:
                        return str(currency).strip().upper()
                    
                    currency = BaseExtractor.extract_json_field(data, 'data.priceModule.minAmount.currency')
                    if currency:
                        return str(currency).strip().upper()
                except:
                    pass
    
    # Fallback 1: Meta tag
    elem = soup.select_one("meta[property='og:price:currency']")
    if elem:
        value = elem.get("content")
        if value:
            return str(value).strip().upper()
    
    elem = soup.select_one("meta[property='product:price:currency']")
    if elem:
        value = elem.get("content")
        if value:
            return str(value).strip().upper()
    
    # Fallback 2: Default to USD (most common on AliExpress international)
    return "USD"
