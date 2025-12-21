"""
Auto-generated extractor for komplett.no

Converted from JSON pattern on 2025-12-17T16:02:31.859473
Original confidence: 0.92
"""
import re
from decimal import Decimal
from typing import Optional
from bs4 import BeautifulSoup
from ._base import BaseExtractor


# Metadata (required for discovery)
PATTERN_METADATA = {
    'domain': 'komplett.no',
    'generated_at': '2025-12-17T16:02:31.859494',
    'generator': 'JSON to Python converter',
    'version': '1.1',
    'confidence': 0.92,
    'fields': ['price', 'title', 'availability', 'image', 'article_number', 'model_number', 'currency'],
    'notes': 'Converted from JSON pattern, enhanced with article_number and model_number extraction'
}


def extract_price(soup: BeautifulSoup) -> Optional[Decimal]:
    """
    Extract price.

    Primary: Primary price in data attribute
    Confidence: 0.95
    """
    # Primary selector
    elem = soup.select_one("#cash-price-container")
    if elem:
        value = elem.get("data-price")
        if value:
            return BaseExtractor.clean_price(value)
        # Fallback to text content
        return BaseExtractor.clean_price(elem.get_text(strip=True))

    # Fallback 1: Price from JSON in data-initobject attribute
    elem = soup.select_one(".buy-button")
    if elem and elem.get("data-initobject"):
        try:
            import json
            from html import unescape
            data_str = unescape(elem.get("data-initobject"))
            data = json.loads(data_str)
            value = BaseExtractor.extract_json_field(data, "price")
            if value:
                return BaseExtractor.clean_price(str(value))
        except:
            pass

    # Fallback 2: Displayed price text
    elem = soup.select_one(".product-price-now")
    if elem:
        return BaseExtractor.clean_price(elem.get_text(strip=True))

    return None


def extract_title(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract title.

    Primary: Open Graph title meta tag
    Confidence: 0.95
    """
    # Primary selector
    elem = soup.select_one("meta[property='og:title']")
    if elem:
        value = elem.get("content")
        if value:
            value = BaseExtractor.clean_text(value)
            # Remove category suffix (e.g., " - USB-kabler")
            if value and ' - ' in value:
                value = value.rsplit(' - ', 1)[0].strip()
            return value if value else None

    # Fallback 1: Product title heading
    elem = soup.select_one("h1.product-main-info__title")
    if elem:
        value = BaseExtractor.clean_text(elem.get_text())
        if value and ' - ' in value:
            value = value.rsplit(' - ', 1)[0].strip()
        return value if value else None

    # Fallback 2: Title from buy button JSON data
    elem = soup.select_one(".buy-button")
    if elem and elem.get("data-initobject"):
        try:
            import json
            from html import unescape
            data_str = unescape(elem.get("data-initobject"))
            data = json.loads(data_str)
            value = BaseExtractor.extract_json_field(data, "webtext1")
            if value:
                value = BaseExtractor.clean_text(str(value))
                if value and ' - ' in value:
                    value = value.rsplit(' - ', 1)[0].strip()
                return value if value else None
        except:
            pass

    return None


def extract_image(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract image.

    Primary: Secure product image from Open Graph
    Confidence: 0.95
    """
    # Primary selector
    elem = soup.select_one("meta[property='og:image:secure_url']")
    if elem:
        value = elem.get("content")
        if value:
            value = str(value).strip()
            if value.startswith('http'):
                return value

    # Fallback 1: Product image from Open Graph
    elem = soup.select_one("meta[property='og:image']")
    if elem:
        value = elem.get("content")
        if value:
            value = str(value).strip()
            if value.startswith('http'):
                return value

    # Fallback 2: Main product image element
    elem = soup.select_one(".product-main-image img")
    if elem:
        value = elem.get("src")
        if value:
            value = str(value).strip()
            if value.startswith('http'):
                return value

    return None


def extract_availability(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract availability.

    Primary: Stock status icon title attribute
    Confidence: 0.90
    """
    import re
    
    # Primary selector
    elem = soup.select_one(".stockstatus-instock")
    if elem:
        value = elem.get("title")
        if value:
            value = BaseExtractor.clean_text(value)
            # Remove "Tilgjengelighet: " prefix
            if value:
                value = re.sub(r'^Tilgjengelighet:\s*', '', value, flags=re.IGNORECASE).strip()
            # Extract numeric quantity (e.g., "50+ stk. på lager." -> "50+")
            if value:
                match = re.search(r'(\d+\+?|\>\d+)', value)
                if match:
                    return match.group(1)
                # Check for keywords
                if re.search(r'på lager|in stock|stocked', value, re.IGNORECASE):
                    return "In Stock"
                if re.search(r'ikke på lager|out of stock', value, re.IGNORECASE):
                    return "Out of Stock"
            return value if value else None

    # Fallback 1: Stock status text
    elem = soup.select_one(".stockstatus-stock-details")
    if elem:
        value = BaseExtractor.clean_text(elem.get_text())
        if value:
            value = re.sub(r'^Tilgjengelighet:\s*', '', value, flags=re.IGNORECASE).strip()
            # Extract numeric quantity
            match = re.search(r'(\d+\+?|\>\d+)', value)
            if match:
                return match.group(1)
        return value if value else None

    # Fallback 2: Stock status from JSON data (values: Stocked, OutOfStock)
    elem = soup.select_one(".buy-button")
    if elem and elem.get("data-initobject"):
        try:
            import json
            from html import unescape
            data_str = unescape(elem.get("data-initobject"))
            data = json.loads(data_str)
            value = BaseExtractor.extract_json_field(data, "item_stock_status")
            if value:
                value = str(value).strip()
                if value == "Stocked":
                    return "In Stock"
                elif value == "OutOfStock":
                    return "Out of Stock"
                return BaseExtractor.clean_text(value)
        except:
            pass

    return None


def extract_article_number(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract article_number (product ID/SKU).
    
    Primary: Extract from dataLayer.ecomm_prodid or item_id
    Confidence: 0.95
    """
    import re
    
    # Look for dataLayer.push with productId
    scripts = soup.find_all('script')
    for script in scripts:
        if script.string and 'dataLayer.push' in script.string:
            # Extract the productId field
            match = re.search(r'"productId"\s*:\s*"([^"]+)"', script.string)
            if match:
                return match.group(1).strip()
            # Also try ecomm_prodid
            match = re.search(r'"ecomm_prodid"\s*:\s*"([^"]+)"', script.string)
            if match:
                return match.group(1).strip()
            # Also try item_id from ecommerce object
            match = re.search(r'"item_id"\s*:\s*"([^"]+)"', script.string)
            if match:
                return match.group(1).strip()
    
    # Fallback: extract from URL (product ID is in the URL)
    canonical = soup.select_one('link[rel="canonical"]')
    if canonical:
        url = canonical.get('href', '')
        if url:
            match = re.search(r'/product/(\d+)/', url)
            if match:
                return match.group(1).strip()
    
    return None


def extract_model_number(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract model_number (manufacturer part number).
    
    Primary: Extract from dataLayer.item_manufacturer_number
    Confidence: 0.90
    """
    import re
    
    # Look for item_manufacturer_number in dataLayer
    scripts = soup.find_all('script')
    for script in scripts:
        if script.string and 'dataLayer.push' in script.string:
            # Extract the item_manufacturer_number field
            match = re.search(r'"item_manufacturer_number"\s*:\s*"([^"]+)"', script.string)
            if match:
                value = match.group(1).strip()
                if value:
                    return value
    
    return None

def extract_currency(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract currency code.
    
    Returns:
        Currency code (e.g., 'NOK', 'USD', 'EUR')
    
    Confidence: 1.0 (hardcoded default)
    """
    return "NOK"

