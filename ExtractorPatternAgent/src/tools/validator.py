"""Validator tools for testing extraction patterns."""

from claude_agent_sdk import tool
from bs4 import BeautifulSoup
from typing import Any, Dict
import json
import logging
import re

logger = logging.getLogger(__name__)


@tool(
    "test_pattern",
    "Test a selector pattern against HTML and return extracted value",
    {"html": str, "selector": str, "selector_type": str, "attribute": str}
)
async def test_pattern_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Test if a selector extracts valid data from HTML.

    Args:
        html: The HTML content to test against
        selector: The selector string (CSS or XPath)
        selector_type: Type of selector ("css" or "xpath")
        attribute: Optional attribute to extract (for "css" type only)

    Returns:
        Dictionary with test results including success status and extracted value
    """
    html = args["html"]
    selector = args["selector"]
    selector_type = args["selector_type"]
    attribute = args.get("attribute")

    logger.info(f"Testing pattern: {selector_type}='{selector}', attribute='{attribute}'")

    try:
        soup = BeautifulSoup(html, 'html.parser')
        value = None
        success = False

        if selector_type == "css":
            element = soup.select_one(selector)
            if element:
                if attribute:
                    value = element.get(attribute, '')
                else:
                    value = element.get_text(strip=True)
                success = value is not None and len(str(value)) > 0

        elif selector_type == "xpath":
            # XPath requires lxml parser
            from lxml import html as lxml_html
            from lxml import etree

            tree = lxml_html.fromstring(html)
            elements = tree.xpath(selector)

            if elements:
                elem = elements[0]
                if attribute and hasattr(elem, 'get'):
                    value = elem.get(attribute, '')
                elif isinstance(elem, str):
                    value = elem
                else:
                    value = elem.text_content().strip()
                success = value is not None and len(str(value)) > 0

        result = {
            "success": success,
            "extracted_value": value,
            "selector": selector,
            "selector_type": selector_type,
            "attribute": attribute,
        }

        logger.info(f"Pattern test result: success={success}, value='{str(value)[:50]}'")

        return {
            "content": [{
                "type": "text",
                "text": json.dumps(result, indent=2)
            }]
        }

    except Exception as e:
        logger.error(f"Error testing pattern: {e}")
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": False,
                    "error": str(e),
                    "selector": selector
                }, indent=2)
            }],
            "isError": False  # Not a tool error, just pattern failed
        }


@tool(
    "validate_extraction",
    "Validate that extracted data matches expected format for a field type",
    {"field": str, "value": str}
)
async def validate_extraction_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate extracted value is correct format for the field type.

    Args:
        field: The field type (price, title, availability, image)
        value: The extracted value to validate

    Returns:
        Dictionary with validation result including validity and confidence
    """
    field = args["field"].lower()
    value = str(args["value"]).strip()

    logger.info(f"Validating extraction for field '{field}': '{value[:50]}'")

    valid = False
    confidence = 0.0
    reasoning = ""

    try:
        if field == "price":
            # Check if looks like a price
            # Patterns: $10.99, 10.99, £10, €10,99, etc.
            has_number = bool(re.search(r'\d+[.,]?\d*', value))
            has_currency = bool(re.search(r'[$€£¥₹₽]', value))

            # Remove common text and check if numeric remains
            cleaned = re.sub(r'[^0-9.,]', '', value)
            has_decimal = bool(re.search(r'\d+[.,]\d{2}', cleaned))

            valid = has_number

            if has_currency and has_decimal:
                confidence = 0.95
                reasoning = "Contains currency symbol and decimal price"
            elif has_decimal:
                confidence = 0.85
                reasoning = "Contains decimal price pattern"
            elif has_number:
                confidence = 0.70
                reasoning = "Contains numeric value"
            else:
                confidence = 0.0
                reasoning = "No numeric value found"

        elif field == "title":
            # Title should be 5-200 chars, no excessive special chars
            length_ok = 5 <= len(value) <= 200
            not_too_many_symbols = len(re.findall(r'[^\w\s-]', value)) < len(value) * 0.3

            valid = length_ok and not_too_many_symbols

            if valid:
                confidence = 0.90
                reasoning = "Reasonable length and format for product title"
            elif not length_ok:
                confidence = 0.30
                reasoning = f"Length {len(value)} is outside expected range (5-200)"
            else:
                confidence = 0.50
                reasoning = "Too many special characters"

        elif field == "availability":
            # Should contain stock-related keywords
            stock_keywords = [
                'in stock', 'out of stock', 'available', 'unavailable',
                'in-stock', 'out-of-stock', 'sold out', 'low stock',
                'backorder', 'pre-order', 'coming soon'
            ]

            value_lower = value.lower()
            matches = [kw for kw in stock_keywords if kw in value_lower]

            valid = len(matches) > 0

            if valid:
                confidence = 0.90
                reasoning = f"Contains stock keyword: '{matches[0]}'"
            else:
                confidence = 0.20
                reasoning = "No stock-related keywords found"

        elif field == "image":
            # Should be a URL or path to image
            is_url = bool(re.match(r'https?://', value))
            has_image_ext = bool(re.search(r'\.(jpg|jpeg|png|gif|webp)', value, re.I))
            is_data_uri = value.startswith('data:image/')

            valid = is_url or has_image_ext or is_data_uri

            if is_url and has_image_ext:
                confidence = 0.95
                reasoning = "Valid HTTP URL with image extension"
            elif is_url:
                confidence = 0.80
                reasoning = "Valid HTTP URL (extension may be handled dynamically)"
            elif is_data_uri:
                confidence = 0.85
                reasoning = "Data URI for embedded image"
            elif has_image_ext:
                confidence = 0.70
                reasoning = "Has image extension but not full URL"
            else:
                confidence = 0.30
                reasoning = "Doesn't match expected image URL format"

        else:
            # Unknown field type
            valid = len(value) > 0
            confidence = 0.50 if valid else 0.0
            reasoning = f"Unknown field type '{field}', basic non-empty check"

        result = {
            "valid": valid,
            "confidence": confidence,
            "field": field,
            "value": value[:100],  # Truncate for logging
            "reasoning": reasoning
        }

        logger.info(f"Validation result: valid={valid}, confidence={confidence}")

        return {
            "content": [{
                "type": "text",
                "text": json.dumps(result, indent=2)
            }]
        }

    except Exception as e:
        logger.error(f"Error validating extraction: {e}")
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "valid": False,
                    "confidence": 0.0,
                    "field": field,
                    "error": str(e)
                }, indent=2)
            }],
            "isError": True
        }


@tool(
    "validate_pattern_result",
    "Validate complete pattern extraction result with multiple fields",
    {"patterns": dict, "extracted_data": dict}
)
async def validate_pattern_result_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate a complete pattern extraction result.

    Args:
        patterns: The patterns that were used
        extracted_data: The data that was extracted using those patterns

    Returns:
        Dictionary with overall validation result
    """
    patterns = args["patterns"]
    extracted_data = args["extracted_data"]

    logger.info("Validating complete pattern result")

    try:
        validations = {}
        total_confidence = 0.0
        field_count = 0

        for field_name, field_data in extracted_data.items():
            value = field_data.get("value", "")

            # Validate each field
            validation_args = {"field": field_name, "value": value}
            validation_result = await validate_extraction_tool(validation_args)

            # Parse the validation result
            result_text = validation_result["content"][0]["text"]
            validation_info = json.loads(result_text)

            validations[field_name] = validation_info

            if validation_info["valid"]:
                total_confidence += validation_info["confidence"]
                field_count += 1

        overall_confidence = total_confidence / max(len(extracted_data), 1)
        all_valid = all(v["valid"] for v in validations.values())

        result = {
            "success": all_valid,
            "overall_confidence": overall_confidence,
            "field_validations": validations,
            "summary": f"{field_count}/{len(extracted_data)} fields validated successfully"
        }

        logger.info(f"Overall validation: success={all_valid}, confidence={overall_confidence:.2f}")

        return {
            "content": [{
                "type": "text",
                "text": json.dumps(result, indent=2)
            }]
        }

    except Exception as e:
        logger.error(f"Error validating pattern result: {e}")
        return {
            "content": [{
                "type": "text",
                "text": f"Error validating pattern result: {str(e)}"
            }],
            "isError": True
        }
