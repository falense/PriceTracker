"""Pytest configuration and fixtures."""

import pytest
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def sample_html():
    """Sample HTML for testing."""
    return """
<!DOCTYPE html>
<html>
<head>
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": "Sample Product",
        "image": "https://example.com/product.jpg",
        "description": "A sample product for testing",
        "offers": {
            "@type": "Offer",
            "price": "99.99",
            "priceCurrency": "USD",
            "availability": "https://schema.org/InStock"
        }
    }
    </script>
    <meta property="og:title" content="Sample Product" />
    <meta property="og:price:amount" content="99.99" />
    <meta property="og:price:currency" content="USD" />
</head>
<body>
    <div class="product-container">
        <h1 class="product-title">Sample Product</h1>
        <div class="price-container">
            <span class="price" data-price="99.99">$99.99</span>
        </div>
        <div class="availability in-stock">In Stock</div>
        <img src="https://example.com/product.jpg" class="product-image" alt="Sample Product" />
    </div>
</body>
</html>
"""


@pytest.fixture
def sample_patterns():
    """Sample extraction patterns for testing."""
    return {
        "store_domain": "example.com",
        "patterns": {
            "price": {
                "primary": {
                    "type": "css",
                    "selector": ".price",
                    "confidence": 0.90,
                    "attribute": None
                },
                "fallbacks": [
                    {
                        "type": "css",
                        "selector": "[data-price]",
                        "confidence": 0.85,
                        "attribute": "data-price"
                    }
                ]
            },
            "title": {
                "primary": {
                    "type": "css",
                    "selector": "h1.product-title",
                    "confidence": 0.95
                },
                "fallbacks": []
            },
            "availability": {
                "primary": {
                    "type": "css",
                    "selector": ".availability",
                    "confidence": 0.85
                },
                "fallbacks": []
            },
            "image": {
                "primary": {
                    "type": "css",
                    "selector": "img.product-image",
                    "confidence": 0.90,
                    "attribute": "src"
                },
                "fallbacks": []
            }
        },
        "metadata": {
            "validated_count": 1,
            "confidence_score": 0.90
        }
    }


@pytest.fixture
def test_db_path(tmp_path):
    """Temporary database path for testing."""
    return tmp_path / "test_patterns.db"
