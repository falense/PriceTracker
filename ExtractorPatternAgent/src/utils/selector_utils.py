"""Selector generation and optimization utilities."""

from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
import re
import logging

logger = logging.getLogger(__name__)


def generate_css_selector(element, prefer_id: bool = True) -> str:
    """
    Generate optimal CSS selector for an element.

    Args:
        element: BeautifulSoup element
        prefer_id: Whether to prefer ID selectors

    Returns:
        CSS selector string
    """
    # Prefer ID if available and requested
    if prefer_id and element.get('id'):
        element_id = element['id']
        # Ensure ID is stable (not auto-generated)
        if not re.search(r'\d{6,}|[a-f0-9]{8,}', element_id):
            return f"#{element_id}"

    # Try data attributes (often stable)
    for attr in element.attrs:
        if attr.startswith('data-') and not attr.endswith('-id'):
            value = element[attr]
            if value and not re.search(r'\d{6,}|[a-f0-9]{8,}', str(value)):
                return f"{element.name}[{attr}='{value}']"

    # Use semantic classes
    classes = element.get('class', [])
    if classes:
        stable_classes = []
        for cls in classes:
            # Avoid auto-generated classes
            if not re.search(r'\d{4,}|[a-f0-9]{8,}|^[a-z]{1,3}$', cls):
                # Prefer semantic names
                if any(keyword in cls.lower() for keyword in [
                    'price', 'title', 'product', 'name', 'availability',
                    'stock', 'image', 'description', 'content'
                ]):
                    stable_classes.insert(0, cls)
                else:
                    stable_classes.append(cls)

        if stable_classes:
            return f"{element.name}.{stable_classes[0]}"

    # Fallback: use tag with nth-child
    return _generate_nth_child_selector(element)


def _generate_nth_child_selector(element) -> str:
    """
    Generate nth-child selector as fallback.

    Args:
        element: BeautifulSoup element

    Returns:
        CSS selector with nth-child
    """
    if not element.parent:
        return element.name

    siblings = [s for s in element.parent.children if hasattr(s, 'name') and s.name == element.name]
    index = siblings.index(element) + 1

    parent_selector = generate_css_selector(element.parent, prefer_id=True)

    return f"{parent_selector} > {element.name}:nth-child({index})"


def generate_xpath_selector(element) -> str:
    """
    Generate XPath selector for an element.

    Args:
        element: BeautifulSoup element

    Returns:
        XPath selector string
    """
    components = []
    current = element

    while current and hasattr(current, 'name'):
        if current.get('id'):
            components.insert(0, f"//{current.name}[@id='{current['id']}']")
            break

        # Count position among siblings
        siblings = [s for s in current.parent.children if hasattr(s, 'name') and s.name == current.name]
        position = siblings.index(current) + 1

        if len(siblings) > 1:
            components.insert(0, f"{current.name}[{position}]")
        else:
            components.insert(0, current.name)

        current = current.parent

    if not components[0].startswith('//'):
        return '//' + '/'.join(components)

    return components[0] + '/' + '/'.join(components[1:]) if len(components) > 1 else components[0]


def test_selector_uniqueness(html: str, selector: str, selector_type: str = 'css') -> Dict[str, Any]:
    """
    Test if a selector uniquely identifies an element.

    Args:
        html: HTML content to test against
        selector: The selector to test
        selector_type: Type of selector ('css' or 'xpath')

    Returns:
        Dictionary with uniqueness info
    """
    soup = BeautifulSoup(html, 'html.parser')

    try:
        if selector_type == 'css':
            matches = soup.select(selector)
        else:
            # XPath requires lxml
            from lxml import html as lxml_html
            tree = lxml_html.fromstring(html)
            matches = tree.xpath(selector)

        is_unique = len(matches) == 1
        match_count = len(matches)

        return {
            "is_unique": is_unique,
            "match_count": match_count,
            "selector": selector,
            "type": selector_type
        }

    except Exception as e:
        logger.error(f"Error testing selector: {e}")
        return {
            "is_unique": False,
            "match_count": 0,
            "selector": selector,
            "type": selector_type,
            "error": str(e)
        }


def optimize_selector(html: str, selector: str) -> str:
    """
    Optimize a selector to be more specific or more general as needed.

    Args:
        html: HTML content
        selector: Initial selector

    Returns:
        Optimized selector
    """
    soup = BeautifulSoup(html, 'html.parser')
    matches = soup.select(selector)

    if not matches:
        # Selector doesn't work, can't optimize
        return selector

    if len(matches) == 1:
        # Already unique, try to simplify
        return _simplify_selector(selector)

    # Multiple matches, make more specific
    return _make_selector_more_specific(html, selector, matches[0])


def _simplify_selector(selector: str) -> str:
    """
    Simplify a selector by removing unnecessary parts.

    Args:
        selector: CSS selector

    Returns:
        Simplified selector
    """
    # Remove descendant combinators where possible
    parts = selector.split(' > ')
    if len(parts) > 2:
        # Try using just the last two parts
        return ' > '.join(parts[-2:])

    # Remove excessive class chaining
    parts = selector.split('.')
    if len(parts) > 2:
        # Keep tag and most specific class
        return f"{parts[0]}.{parts[-1]}"

    return selector


def _make_selector_more_specific(html: str, selector: str, target_element) -> str:
    """
    Make a selector more specific to match only the target element.

    Args:
        html: HTML content
        selector: Current selector
        target_element: The element we want to uniquely match

    Returns:
        More specific selector
    """
    # Try adding nth-child
    if target_element.parent:
        siblings = [s for s in target_element.parent.children
                   if hasattr(s, 'name') and s.name == target_element.name]
        index = siblings.index(target_element) + 1

        specific_selector = f"{selector}:nth-child({index})"

        soup = BeautifulSoup(html, 'html.parser')
        if len(soup.select(specific_selector)) == 1:
            return specific_selector

    # Try adding parent context
    if target_element.parent:
        parent_classes = target_element.parent.get('class', [])
        if parent_classes:
            return f".{parent_classes[0]} > {selector}"

    return selector


def suggest_fallback_selectors(html: str, primary_selector: str, field_type: str) -> List[str]:
    """
    Suggest alternative fallback selectors based on field type.

    Args:
        html: HTML content
        primary_selector: The primary selector that's being used
        field_type: Type of field (price, title, etc.)

    Returns:
        List of fallback selector strings
    """
    fallbacks = []
    soup = BeautifulSoup(html, 'html.parser')

    if field_type == "price":
        # Common price selector patterns
        patterns = [
            '[data-price]',
            '[data-product-price]',
            '.price',
            '.product-price',
            '[itemprop="price"]',
            'span.price',
            'div.price',
        ]

    elif field_type == "title":
        patterns = [
            'h1',
            '[itemprop="name"]',
            '.product-title',
            '.product-name',
            'h1[class*="product"]',
            'h1[class*="title"]',
        ]

    elif field_type == "availability":
        patterns = [
            '[data-availability]',
            '[itemprop="availability"]',
            '.availability',
            '.stock-status',
            'span[class*="stock"]',
        ]

    elif field_type == "image":
        patterns = [
            'img[itemprop="image"]',
            'img.product-image',
            'img[class*="product"]',
            'img[data-src]',
        ]

    else:
        return []

    # Test each pattern
    for pattern in patterns:
        if pattern != primary_selector:
            matches = soup.select(pattern)
            if matches:
                fallbacks.append(pattern)

    return fallbacks[:3]  # Return top 3 fallbacks
