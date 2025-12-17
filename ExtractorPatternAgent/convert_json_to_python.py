#!/usr/bin/env python3
"""
Convert JSON patterns to Python extractor modules.

This script reads JSON pattern files and generates equivalent Python extractors.
"""
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional


def normalize_domain(domain: str) -> str:
    """Normalize domain for module name."""
    return domain.lower().replace('www.', '').replace('.', '_').replace('-', '_')


def generate_selector_code(selector_config: Dict, indent: str = "    ") -> str:
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

    elif selector_type == 'meta':
        # Meta tag
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


def generate_extract_function(field_name: str, field_pattern: Dict, confidence: float) -> str:
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
        func_code += generate_selector_code(primary)

        # For price, add cleaning
        if field_name == 'price' and primary.get('type') == 'css' and not primary.get('json_path'):
            func_code += f"    if elem:\n"
            func_code += f"        return {clean_method}(elem.get_text(strip=True))\n"

    # Fallback selectors
    for i, fallback in enumerate(fallbacks):
        func_code += f"\n    # Fallback {i+1}: {fallback.get('description', fallback.get('selector', 'N/A'))}\n"
        func_code += generate_selector_code(fallback)

        # For price, add cleaning
        if field_name == 'price' and fallback.get('type') == 'css' and not fallback.get('json_path'):
            func_code += f"    if elem:\n"
            func_code += f"        return {clean_method}(elem.get_text(strip=True))\n"

    func_code += "\n    return None\n"

    return func_code


def convert_pattern_to_python(pattern_json: Dict, output_path: Path) -> str:
    """
    Convert JSON pattern to Python module.

    Args:
        pattern_json: Pattern dictionary
        output_path: Where to save the Python file

    Returns:
        Generated Python code
    """
    domain = pattern_json.get('store_domain', 'unknown')
    # Normalize domain (remove www.)
    domain = domain.lower().replace('www.', '')
    patterns = pattern_json.get('patterns', {})
    metadata = pattern_json.get('metadata', {})

    # Start building Python code
    code = f'''"""
Auto-generated extractor for {domain}

Converted from JSON pattern on {datetime.now().isoformat()}
Original confidence: {metadata.get('confidence_score', 0.0):.2f}
"""
import re
from decimal import Decimal
from typing import Optional
from bs4 import BeautifulSoup
from ._base import BaseExtractor


# Metadata (required for discovery)
PATTERN_METADATA = {{
    'domain': '{domain}',
    'generated_at': '{datetime.now().isoformat()}',
    'generator': 'JSON to Python converter',
    'version': '1.0',
    'confidence': {metadata.get('confidence_score', 0.0):.2f},
    'fields': {list(patterns.keys())},
    'notes': 'Converted from JSON pattern'
}}


'''

    # Generate each extract function
    field_order = ['price', 'title', 'image', 'availability', 'article_number', 'model_number']

    for field_name in field_order:
        if field_name in patterns:
            field_pattern = patterns[field_name]
            primary_confidence = field_pattern.get('primary', {}).get('confidence', 0.0)
            code += generate_extract_function(field_name, field_pattern, primary_confidence)
            code += "\n\n"
        else:
            # Generate stub for missing fields
            return_type = 'Optional[Decimal]' if field_name == 'price' else 'Optional[str]'
            code += f'''def extract_{field_name}(soup: BeautifulSoup) -> {return_type}:
    """Extract {field_name} (not available in source pattern)."""
    return None


'''

    # Save to file
    output_path.write_text(code)

    return code


def main():
    """Main conversion script."""
    # Find all JSON pattern files
    repo_root = Path(__file__).parent.parent
    pattern_files = [
        repo_root / 'ExtractorPatternAgent' / 'komplett_patterns.json',
        repo_root / 'ExtractorPatternAgent' / 'power_no_patterns.json',
        repo_root / 'ExtractorPatternAgent' / 'amazon_com_patterns.json',
        repo_root / 'ExtractorPatternAgent' / 'www_netonnet_no_patterns.json',
        # Skip www_komplett_no_patterns.json - has bad selectors, use komplett_patterns.json instead
        # Skip www_example_com_patterns.json - example.com module already exists
    ]

    output_dir = repo_root / 'ExtractorPatternAgent' / 'generated_extractors'
    output_dir.mkdir(exist_ok=True)

    converted = []
    errors = []
    skipped = []

    for pattern_file in pattern_files:
        if not pattern_file.exists():
            continue

        try:
            print(f"Converting: {pattern_file.name}")

            # Read JSON
            with open(pattern_file) as f:
                pattern_json = json.load(f)

            domain = pattern_json.get('store_domain', 'unknown')
            # Normalize domain
            domain = domain.lower().replace('www.', '')
            module_name = normalize_domain(domain)
            output_path = output_dir / f'{module_name}.py'

            # Skip if module already exists (prefer earlier/better patterns)
            if output_path.exists() and 'example' not in module_name:
                print(f"  ⊘ Skipped: {output_path.name} already exists")
                skipped.append((domain, pattern_file.name))
                continue

            # Convert
            code = convert_pattern_to_python(pattern_json, output_path)

            print(f"  ✓ Generated: {output_path.name}")
            print(f"    Domain: {domain}")
            print(f"    Fields: {len(pattern_json.get('patterns', {}))}")

            converted.append((domain, output_path))

        except Exception as e:
            print(f"  ✗ Error: {e}")
            errors.append((pattern_file.name, str(e)))

    print("\n" + "="*60)
    print(f"Conversion complete!")
    print(f"  Converted: {len(converted)}")
    print(f"  Skipped: {len(skipped)}")
    print(f"  Errors: {len(errors)}")

    if converted:
        print("\nGenerated modules:")
        for domain, path in converted:
            print(f"  - {domain:20s} → {path.name}")

    if skipped:
        print("\nSkipped (already exists):")
        for domain, file in skipped:
            print(f"  - {domain:20s} ({file})")

    if errors:
        print("\nErrors:")
        for file, error in errors:
            print(f"  - {file}: {error}")

    return 0 if not errors else 1


if __name__ == '__main__':
    sys.exit(main())
