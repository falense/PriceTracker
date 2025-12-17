"""Simple pattern generator for e-commerce websites."""

import re
import structlog
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from urllib.parse import urlparse

from ExtractorPatternAgent.src.utils.stealth import (
    STEALTH_ARGS,
    apply_stealth,
    get_stealth_context_options
)


class PatternGenerator:
    """
    Simple pattern generator that analyzes product pages and generates extraction patterns.

    This is a lightweight alternative to the full ExtractorPatternAgent SDK implementation.
    """

    def __init__(self, logger: Optional[structlog.BoundLogger] = None):
        """
        Initialize PatternGenerator.

        Args:
            logger: Optional structlog logger. If not provided, a default logger will be created.
        """
        self.logger = logger or structlog.get_logger()

    async def fetch_page(self, url: str) -> str:
        """
        Fetch page with comprehensive stealth to avoid bot detection.

        Args:
            url: URL to fetch

        Returns:
            HTML content as string
        """
        self.logger.info("fetch_page_started", url=url)

        async with async_playwright() as p:
            # Launch with stealth arguments
            browser = await p.chromium.launch(
                headless=True,  # Required for Docker/server environments
                args=STEALTH_ARGS
            )

            # Create context with stealth options
            context_options = get_stealth_context_options()
            context = await browser.new_context(**context_options)

            page = await context.new_page()

            # Apply comprehensive stealth script
            await apply_stealth(page)

            try:
                # Navigate with realistic behavior
                await page.goto(url, wait_until='load', timeout=60000)

                # Wait for dynamic content (more realistic timing)
                await page.wait_for_timeout(2000)

                html = await page.content()
                self.logger.info("fetch_page_completed", url=url, html_length=len(html))
                return html
            finally:
                await browser.close()

    def analyze_html(self, html: str, url: str) -> Dict[str, Any]:
        """
        Analyze HTML and generate extraction patterns.

        Args:
            html: HTML content to analyze
            url: Original URL (used for domain extraction)

        Returns:
            Dictionary with extraction patterns
        """
        self.logger.info("analyze_html_started", url=url)

        soup = BeautifulSoup(html, 'html.parser')
        # Normalize domain by removing www prefix for consistency
        domain = urlparse(url).netloc.replace('www.', '').lower()
        patterns = {
            "store_domain": domain,
            "url": url,
            "patterns": {}
        }

        # Extract Price
        self.logger.info("extracting_field", field="price")
        price_pattern = self._extract_price(soup)
        if price_pattern:
            patterns["patterns"]["price"] = price_pattern
            self.logger.info("pattern_found", field="price",
                           selector=price_pattern["primary"]["selector"])
        else:
            self.logger.warning("pattern_not_found", field="price")

        # Extract Title
        self.logger.info("extracting_field", field="title")
        title_pattern = self._extract_title(soup)
        if title_pattern:
            patterns["patterns"]["title"] = title_pattern
            self.logger.info("pattern_found", field="title",
                           selector=title_pattern["primary"]["selector"])
        else:
            self.logger.warning("pattern_not_found", field="title")

        # Extract Image
        self.logger.info("extracting_field", field="image")
        image_pattern = self._extract_image(soup)
        if image_pattern:
            patterns["patterns"]["image"] = image_pattern
            self.logger.info("pattern_found", field="image",
                           selector=image_pattern["primary"]["selector"])
        else:
            self.logger.warning("pattern_not_found", field="image")

        # Extract Availability/Stock
        self.logger.info("extracting_field", field="availability")
        avail_pattern = self._extract_availability(soup)
        if avail_pattern:
            patterns["patterns"]["availability"] = avail_pattern
            self.logger.info("pattern_found", field="availability",
                           selector=avail_pattern["primary"]["selector"])
        else:
            self.logger.warning("pattern_not_found", field="availability")

        # Extract Article Number
        self.logger.info("extracting_field", field="article_number")
        article_pattern = self._extract_article_number(soup)
        if article_pattern:
            patterns["patterns"]["article_number"] = article_pattern
            self.logger.info("pattern_found", field="article_number",
                           selector=article_pattern["primary"]["selector"])
        else:
            self.logger.warning("pattern_not_found", field="article_number")

        # Extract Model Number
        self.logger.info("extracting_field", field="model_number")
        model_pattern = self._extract_model_number(soup)
        if model_pattern:
            patterns["patterns"]["model_number"] = model_pattern
            self.logger.info("pattern_found", field="model_number",
                           selector=model_pattern["primary"]["selector"])
        else:
            self.logger.warning("pattern_not_found", field="model_number")

        # Calculate overall confidence
        confidences = []
        for field_pattern in patterns["patterns"].values():
            confidences.append(field_pattern["primary"]["confidence"])

        patterns["metadata"] = {
            "fields_found": len(patterns["patterns"]),
            "total_fields": 6,
            "overall_confidence": sum(confidences) / len(confidences) if confidences else 0.0
        }

        self.logger.info("analyze_html_completed",
                        fields_found=patterns["metadata"]["fields_found"],
                        overall_confidence=patterns["metadata"]["overall_confidence"])

        return patterns

    def _extract_price(self, soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """Extract price pattern from HTML."""
        # Try data-price attribute
        price_elem = soup.select_one('[data-price]')
        if price_elem:
            price_value = price_elem.get('data-price')
            selector = f"#{price_elem.get('id')}" if price_elem.get('id') else f".{price_elem.get('class')[0]}"
            return {
                "primary": {
                    "type": "css",
                    "selector": selector,
                    "attribute": "data-price",
                    "confidence": 0.95,
                    "sample_value": price_value
                },
                "fallbacks": []
            }

        # Try price class names
        price_elems = soup.find_all(class_=lambda c: c and 'price' in str(c).lower())
        for elem in price_elems[:3]:
            text = elem.get_text(strip=True)
            if re.search(r'\d+[.,]?\d*', text):
                classes = elem.get('class', [])
                selector = f".{classes[0]}" if classes else elem.name
                return {
                    "primary": {
                        "type": "css",
                        "selector": selector,
                        "confidence": 0.85,
                        "sample_value": text
                    },
                    "fallbacks": []
                }
        return None

    def _extract_title(self, soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """Extract title pattern from HTML."""
        # Try Open Graph
        og_title = soup.select_one('meta[property="og:title"]')
        if og_title and og_title.get('content'):
            pattern = {
                "primary": {
                    "type": "meta",
                    "selector": 'meta[property="og:title"]',
                    "attribute": "content",
                    "confidence": 0.95,
                    "sample_value": og_title.get('content')
                },
                "fallbacks": []
            }
            # Add h1 as fallback
            h1 = soup.find('h1')
            if h1:
                pattern["fallbacks"].append({
                    "type": "css",
                    "selector": "h1",
                    "confidence": 0.85
                })
            return pattern

        # Try h1 as primary
        h1 = soup.find('h1')
        if h1:
            text = h1.get_text(strip=True)
            return {
                "primary": {
                    "type": "css",
                    "selector": "h1",
                    "confidence": 0.85,
                    "sample_value": text
                },
                "fallbacks": []
            }
        return None

    def _extract_image(self, soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """Extract image pattern from HTML."""
        # Try Open Graph
        og_image = soup.select_one('meta[property="og:image:secure_url"], meta[property="og:image"]')
        if og_image and og_image.get('content'):
            return {
                "primary": {
                    "type": "meta",
                    "selector": 'meta[property="og:image:secure_url"]',
                    "attribute": "content",
                    "confidence": 0.95,
                    "sample_value": og_image.get('content')
                },
                "fallbacks": [{
                    "type": "meta",
                    "selector": 'meta[property="og:image"]',
                    "attribute": "content",
                    "confidence": 0.95
                }]
            }
        return None

    def _extract_availability(self, soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """Extract availability/stock pattern from HTML."""
        # Look for stock-related elements
        stock_elems = soup.find_all(class_=lambda c: c and any(
            kw in str(c).lower() for kw in ['stock', 'availability', 'avail', 'lager']
        ))

        for elem in stock_elems[:3]:
            text = elem.get_text(strip=True)
            if text:
                classes = elem.get('class', [])
                selector = f".{classes[0]}" if classes else elem.name

                # Check if it has a title attribute (often more reliable)
                title = elem.get('title')
                if title:
                    return {
                        "primary": {
                            "type": "css",
                            "selector": selector,
                            "attribute": "title",
                            "confidence": 0.90,
                            "sample_value": title
                        },
                        "fallbacks": [{
                            "type": "css",
                            "selector": selector,
                            "confidence": 0.85
                        }]
                    }
                else:
                    return {
                        "primary": {
                            "type": "css",
                            "selector": selector,
                            "confidence": 0.80,
                            "sample_value": text
                        },
                        "fallbacks": []
                    }
        return None

    def _extract_article_number(self, soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """Extract article number/SKU pattern from HTML."""
        # Try itemprop="sku"
        sku_elem = soup.select_one('[itemprop="sku"]')
        if sku_elem:
            sku_value = sku_elem.get_text(strip=True)
            return {
                "primary": {
                    "type": "css",
                    "selector": '[itemprop="sku"]',
                    "confidence": 0.95,
                    "sample_value": sku_value
                },
                "fallbacks": []
            }

        # Try searching for "Varenummer" or "Article" labels
        for label in soup.find_all(['span', 'div', 'dt']):
            label_text = label.get_text(strip=True).lower()
            if any(kw in label_text for kw in ['varenummer', 'artikkel', 'article', 'sku', 'item number']):
                # Look for value in next sibling
                value_elem = label.find_next_sibling()
                if value_elem:
                    value = value_elem.get_text(strip=True)
                    if value and value.isdigit():
                        return {
                            "primary": {
                                "type": "css",
                                "selector": f"{label.name} + {value_elem.name}",
                                "confidence": 0.85,
                                "sample_value": value
                            },
                            "fallbacks": []
                        }
        return None

    def _extract_model_number(self, soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """Extract model number/manufacturer number pattern from HTML."""
        import json as json_lib
        from html import unescape

        # Try searching in JSON data attributes
        json_elems = soup.find_all(attrs={"data-initobject": True})
        for elem in json_elems:
            try:
                data_str = elem.get('data-initobject', '')
                # Unescape HTML entities
                data_str = unescape(data_str)
                data = json_lib.loads(data_str)

                # Look for manufacturer number
                model_num = None
                json_path = None

                # Check trackingData first
                if 'trackingData' in data:
                    for key in ['item_manufacturer_number', 'manufacturerNumber', 'model_number', 'modelNumber', 'mpn']:
                        if key in data['trackingData']:
                            model_num = data['trackingData'][key]
                            json_path = f"trackingData.{key}"
                            break

                # Check root level
                if not model_num:
                    for key in ['item_manufacturer_number', 'manufacturerNumber', 'model_number', 'modelNumber', 'mpn']:
                        if key in data:
                            model_num = data[key]
                            json_path = key
                            break

                if model_num:
                    classes = elem.get('class', [])
                    selector = f".{classes[0]}" if classes else f"{elem.name}"
                    return {
                        "primary": {
                            "type": "json",
                            "selector": selector,
                            "attribute": "data-initobject",
                            "json_path": json_path,
                            "confidence": 0.90,
                            "sample_value": model_num
                        },
                        "fallbacks": []
                    }
            except Exception:
                continue

        # Try searching for "Model" or "Produsent" labels
        for label in soup.find_all(['span', 'div', 'dt', 'th']):
            label_text = label.get_text(strip=True).lower()
            if any(kw in label_text for kw in ['modell', 'model', 'produsent', 'manufacturer', 'mpn', 'part number']):
                # Look for value in next sibling
                value_elem = label.find_next_sibling() or label.find_next(['td', 'dd', 'span'])
                if value_elem:
                    value = value_elem.get_text(strip=True)
                    if value and len(value) > 3:
                        return {
                            "primary": {
                                "type": "css",
                                "selector": f"{label.name}:contains('{label_text[:10]}') + {value_elem.name}",
                                "confidence": 0.75,
                                "sample_value": value
                            },
                            "fallbacks": []
                        }
        return None

    def _generate_selector_code(self, selector_config: Dict, indent: str = "    ") -> str:
        """
        Generate Python code for a selector configuration.

        Args:
            selector_config: Selector dict from JSON pattern
            indent: Indentation string

        Returns:
            Python code as string
        """
        selector_type = selector_config.get('type')
        selector = selector_config.get('selector')
        attribute = selector_config.get('attribute')
        json_path = selector_config.get('json_path')

        # Escape double quotes in selector for Python string
        if selector:
            selector = selector.replace('"', '\\"')
        if attribute:
            attribute = attribute.replace('"', '\\"')
        if json_path:
            json_path = json_path.replace('"', '\\"')

        if selector_type == 'css':
            if json_path:
                # CSS + JSON path (e.g., data-initobject)
                return f"""{indent}# Extract from JSON in {attribute}
{indent}elem = soup.select_one("{selector}")
{indent}if elem and elem.get("{attribute}"):
{indent}    try:
{indent}        import json
{indent}        from html import unescape
{indent}        data_str = unescape(elem.get("{attribute}"))
{indent}        data = json.loads(data_str)
{indent}        value = BaseExtractor.extract_json_field(data, "{json_path}")
{indent}        if value:
{indent}            return str(value)
{indent}    except:
{indent}        pass
"""
            elif attribute:
                # CSS + attribute
                return f"""{indent}elem = soup.select_one("{selector}")
{indent}if elem:
{indent}    value = elem.get("{attribute}")
{indent}    if value:
{indent}        return value
"""
            else:
                # CSS text content
                return f"""{indent}elem = soup.select_one("{selector}")
{indent}if elem:
{indent}    return BaseExtractor.clean_text(elem.get_text())
"""

        elif selector_type == 'meta' or selector_type == 'json':
            # Meta tag or JSON data
            return f"""{indent}elem = soup.select_one("{selector}")
{indent}if elem:
{indent}    value = elem.get("{attribute or "content"}")
{indent}    if value:
{indent}        return value
"""

        elif selector_type == 'xpath':
            # XPath (less common)
            return f"""{indent}# XPath selector: {selector}
{indent}from lxml import html as lxml_html
{indent}try:
{indent}    tree = lxml_html.fromstring(str(soup))
{indent}    elements = tree.xpath("{selector}")
{indent}    if elements:
{indent}        return elements[0].text_content().strip()
{indent}except:
{indent}    pass
"""

        return f"{indent}# TODO: Unsupported selector type: {selector_type}\n{indent}pass\n"

    def _generate_extract_function(self, field_name: str, field_pattern: Dict, confidence: float) -> str:
        """Generate extract_* function for a field."""
        primary = field_pattern.get('primary', {})
        fallbacks = field_pattern.get('fallbacks', [])

        # Determine return type
        if field_name == 'price':
            return_type = 'Optional[Decimal]'
            clean_method = 'BaseExtractor.clean_price'
        else:
            return_type = 'Optional[str]'
            clean_method = 'BaseExtractor.clean_text'

        # Start function
        func_code = f'''def extract_{field_name}(soup: BeautifulSoup) -> {return_type}:
    """
    Extract {field_name}.

    Primary: {primary.get('description', primary.get('selector', 'N/A'))}
    Confidence: {confidence:.2f}
    """
'''

        # Primary selector
        if primary:
            func_code += "    # Primary selector\n"
            func_code += self._generate_selector_code(primary)

            # For price, add cleaning
            if field_name == 'price' and primary.get('type') == 'css' and not primary.get('json_path'):
                func_code += f"    if elem:\n"
                func_code += f"        return {clean_method}(elem.get_text(strip=True))\n"

        # Fallback selectors
        for i, fallback in enumerate(fallbacks):
            func_code += f"\n    # Fallback {i+1}: {fallback.get('description', fallback.get('selector', 'N/A'))}\n"
            func_code += self._generate_selector_code(fallback)

            # For price, add cleaning
            if field_name == 'price' and fallback.get('type') == 'css' and not fallback.get('json_path'):
                func_code += f"    if elem:\n"
                func_code += f"        return {clean_method}(elem.get_text(strip=True))\n"

        func_code += "\n    return None\n"

        return func_code

    def generate_python_module(self, patterns: Dict[str, Any], output_path: Optional[Path] = None) -> str:
        """
        Generate Python extractor module from JSON patterns.

        Args:
            patterns: Pattern dictionary (from analyze_html or generate)
            output_path: Optional path to save the module

        Returns:
            Generated Python code as string
        """
        domain = patterns.get('store_domain', 'unknown')
        patterns_data = patterns.get('patterns', {})
        metadata = patterns.get('metadata', {})

        # Start building Python code
        code = f'''"""
Auto-generated extractor for {domain}

Generated on {datetime.now().isoformat()}
Confidence: {metadata.get('overall_confidence', 0.0):.2f}
"""
import re
from decimal import Decimal
from typing import Optional
from bs4 import BeautifulSoup
from ExtractorPatternAgent.generated_extractors._base import BaseExtractor


# Metadata (required for discovery)
PATTERN_METADATA = {{
    'domain': '{domain}',
    'generated_at': '{datetime.now().isoformat()}',
    'generator': 'PatternGenerator',
    'version': '1.0',
    'confidence': {metadata.get('overall_confidence', 0.0):.2f},
    'fields': {list(patterns_data.keys())},
    'notes': 'Auto-generated by PatternGenerator'
}}


'''

        # Generate each extract function
        field_order = ['price', 'title', 'image', 'availability', 'article_number', 'model_number']

        for field_name in field_order:
            if field_name in patterns_data:
                field_pattern = patterns_data[field_name]
                primary_confidence = field_pattern.get('primary', {}).get('confidence', 0.0)
                code += self._generate_extract_function(field_name, field_pattern, primary_confidence)
                code += "\n\n"
            else:
                # Generate stub for missing fields
                return_type = 'Optional[Decimal]' if field_name == 'price' else 'Optional[str]'
                code += f'''def extract_{field_name}(soup: BeautifulSoup) -> {return_type}:
    """Extract {field_name} (not available in source pattern)."""
    return None


'''

        # Save to file if path provided
        if output_path:
            output_path.write_text(code)
            self.logger.info("python_module_saved", path=str(output_path), domain=domain)

        return code

    async def generate(self, url: str, domain: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate extraction patterns for a product URL.

        Args:
            url: Product URL to analyze
            domain: Optional domain override (if not provided, extracted from URL)

        Returns:
            Dictionary with extraction patterns
        """
        self.logger.info("pattern_generation_started", url=url)

        # Fetch page
        html = await self.fetch_page(url)

        # Analyze and generate patterns
        patterns = self.analyze_html(html, url)

        # Override domain if provided
        if domain:
            patterns["store_domain"] = domain.replace('www.', '').lower()

        self.logger.info("pattern_generation_completed",
                        store_domain=patterns['store_domain'],
                        fields_found=patterns['metadata']['fields_found'],
                        confidence=patterns['metadata']['overall_confidence'])

        return patterns
