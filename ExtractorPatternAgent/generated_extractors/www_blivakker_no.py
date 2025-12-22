"""
Auto-generated extractor for www.blivakker.no

Generated: 2025-12-22
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
    'domain': 'blivakker.no',
    'generated_at': '2025-12-22T21:29:00',
    'generator': 'Manual extractor creation',
    'version': '1.0',
    'confidence': 0.95,
    'fields': ['price', 'title', 'image', 'availability', 'article_number', 'currency'],
    'notes': 'Uses JSON-LD structured data for reliable extraction. Norwegian beauty e-commerce site.'
}


def extract_price(soup: BeautifulSoup) -> Optional[Decimal]:
    """
    Extract price.

    Primary: JSON-LD structured data (schema.org Product)
    Fallback 1: dataLayer productDetail.price
    Fallback 2: Meta tag og:price:amount
    Confidence: 0.95
    """
    # Primary: JSON-LD structured data
    json_ld_script = soup.find('script', type='application/ld+json')
    if json_ld_script and json_ld_script.string:
        try:
            data = json.loads(json_ld_script.string)
            if isinstance(data, dict) and data.get('@type') == 'Product':
                offers = data.get('offers', {})
                if isinstance(offers, dict):
                    price_value = offers.get('price')
                    if price_value:
                        return BaseExtractor.clean_price(str(price_value))
        except (json.JSONDecodeError, ValueError):
            pass

    # Fallback 1: dataLayer in script
    scripts = soup.find_all('script')
    for script in scripts:
        if script.string and 'dataLayer.push' in script.string and 'productDetail.price' in script.string:
            # Extract price from dataLayer
            match = re.search(r'"productDetail\.price"\s*:\s*"([^"]+)"', script.string)
            if match:
                price_text = match.group(1)
                return BaseExtractor.clean_price(price_text)
            
            # Also try productDetail.amount
            match = re.search(r'"productDetail\.amount"\s*:\s*"([^"]+)"', script.string)
            if match:
                price_text = match.group(1)
                return BaseExtractor.clean_price(price_text)

    # Fallback 2: Meta tag
    meta = soup.find('meta', property='og:price:amount')
    if meta:
        price_value = meta.get('content')
        if price_value:
            return BaseExtractor.clean_price(price_value)

    return None


def extract_title(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract title.

    Primary: JSON-LD structured data name
    Fallback 1: Open Graph title meta tag
    Fallback 2: dataLayer productDetail.name
    Confidence: 0.95
    """
    # Primary: JSON-LD structured data
    json_ld_script = soup.find('script', type='application/ld+json')
    if json_ld_script and json_ld_script.string:
        try:
            data = json.loads(json_ld_script.string)
            if isinstance(data, dict) and data.get('@type') == 'Product':
                name = data.get('name')
                if name:
                    return BaseExtractor.clean_text(name)
        except (json.JSONDecodeError, ValueError):
            pass

    # Fallback 1: Open Graph title
    meta = soup.find('meta', property='og:title')
    if meta:
        title = meta.get('content')
        if title:
            # Clean up the title (remove site suffix)
            title = BaseExtractor.clean_text(title)
            if title and ' | ' in title:
                # Remove " | Norges største skjønnhetsbutikk på nett" suffix
                title = title.split(' | ')[0].strip()
            return title if title else None

    # Fallback 2: dataLayer
    scripts = soup.find_all('script')
    for script in scripts:
        if script.string and 'dataLayer.push' in script.string and 'productDetail.name' in script.string:
            match = re.search(r'"productDetail\.name"\s*:\s*"([^"]+)"', script.string)
            if match:
                return BaseExtractor.clean_text(match.group(1))

    return None


def extract_image(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract image.

    Primary: JSON-LD structured data image
    Fallback 1: Open Graph image meta tag
    Fallback 2: dataLayer productDetail.photoUrl
    Confidence: 0.95
    """
    # Primary: JSON-LD structured data
    json_ld_script = soup.find('script', type='application/ld+json')
    if json_ld_script and json_ld_script.string:
        try:
            data = json.loads(json_ld_script.string)
            if isinstance(data, dict) and data.get('@type') == 'Product':
                image = data.get('image')
                if image:
                    image_url = str(image).strip()
                    if image_url.startswith('http'):
                        return image_url
        except (json.JSONDecodeError, ValueError):
            pass

    # Fallback 1: Open Graph image
    meta = soup.find('meta', property='og:image')
    if meta:
        image_url = meta.get('content')
        if image_url:
            image_url = str(image_url).strip()
            if image_url.startswith('http'):
                return image_url

    # Fallback 2: dataLayer
    scripts = soup.find_all('script')
    for script in scripts:
        if script.string and 'dataLayer.push' in script.string and 'productDetail.photoUrl' in script.string:
            match = re.search(r'"productDetail\.photoUrl"\s*:\s*"([^"]+)"', script.string)
            if match:
                image_url = match.group(1).strip()
                if image_url.startswith('http'):
                    return image_url

    return None


def extract_availability(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract availability.

    Primary: JSON-LD structured data availability
    Fallback 1: dataLayer productDetail.inStock
    Confidence: 0.90
    """
    # Primary: JSON-LD structured data
    json_ld_script = soup.find('script', type='application/ld+json')
    if json_ld_script and json_ld_script.string:
        try:
            data = json.loads(json_ld_script.string)
            if isinstance(data, dict) and data.get('@type') == 'Product':
                offers = data.get('offers', {})
                if isinstance(offers, dict):
                    availability = offers.get('availability')
                    if availability:
                        # Convert schema.org URL to readable status
                        if 'InStock' in str(availability):
                            return "In Stock"
                        elif 'OutOfStock' in str(availability):
                            return "Out of Stock"
                        elif 'PreOrder' in str(availability):
                            return "Pre-Order"
                        elif 'Discontinued' in str(availability):
                            return "Discontinued"
                        else:
                            return BaseExtractor.clean_text(str(availability))
        except (json.JSONDecodeError, ValueError):
            pass

    # Fallback 1: dataLayer inStock field
    scripts = soup.find_all('script')
    for script in scripts:
        if script.string and 'dataLayer.push' in script.string and 'productDetail.inStock' in script.string:
            match = re.search(r'"productDetail\.inStock"\s*:\s*"([^"]+)"', script.string)
            if match:
                in_stock = match.group(1).lower()
                if in_stock == 'true':
                    return "In Stock"
                elif in_stock == 'false':
                    return "Out of Stock"

    return None


def extract_article_number(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract article_number (SKU).

    Primary: JSON-LD structured data sku
    Fallback 1: dataLayer productDetail.id
    Confidence: 0.95
    """
    # Primary: JSON-LD structured data
    json_ld_script = soup.find('script', type='application/ld+json')
    if json_ld_script and json_ld_script.string:
        try:
            data = json.loads(json_ld_script.string)
            if isinstance(data, dict) and data.get('@type') == 'Product':
                sku = data.get('sku')
                if sku:
                    return str(sku).strip()
        except (json.JSONDecodeError, ValueError):
            pass

    # Fallback 1: dataLayer productDetail.id
    scripts = soup.find_all('script')
    for script in scripts:
        if script.string and 'dataLayer.push' in script.string and 'productDetail.id' in script.string:
            match = re.search(r'"productDetail\.id"\s*:\s*"([^"]+)"', script.string)
            if match:
                return match.group(1).strip()

    return None


def extract_model_number(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract model_number (manufacturer part number).

    Primary: JSON-LD structured data gtin13 (barcode can serve as model reference)
    Confidence: 0.80
    """
    # Primary: JSON-LD gtin13 (EAN barcode)
    json_ld_script = soup.find('script', type='application/ld+json')
    if json_ld_script and json_ld_script.string:
        try:
            data = json.loads(json_ld_script.string)
            if isinstance(data, dict) and data.get('@type') == 'Product':
                # Try gtin13 first (barcode)
                gtin = data.get('gtin13')
                if gtin:
                    return str(gtin).strip()
                
                # Try gtin (generic)
                gtin = data.get('gtin')
                if gtin:
                    return str(gtin).strip()
        except (json.JSONDecodeError, ValueError):
            pass

    # Fallback: dataLayer productDetail.ean
    scripts = soup.find_all('script')
    for script in scripts:
        if script.string and 'dataLayer.push' in script.string and 'productDetail.ean' in script.string:
            match = re.search(r'"productDetail\.ean"\s*:\s*"([^"]+)"', script.string)
            if match:
                return match.group(1).strip()

    return None


def extract_currency(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract currency code.

    Primary: JSON-LD structured data priceCurrency
    Fallback: Hardcoded default (NOK for Norwegian site)
    Confidence: 1.0
    """
    # Primary: JSON-LD structured data
    json_ld_script = soup.find('script', type='application/ld+json')
    if json_ld_script and json_ld_script.string:
        try:
            data = json.loads(json_ld_script.string)
            if isinstance(data, dict) and data.get('@type') == 'Product':
                offers = data.get('offers', {})
                if isinstance(offers, dict):
                    currency = offers.get('priceCurrency')
                    if currency:
                        return str(currency).strip()
        except (json.JSONDecodeError, ValueError):
            pass

    # Fallback: Norwegian site default
    return "NOK"
