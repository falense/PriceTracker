"""
Extractor for www.sinful.no

Generated on 2025-12-22
Domain: www.sinful.no / sinful.no
"""
import re
import json
from decimal import Decimal
from typing import Optional
from bs4 import BeautifulSoup
from ._base import BaseExtractor


# Metadata (required for discovery)
PATTERN_METADATA = {
    'domain': 'sinful.no',
    'generated_at': '2025-12-22T23:00:00',
    'generator': 'Manual extraction pattern creation',
    'version': '1.0',
    'confidence': 0.92,
    'fields': ['price', 'title', 'image', 'availability', 'article_number', 'model_number', 'currency'],
    'notes': 'Uses structured data in script tags and Open Graph meta tags. Norwegian e-commerce site.'
}


def _extract_script_product_data(soup: BeautifulSoup) -> Optional[dict]:
    """
    Extract product data from script tags.
    
    The product data is embedded in Next.js data format within script tags.
    Pattern: "sku":"XXXXX"..."price":NNN..."offers":{...}
    
    Returns:
        Product data dict or None
    """
    scripts = soup.find_all('script')
    for script in scripts:
        if not script.string:
            continue
        
        # Look for SKU field which indicates product data
        # We need to find the main product, not related products
        # The main product has both sku and offers with price
        if '"sku":"' in script.string and '"price":' in script.string:
            # Find all SKU occurrences
            sku_matches = list(re.finditer(r'"sku":"([^"]+)"', script.string))
            
            for sku_match in sku_matches:
                sku = sku_match.group(1)
                idx = sku_match.start()
                
                # Get context around this SKU (need larger context for nested objects)
                context_start = max(0, idx - 200)
                context_end = min(len(script.string), idx + 1000)
                context = script.string[context_start:context_end]
                
                # Check if this context has the required fields (sku, mpn, offers, price)
                # This filters out related products which might only have partial data
                if '"mpn":"' not in context or '"offers"' not in context:
                    continue
                
                # Build product data dict from the context
                product_data = {}
                
                # Extract SKU
                sku_pattern = re.search(r'"sku":"([^"]+)"', context)
                if sku_pattern:
                    product_data['sku'] = sku_pattern.group(1)
                
                # Extract MPN (model number)
                mpn_match = re.search(r'"mpn":"([^"]+)"', context)
                if mpn_match:
                    product_data['mpn'] = mpn_match.group(1)
                
                # Extract price from offers
                price_match = re.search(r'"price":(\d+)', context)
                if price_match:
                    product_data['price'] = price_match.group(1)
                
                # Extract currency
                currency_match = re.search(r'"priceCurrency":"([^"]+)"', context)
                if currency_match:
                    product_data['currency'] = currency_match.group(1)
                
                # Extract availability
                avail_match = re.search(r'"availability":"([^"]+)"', context)
                if avail_match:
                    product_data['availability'] = avail_match.group(1)
                
                # Extract image
                image_match = re.search(r'"image":"([^"]+)"', context)
                if image_match:
                    product_data['image'] = image_match.group(1)
                
                # If we have both sku and price, this is likely the main product
                if 'sku' in product_data and 'price' in product_data:
                    return product_data
    
    return None


def extract_price(soup: BeautifulSoup) -> Optional[Decimal]:
    """
    Extract price.

    Primary: JSON data in script tags
    Fallback: Text search for price pattern
    Confidence: 0.95
    """
    # Primary: Extract from script data
    product_data = _extract_script_product_data(soup)
    if product_data and 'price' in product_data:
        return BaseExtractor.clean_price(product_data['price'])
    
    # Fallback 1: Look for price in meta tags (if they exist)
    meta_price = soup.select_one('meta[property="product:price:amount"]')
    if meta_price:
        value = meta_price.get('content')
        if value:
            return BaseExtractor.clean_price(value)
    
    # Fallback 2: Search for price pattern in visible text
    # Norwegian format: "439,00 kr" or "439 kr"
    html_text = soup.get_text()
    price_pattern = re.search(r'(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)\s*kr', html_text, re.IGNORECASE)
    if price_pattern:
        # Find the most prominent price (likely the product price)
        # Look for it near product-related text
        potential_prices = re.findall(r'(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)\s*kr', html_text, re.IGNORECASE)
        if potential_prices:
            # Return first match that seems reasonable (between 1 and 100000 kr)
            for price_str in potential_prices:
                price = BaseExtractor.clean_price(price_str)
                if price and 1 < price < 100000:
                    return price
    
    return None


def extract_title(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract title.

    Primary: Open Graph title meta tag
    Fallback: H1 element
    Confidence: 0.95
    """
    # Primary: og:title meta tag
    og_title = soup.select_one('meta[property="og:title"]')
    if og_title:
        value = og_title.get('content')
        if value:
            value = BaseExtractor.clean_text(value)
            # Remove site suffix if present
            if value and ' | Sinful' in value:
                value = value.split(' | Sinful')[0].strip()
            return value if value else None
    
    # Fallback 1: H1 element
    h1 = soup.find('h1')
    if h1:
        return BaseExtractor.clean_text(h1.get_text())
    
    # Fallback 2: Page title tag
    title_tag = soup.find('title')
    if title_tag:
        value = BaseExtractor.clean_text(title_tag.get_text())
        if value and ' | Sinful' in value:
            value = value.split(' | Sinful')[0].strip()
        return value if value else None
    
    return None


def extract_image(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract image.

    Primary: Open Graph image meta tag
    Fallback: Product data from script or main product image
    Confidence: 0.95
    """
    # Primary: og:image meta tag
    og_image = soup.select_one('meta[property="og:image"]')
    if og_image:
        value = og_image.get('content')
        if value:
            value = str(value).strip()
            if value.startswith('http'):
                return value
    
    # Fallback 1: Extract from script data
    product_data = _extract_script_product_data(soup)
    if product_data and 'image' in product_data:
        image_url = product_data['image']
        if image_url and image_url.startswith('http'):
            return image_url
    
    # Fallback 2: Look for main product image
    # The gallery images have data-gallery-index attribute
    main_image = soup.select_one('img[data-gallery-index="0"], img[alt*="var 1"]')
    if main_image:
        # Check srcset first for higher quality
        srcset = main_image.get('srcset')
        if srcset:
            # Extract the highest quality image from srcset
            # Format: "url 1x, url 2x"
            urls = re.findall(r'(https://[^\s]+)', srcset)
            if urls:
                return urls[-1]  # Last URL is typically highest quality
        
        # Fallback to src
        src = main_image.get('src')
        if src and src.startswith('http'):
            return src
    
    return None


def extract_availability(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract availability.

    Primary: Availability from script data
    Fallback: Text search for "På lager" / "In Stock"
    Confidence: 0.90
    """
    # Primary: Extract from script data
    product_data = _extract_script_product_data(soup)
    if product_data and 'availability' in product_data:
        availability = product_data['availability']
        # Convert schema.org format to simple string
        if 'InStock' in availability:
            return 'In Stock'
        elif 'OutOfStock' in availability:
            return 'Out of Stock'
        elif 'PreOrder' in availability:
            return 'Pre-order'
        elif 'Discontinued' in availability:
            return 'Discontinued'
        return availability
    
    # Fallback 1: Look for Norwegian stock status text
    # Common patterns: "På lager", "Ikke på lager"
    stock_elem = soup.find(string=re.compile(r'På lager', re.IGNORECASE))
    if stock_elem:
        return 'In Stock'
    
    out_of_stock = soup.find(string=re.compile(r'Ikke på lager|Utsolgt', re.IGNORECASE))
    if out_of_stock:
        return 'Out of Stock'
    
    # Fallback 2: Check delivery information
    # If delivery time is mentioned, assume in stock
    delivery_elem = soup.find(string=re.compile(r'Levering:.*\d+-\d+.*hverdager', re.IGNORECASE))
    if delivery_elem:
        return 'In Stock'
    
    return None


def extract_article_number(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract article_number (store SKU).

    Primary: SKU from script data
    Confidence: 0.95
    """
    # Primary: Extract from script data
    product_data = _extract_script_product_data(soup)
    if product_data and 'sku' in product_data:
        return str(product_data['sku'])
    
    # Fallback: Extract from URL
    # URL format: /p/product-name/XXXXXXX?variantSku=YYYY
    # The productKey is in the URL path, variantSku in query
    canonical = soup.select_one('link[rel="canonical"]')
    if canonical:
        url = canonical.get('href', '')
        if url:
            # Extract from path: /p/name/1023501
            match = re.search(r'/p/[^/]+/(\d+)', url)
            if match:
                return match.group(1)
    
    return None


def extract_model_number(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract model_number (manufacturer part number).

    Primary: MPN from script data
    Confidence: 0.90
    """
    # Primary: Extract from script data
    product_data = _extract_script_product_data(soup)
    if product_data and 'mpn' in product_data:
        return str(product_data['mpn'])
    
    # Fallback: Often same as SKU for this store
    # Check variant SKU from URL query parameter
    # URL: ?variantSku=23501
    scripts = soup.find_all('script')
    for script in scripts:
        if script.string and 'variantSku' in script.string:
            match = re.search(r'variantSku["\']?\s*[:=]\s*["\']?(\d+)', script.string)
            if match:
                return match.group(1)
    
    return None


def extract_currency(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract currency code.

    Primary: From script data
    Fallback: Hardcoded default for Norwegian site
    Confidence: 1.0
    """
    # Primary: Extract from script data
    product_data = _extract_script_product_data(soup)
    if product_data and 'currency' in product_data:
        return str(product_data['currency'])
    
    # Fallback: Norwegian site defaults to NOK
    return "NOK"
