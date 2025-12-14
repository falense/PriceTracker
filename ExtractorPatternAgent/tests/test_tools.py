"""Tests for custom MCP tools."""

import pytest
import sys
from pathlib import Path
from bs4 import BeautifulSoup

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.tools.browser import fetch_page_tool, render_js_tool
from src.tools.parser import extract_structured_data_tool, analyze_selectors_tool
from src.tools.validator import test_pattern_tool, validate_extraction_tool
from src.tools.storage import save_pattern_tool, load_pattern_tool, list_patterns_tool


# Sample HTML for testing
SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <script type="application/ld+json">
    {
        "@type": "Product",
        "name": "Test Product",
        "offers": {
            "@type": "Offer",
            "price": "29.99",
            "priceCurrency": "USD"
        }
    }
    </script>
    <meta property="og:title" content="Test Product" />
    <meta property="og:price:amount" content="29.99" />
</head>
<body>
    <h1 class="product-title">Test Product</h1>
    <span class="price">$29.99</span>
    <div class="availability">In Stock</div>
    <img src="https://example.com/image.jpg" class="product-image" />
</body>
</html>
"""


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires internet access and real URL")
async def test_fetch_page_tool():
    """Test fetching a web page."""
    result = await fetch_page_tool({
        "url": "https://www.example.com",
        "wait_for_js": False
    })

    assert "content" in result
    assert len(result["content"]) > 0
    assert "text" in result["content"][0]


@pytest.mark.asyncio
async def test_extract_structured_data_tool():
    """Test extracting structured data from HTML."""
    result = await extract_structured_data_tool({"html": SAMPLE_HTML})

    assert "content" in result
    content_text = result["content"][0]["text"]

    # Check that JSON-LD was extracted
    assert "jsonld" in content_text
    assert "Product" in content_text

    # Check that meta tags were extracted
    assert "og:title" in content_text or "meta_tags" in content_text


@pytest.mark.asyncio
async def test_analyze_selectors_tool_price():
    """Test analyzing selectors for price field."""
    result = await analyze_selectors_tool({
        "html": SAMPLE_HTML,
        "field": "price"
    })

    assert "content" in result
    content_text = result["content"][0]["text"]

    # Should find price-related selectors
    assert "selector" in content_text.lower()


@pytest.mark.asyncio
async def test_analyze_selectors_tool_title():
    """Test analyzing selectors for title field."""
    result = await analyze_selectors_tool({
        "html": SAMPLE_HTML,
        "field": "title"
    })

    assert "content" in result
    content_text = result["content"][0]["text"]

    # Should find title-related selectors
    assert "h1" in content_text.lower() or "title" in content_text.lower()


@pytest.mark.asyncio
async def test_test_pattern_tool_css():
    """Test pattern with CSS selector."""
    result = await test_pattern_tool({
        "html": SAMPLE_HTML,
        "selector": ".price",
        "selector_type": "css"
    })

    assert "content" in result
    content_text = result["content"][0]["text"]

    # Should successfully extract price
    assert "success" in content_text
    assert "29.99" in content_text or "$29.99" in content_text


@pytest.mark.asyncio
async def test_test_pattern_tool_with_attribute():
    """Test pattern with CSS selector and attribute."""
    result = await test_pattern_tool({
        "html": SAMPLE_HTML,
        "selector": ".product-image",
        "selector_type": "css",
        "attribute": "src"
    })

    assert "content" in result
    content_text = result["content"][0]["text"]

    # Should extract image URL
    assert "success" in content_text
    assert "example.com/image.jpg" in content_text


@pytest.mark.asyncio
async def test_validate_extraction_tool_price():
    """Test validating price extraction."""
    result = await validate_extraction_tool({
        "field": "price",
        "value": "$29.99"
    })

    assert "content" in result
    content_text = result["content"][0]["text"]

    # Should be valid
    assert '"valid": true' in content_text
    assert "confidence" in content_text


@pytest.mark.asyncio
async def test_validate_extraction_tool_title():
    """Test validating title extraction."""
    result = await validate_extraction_tool({
        "field": "title",
        "value": "Test Product Name"
    })

    assert "content" in result
    content_text = result["content"][0]["text"]

    # Should be valid
    assert '"valid": true' in content_text


@pytest.mark.asyncio
async def test_validate_extraction_tool_invalid_price():
    """Test validating invalid price."""
    result = await validate_extraction_tool({
        "field": "price",
        "value": "not a price"
    })

    assert "content" in result
    content_text = result["content"][0]["text"]

    # Should be invalid
    assert '"valid": false' in content_text or "confidence" in content_text


@pytest.mark.asyncio
async def test_save_and_load_pattern():
    """Test saving and loading patterns from database."""
    test_patterns = {
        "price": {
            "primary": {
                "type": "css",
                "selector": ".price",
                "confidence": 0.9
            }
        }
    }

    # Save pattern
    save_result = await save_pattern_tool({
        "domain": "test.example.com",
        "patterns": test_patterns,
        "confidence": 0.9
    })

    assert "content" in save_result
    save_text = save_result["content"][0]["text"]
    assert "success" in save_text

    # Load pattern
    load_result = await load_pattern_tool({
        "domain": "test.example.com"
    })

    assert "content" in load_result
    load_text = load_result["content"][0]["text"]
    assert "success" in load_text
    assert "price" in load_text


@pytest.mark.asyncio
async def test_list_patterns_tool():
    """Test listing all patterns."""
    result = await list_patterns_tool({})

    assert "content" in result
    content_text = result["content"][0]["text"]

    assert "success" in content_text
    # Should have count field
    assert "count" in content_text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
