"""Parser tools for HTML analysis and structured data extraction."""

from claude_agent_sdk import tool
from bs4 import BeautifulSoup
from typing import Any, Dict, List
import json
import logging
import re

logger = logging.getLogger(__name__)


@tool(
    "extract_structured_data",
    "Extract JSON-LD or meta tag structured data from HTML",
    {"html": str}
)
async def extract_structured_data_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract structured data from HTML (JSON-LD, Open Graph, meta tags).

    Args:
        html: The HTML content to parse

    Returns:
        Dictionary with extracted structured data
    """
    html = args["html"]
    logger.info("Extracting structured data from HTML")

    try:
        soup = BeautifulSoup(html, 'html.parser')
        result = {
            "jsonld": [],
            "meta_tags": {},
            "open_graph": {},
            "twitter_card": {},
        }

        # Extract JSON-LD
        jsonld_scripts = soup.find_all('script', type='application/ld+json')
        for script in jsonld_scripts:
            try:
                if script.string:
                    data = json.loads(script.string)
                    result["jsonld"].append(data)
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse JSON-LD: {e}")

        # Extract meta tags
        for meta in soup.find_all('meta'):
            # Open Graph tags
            if meta.get('property') and meta.get('property').startswith('og:'):
                key = meta.get('property')
                value = meta.get('content')
                if value:
                    result["open_graph"][key] = value

            # Twitter Card tags
            elif meta.get('name') and meta.get('name').startswith('twitter:'):
                key = meta.get('name')
                value = meta.get('content')
                if value:
                    result["twitter_card"][key] = value

            # Other meta tags
            elif meta.get('name') or meta.get('property'):
                key = meta.get('name') or meta.get('property')
                value = meta.get('content')
                if value:
                    result["meta_tags"][key] = value

        # Log summary
        logger.info(f"Found {len(result['jsonld'])} JSON-LD blocks, "
                   f"{len(result['open_graph'])} OG tags, "
                   f"{len(result['meta_tags'])} meta tags")

        return {
            "content": [{
                "type": "text",
                "text": f"Structured data extraction results:\n\n{json.dumps(result, indent=2)}"
            }]
        }

    except Exception as e:
        logger.error(f"Error extracting structured data: {e}")
        return {
            "content": [{
                "type": "text",
                "text": f"Error extracting structured data: {str(e)}"
            }],
            "isError": True
        }


@tool(
    "analyze_selectors",
    "Analyze HTML structure and suggest reliable CSS selectors for a specific field",
    {"html": str, "field": str}
)
async def analyze_selectors_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze HTML for good selector candidates based on field type.

    Args:
        html: The HTML content to analyze
        field: The field type to find selectors for (price, title, availability, image)

    Returns:
        Dictionary with suggested selectors and confidence scores
    """
    html = args["html"]
    field = args["field"].lower()
    logger.info(f"Analyzing selectors for field: {field}")

    try:
        soup = BeautifulSoup(html, 'html.parser')
        candidates = []

        if field == "price":
            # Look for price-related patterns
            # 1. Elements with price in class/id
            price_elements = soup.find_all(
                class_=lambda c: c and any(kw in c.lower() for kw in ['price', 'cost', 'amount'])
            )
            for el in price_elements[:10]:
                text = el.get_text(strip=True)
                # Check if contains price pattern
                if re.search(r'[$€£¥]\s*\d+|\\d+\.\d{2}', text):
                    classes = el.get('class', [])
                    if classes:
                        selector = f".{classes[0]}"
                        candidates.append({
                            "selector": selector,
                            "type": "css",
                            "confidence": 0.8,
                            "sample_value": text[:50],
                            "reasoning": "Class name contains 'price' and element contains price pattern"
                        })

            # 2. Look for data attributes
            data_price_els = soup.find_all(attrs={"data-price": True})
            for el in data_price_els[:5]:
                candidates.append({
                    "selector": "[data-price]",
                    "type": "css",
                    "confidence": 0.9,
                    "attribute": "data-price",
                    "sample_value": el.get("data-price", ""),
                    "reasoning": "data-price attribute found"
                })

        elif field == "title":
            # Look for title patterns
            # 1. H1 tags (most common for product titles)
            h1_tags = soup.find_all('h1')
            for h1 in h1_tags[:3]:
                text = h1.get_text(strip=True)
                if len(text) > 10:  # Reasonable title length
                    candidates.append({
                        "selector": "h1",
                        "type": "css",
                        "confidence": 0.85,
                        "sample_value": text[:50],
                        "reasoning": "H1 tag with substantial content"
                    })

            # 2. Product title classes
            title_elements = soup.find_all(
                class_=lambda c: c and any(kw in c.lower() for kw in ['product-title', 'product_name', 'item-name'])
            )
            for el in title_elements[:5]:
                classes = el.get('class', [])
                if classes:
                    candidates.append({
                        "selector": f".{classes[0]}",
                        "type": "css",
                        "confidence": 0.9,
                        "sample_value": el.get_text(strip=True)[:50],
                        "reasoning": "Class name suggests product title"
                    })

        elif field == "availability":
            # Look for availability/stock indicators
            stock_elements = soup.find_all(
                class_=lambda c: c and any(kw in c.lower() for kw in ['stock', 'availability', 'available'])
            )
            for el in stock_elements[:5]:
                text = el.get_text(strip=True).lower()
                if any(kw in text for kw in ['in stock', 'out of stock', 'available', 'unavailable']):
                    classes = el.get('class', [])
                    if classes:
                        candidates.append({
                            "selector": f".{classes[0]}",
                            "type": "css",
                            "confidence": 0.85,
                            "sample_value": el.get_text(strip=True),
                            "reasoning": "Class and text indicate stock status"
                        })

        elif field == "image":
            # Look for main product images
            # 1. Images with specific classes
            img_elements = soup.find_all('img',
                class_=lambda c: c and any(kw in c.lower() for kw in ['product', 'main', 'primary'])
            )
            for img in img_elements[:5]:
                classes = img.get('class', [])
                src = img.get('src', '')
                if classes and src:
                    candidates.append({
                        "selector": f"img.{classes[0]}",
                        "type": "css",
                        "confidence": 0.8,
                        "attribute": "src",
                        "sample_value": src[:100],
                        "reasoning": "Image with product-related class"
                    })

            # 2. First large image
            all_images = soup.find_all('img', src=True)
            if all_images:
                candidates.append({
                    "selector": "img[src]",
                    "type": "css",
                    "confidence": 0.6,
                    "attribute": "src",
                    "sample_value": all_images[0].get('src', '')[:100],
                    "reasoning": "Fallback: first image with src"
                })

        # Sort by confidence
        candidates.sort(key=lambda x: x['confidence'], reverse=True)

        logger.info(f"Found {len(candidates)} selector candidates for {field}")

        return {
            "content": [{
                "type": "text",
                "text": f"Selector analysis for '{field}':\n\n{json.dumps(candidates[:10], indent=2)}"
            }]
        }

    except Exception as e:
        logger.error(f"Error analyzing selectors: {e}")
        return {
            "content": [{
                "type": "text",
                "text": f"Error analyzing selectors: {str(e)}"
            }],
            "isError": True
        }


@tool(
    "extract_with_selector",
    "Test extraction using a specific CSS selector on HTML content",
    {"html": str, "selector": str, "attribute": str}
)
async def extract_with_selector_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract data using a CSS selector.

    Args:
        html: The HTML content
        selector: CSS selector to use
        attribute: Optional attribute to extract (e.g., 'src', 'href'). If not provided, extracts text.

    Returns:
        Dictionary with extracted values
    """
    html = args["html"]
    selector = args["selector"]
    attribute = args.get("attribute")

    logger.info(f"Extracting with selector: {selector}, attribute: {attribute}")

    try:
        soup = BeautifulSoup(html, 'html.parser')
        elements = soup.select(selector)

        results = []
        for el in elements[:10]:  # Limit to first 10 matches
            if attribute:
                value = el.get(attribute, '')
            else:
                value = el.get_text(strip=True)

            if value:
                results.append(value)

        logger.info(f"Found {len(results)} matches")

        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "selector": selector,
                    "attribute": attribute,
                    "match_count": len(results),
                    "values": results
                }, indent=2)
            }]
        }

    except Exception as e:
        logger.error(f"Error extracting with selector: {e}")
        return {
            "content": [{
                "type": "text",
                "text": f"Error extracting with selector: {str(e)}"
            }],
            "isError": True
        }
