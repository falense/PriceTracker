"""HTML processing utility functions."""

from bs4 import BeautifulSoup
from typing import Optional, List, Dict, Any
import re
import logging

logger = logging.getLogger(__name__)


def clean_text(text: str) -> str:
    """
    Clean and normalize extracted text.

    Args:
        text: Raw text to clean

    Returns:
        Cleaned text with normalized whitespace
    """
    if not text:
        return ""

    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()

    return text


def extract_price_from_text(text: str) -> Optional[str]:
    """
    Extract price value from text string.

    Args:
        text: Text potentially containing a price

    Returns:
        Extracted price string or None
    """
    if not text:
        return None

    # Common price patterns
    patterns = [
        r'[$€£¥₹₽]\s*(\d+[.,]\d{2})',  # $10.99, €10,99
        r'(\d+[.,]\d{2})\s*[$€£¥₹₽]',  # 10.99$
        r'(\d+[.,]\d{2})',               # 10.99
        r'[$€£¥₹₽]\s*(\d+)',            # $10
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(0)

    return None


def find_elements_with_text(html: str, text_pattern: str, tag: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Find HTML elements containing specific text pattern.

    Args:
        html: HTML content to search
        text_pattern: Regex pattern or text to search for
        tag: Optional tag name to limit search

    Returns:
        List of matching elements with their selectors
    """
    soup = BeautifulSoup(html, 'html.parser')
    results = []

    # Compile pattern
    pattern = re.compile(text_pattern, re.IGNORECASE)

    # Find all matching elements
    elements = soup.find_all(tag) if tag else soup.find_all()

    for el in elements:
        text = el.get_text(strip=True)
        if pattern.search(text):
            # Generate selector
            selector = _generate_selector_for_element(el)
            results.append({
                "element": el.name,
                "text": text[:100],
                "selector": selector,
                "classes": el.get('class', []),
                "id": el.get('id')
            })

    return results[:20]  # Limit results


def _generate_selector_for_element(element) -> str:
    """
    Generate a CSS selector for a BeautifulSoup element.

    Args:
        element: BeautifulSoup element

    Returns:
        CSS selector string
    """
    if element.get('id'):
        return f"#{element['id']}"

    if element.get('class'):
        classes = '.'.join(element['class'])
        return f"{element.name}.{classes}"

    return element.name


def extract_json_ld(html: str, schema_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Extract JSON-LD structured data from HTML.

    Args:
        html: HTML content
        schema_type: Optional schema.org type to filter by (e.g., "Product")

    Returns:
        List of JSON-LD data objects
    """
    soup = BeautifulSoup(html, 'html.parser')
    results = []

    scripts = soup.find_all('script', type='application/ld+json')

    for script in scripts:
        if not script.string:
            continue

        try:
            import json
            data = json.loads(script.string)

            # Handle @graph structures
            if isinstance(data, dict) and '@graph' in data:
                items = data['@graph']
            elif isinstance(data, list):
                items = data
            else:
                items = [data]

            # Filter by type if specified
            for item in items:
                if isinstance(item, dict):
                    item_type = item.get('@type', '')
                    if not schema_type or item_type == schema_type:
                        results.append(item)

        except Exception as e:
            logger.warning(f"Failed to parse JSON-LD: {e}")

    return results


def extract_meta_tags(html: str, prefix: Optional[str] = None) -> Dict[str, str]:
    """
    Extract meta tags from HTML.

    Args:
        html: HTML content
        prefix: Optional prefix to filter tags (e.g., "og:" for Open Graph)

    Returns:
        Dictionary of meta tag key-value pairs
    """
    soup = BeautifulSoup(html, 'html.parser')
    meta_tags = {}

    for meta in soup.find_all('meta'):
        key = meta.get('property') or meta.get('name')
        value = meta.get('content')

        if key and value:
            if not prefix or key.startswith(prefix):
                meta_tags[key] = value

    return meta_tags


def get_element_depth(element) -> int:
    """
    Calculate depth of element in DOM tree.

    Args:
        element: BeautifulSoup element

    Returns:
        Depth level (root = 0)
    """
    depth = 0
    current = element.parent

    while current:
        depth += 1
        current = current.parent

    return depth


def find_stable_parent(element, max_depth: int = 3):
    """
    Find a stable parent element with good selector characteristics.

    Args:
        element: BeautifulSoup element
        max_depth: Maximum depth to search up

    Returns:
        Parent element with ID or stable class, or original element
    """
    current = element
    depth = 0

    while current and depth < max_depth:
        # Prefer elements with IDs
        if current.get('id'):
            return current

        # Or semantic classes (not randomly generated)
        classes = current.get('class', [])
        if classes:
            stable_classes = [c for c in classes if not re.search(r'\d{4,}|[a-f0-9]{8,}', c)]
            if stable_classes:
                return current

        current = current.parent
        depth += 1

    return element


def simplify_html(html: str, keep_tags: Optional[List[str]] = None) -> str:
    """
    Simplify HTML by removing scripts, styles, and unnecessary tags.

    Args:
        html: HTML content to simplify
        keep_tags: Optional list of tags to keep (default: common content tags)

    Returns:
        Simplified HTML string
    """
    soup = BeautifulSoup(html, 'html.parser')

    # Remove script and style tags
    for script in soup(['script', 'style', 'noscript']):
        script.decompose()

    # Remove comments
    for comment in soup.find_all(string=lambda text: isinstance(text, str) and text.strip().startswith('<!--')):
        comment.extract()

    if keep_tags:
        # Keep only specified tags
        for element in soup.find_all():
            if element.name not in keep_tags:
                element.unwrap()

    return str(soup)
