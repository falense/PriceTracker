"""Tests for extractor module."""

import pytest

from src.extractor import Extractor
from src.models import ExtractionPattern, FieldPattern, PatternSelector


class TestExtractor:
    """Test Extractor class."""

    def test_extract_css_selector(self):
        """Test CSS selector extraction."""
        html = """
        <html>
            <body>
                <div class="price">$29.99</div>
                <h1 class="title">Test Product</h1>
            </body>
        </html>
        """

        pattern = ExtractionPattern(
            store_domain="test.com",
            patterns={
                "price": FieldPattern(
                    primary=PatternSelector(
                        type="css",
                        selector=".price",
                        confidence=0.9,
                    )
                ),
                "title": FieldPattern(
                    primary=PatternSelector(
                        type="css",
                        selector=".title",
                        confidence=0.9,
                    )
                ),
            },
        )

        extractor = Extractor()
        result = extractor.extract_with_pattern(html, pattern)

        assert result.price.value == "$29.99"
        assert result.price.method == "css"
        assert result.title.value == "Test Product"

    def test_extract_jsonld(self):
        """Test JSON-LD extraction."""
        html = """
        <html>
            <head>
                <script type="application/ld+json">
                {
                    "@context": "https://schema.org",
                    "@type": "Product",
                    "name": "Test Product",
                    "offers": {
                        "@type": "Offer",
                        "price": "29.99",
                        "priceCurrency": "USD"
                    }
                }
                </script>
            </head>
        </html>
        """

        pattern = ExtractionPattern(
            store_domain="test.com",
            patterns={
                "price": FieldPattern(
                    primary=PatternSelector(
                        type="jsonld",
                        selector="offers.price",
                        confidence=0.95,
                    )
                ),
                "title": FieldPattern(
                    primary=PatternSelector(
                        type="jsonld",
                        selector="name",
                        confidence=0.95,
                    )
                ),
            },
        )

        extractor = Extractor()
        result = extractor.extract_with_pattern(html, pattern)

        assert result.price.value == "29.99"
        assert result.price.method == "jsonld"
        assert result.title.value == "Test Product"

    def test_extract_meta_tags(self):
        """Test meta tag extraction."""
        html = """
        <html>
            <head>
                <meta property="og:price:amount" content="29.99">
                <meta property="og:title" content="Test Product">
            </head>
        </html>
        """

        pattern = ExtractionPattern(
            store_domain="test.com",
            patterns={
                "price": FieldPattern(
                    primary=PatternSelector(
                        type="meta",
                        selector="og:price:amount",
                        confidence=0.85,
                    )
                ),
                "title": FieldPattern(
                    primary=PatternSelector(
                        type="meta",
                        selector="og:title",
                        confidence=0.85,
                    )
                ),
            },
        )

        extractor = Extractor()
        result = extractor.extract_with_pattern(html, pattern)

        assert result.price.value == "29.99"
        assert result.price.method == "meta"
        assert result.title.value == "Test Product"

    def test_fallback_chain(self):
        """Test fallback chain when primary fails."""
        html = """
        <html>
            <body>
                <span class="backup-price">$29.99</span>
            </body>
        </html>
        """

        pattern = ExtractionPattern(
            store_domain="test.com",
            patterns={
                "price": FieldPattern(
                    primary=PatternSelector(
                        type="css",
                        selector=".price",  # This will fail
                        confidence=0.9,
                    ),
                    fallbacks=[
                        PatternSelector(
                            type="css",
                            selector=".backup-price",  # This will succeed
                            confidence=0.7,
                        )
                    ],
                )
            },
        )

        extractor = Extractor()
        result = extractor.extract_with_pattern(html, pattern)

        assert result.price.value == "$29.99"
        assert result.price.method == "css"
        assert result.price.confidence == 0.7  # Fallback confidence

    def test_extraction_failure(self):
        """Test when all extraction methods fail."""
        html = """
        <html>
            <body>
                <div>No price here</div>
            </body>
        </html>
        """

        pattern = ExtractionPattern(
            store_domain="test.com",
            patterns={
                "price": FieldPattern(
                    primary=PatternSelector(
                        type="css",
                        selector=".price",
                        confidence=0.9,
                    )
                )
            },
        )

        extractor = Extractor()
        result = extractor.extract_with_pattern(html, pattern)

        assert result.price.value is None
        assert result.price.method is None
        assert result.price.confidence == 0.0
