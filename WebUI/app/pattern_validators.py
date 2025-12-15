"""
Pattern Validation Utilities.

Provides validation for pattern structure and selector syntax.
"""
import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


def validate_pattern_structure(pattern_json: Dict) -> Dict[str, Any]:
    """
    Validate pattern has correct structure.

    Args:
        pattern_json: Pattern JSON to validate

    Returns:
        Dict with 'valid' (bool) and 'errors' (list)
    """
    errors = []

    # Check required top-level keys
    required_keys = ['store_domain', 'patterns']
    for key in required_keys:
        if key not in pattern_json:
            errors.append(f'Missing required field: {key}')

    # Validate patterns object
    if 'patterns' in pattern_json:
        patterns = pattern_json['patterns']

        if not isinstance(patterns, dict):
            errors.append('patterns must be an object')
        else:
            # Validate each field pattern
            for field_name, field_pattern in patterns.items():
                field_errors = _validate_field_pattern(field_name, field_pattern)
                errors.extend(field_errors)

    return {
        'valid': len(errors) == 0,
        'errors': errors
    }


def _validate_field_pattern(field_name: str, field_pattern: Any) -> List[str]:
    """Validate individual field pattern structure."""
    errors = []

    if not isinstance(field_pattern, dict):
        errors.append(f'{field_name}: Field pattern must be an object')
        return errors

    # Check for primary selector
    if 'primary' not in field_pattern:
        errors.append(f'{field_name}: Missing primary selector')
    else:
        primary_errors = _validate_selector_structure(f'{field_name}.primary', field_pattern['primary'])
        errors.extend(primary_errors)

    # Validate fallbacks if present
    if 'fallbacks' in field_pattern:
        fallbacks = field_pattern['fallbacks']

        if not isinstance(fallbacks, list):
            errors.append(f'{field_name}.fallbacks: Must be an array')
        else:
            for i, fallback in enumerate(fallbacks):
                fallback_errors = _validate_selector_structure(
                    f'{field_name}.fallbacks[{i}]',
                    fallback
                )
                errors.extend(fallback_errors)

    return errors


def _validate_selector_structure(path: str, selector: Any) -> List[str]:
    """Validate selector object structure."""
    errors = []

    if not isinstance(selector, dict):
        errors.append(f'{path}: Selector must be an object')
        return errors

    # Check required fields
    if 'type' not in selector:
        errors.append(f'{path}: Missing type field')
    elif selector['type'] not in ['css', 'xpath', 'jsonld', 'meta']:
        errors.append(f'{path}: Invalid type "{selector["type"]}" (must be css, xpath, jsonld, or meta)')

    if 'selector' not in selector:
        errors.append(f'{path}: Missing selector field')

    # Validate optional fields
    if 'confidence' in selector:
        confidence = selector['confidence']
        if not isinstance(confidence, (int, float)):
            errors.append(f'{path}.confidence: Must be a number')
        elif not (0.0 <= confidence <= 1.0):
            errors.append(f'{path}.confidence: Must be between 0.0 and 1.0')

    return errors


def validate_css_selector(selector: str) -> bool:
    """
    Validate CSS selector syntax.

    Args:
        selector: CSS selector string

    Returns:
        True if valid, False otherwise
    """
    try:
        from bs4 import BeautifulSoup

        # Try to parse with a dummy HTML
        soup = BeautifulSoup('<div></div>', 'html.parser')
        soup.select(selector)
        return True

    except Exception as e:
        logger.debug(f"Invalid CSS selector '{selector}': {e}")
        return False


def validate_xpath_selector(selector: str) -> bool:
    """
    Validate XPath selector syntax.

    Args:
        selector: XPath selector string

    Returns:
        True if valid, False otherwise
    """
    try:
        from lxml import html as lxml_html
        from lxml import etree

        # Try to parse with a dummy HTML
        tree = lxml_html.fromstring('<div></div>')
        tree.xpath(selector)
        return True

    except etree.XPathEvalError as e:
        logger.debug(f"Invalid XPath selector '{selector}': {e}")
        return False
    except Exception as e:
        logger.debug(f"Error validating XPath '{selector}': {e}")
        return False


def validate_jsonld_selector(selector: str) -> bool:
    """
    Validate JSON-LD path selector.

    Args:
        selector: JSON-LD path (e.g., "offers.price")

    Returns:
        True if valid (basic check)
    """
    # JSON-LD selectors are just dot-separated paths
    # Basic validation: non-empty, alphanumeric with dots
    if not selector:
        return False

    import re
    return bool(re.match(r'^[a-zA-Z0-9_.]+$', selector))


def validate_meta_selector(selector: str) -> bool:
    """
    Validate meta tag selector.

    Args:
        selector: Meta property name (e.g., "og:title")

    Returns:
        True if valid (basic check)
    """
    # Meta selectors are property names
    # Basic validation: non-empty string
    return bool(selector and isinstance(selector, str))


def validate_selector_syntax(selector_type: str, selector: str) -> bool:
    """
    Validate selector syntax based on type.

    Args:
        selector_type: Type of selector (css, xpath, jsonld, meta)
        selector: Selector string

    Returns:
        True if valid, False otherwise
    """
    if selector_type == 'css':
        return validate_css_selector(selector)
    elif selector_type == 'xpath':
        return validate_xpath_selector(selector)
    elif selector_type == 'jsonld':
        return validate_jsonld_selector(selector)
    elif selector_type == 'meta':
        return validate_meta_selector(selector)
    else:
        logger.warning(f"Unknown selector type: {selector_type}")
        return False


def sanitize_pattern_json(pattern_json: Dict) -> Dict:
    """
    Sanitize pattern JSON to remove potential security issues.

    Args:
        pattern_json: Pattern JSON to sanitize

    Returns:
        Sanitized pattern JSON
    """
    import re
    import copy

    # Deep copy to avoid modifying original
    sanitized = copy.deepcopy(pattern_json)

    def clean_string(s: str) -> str:
        """Remove potential XSS patterns from strings."""
        if not isinstance(s, str):
            return s

        # Remove script tags
        s = re.sub(r'<script[^>]*>.*?</script>', '', s, flags=re.IGNORECASE | re.DOTALL)

        # Remove on* event handlers
        s = re.sub(r'\bon\w+\s*=', '', s, flags=re.IGNORECASE)

        # Remove javascript: protocol
        s = re.sub(r'javascript:', '', s, flags=re.IGNORECASE)

        return s

    def sanitize_dict(d: Dict) -> Dict:
        """Recursively sanitize dictionary."""
        for key, value in d.items():
            if isinstance(value, str):
                d[key] = clean_string(value)
            elif isinstance(value, dict):
                d[key] = sanitize_dict(value)
            elif isinstance(value, list):
                d[key] = [
                    sanitize_dict(item) if isinstance(item, dict)
                    else clean_string(item) if isinstance(item, str)
                    else item
                    for item in value
                ]
        return d

    return sanitize_dict(sanitized)
