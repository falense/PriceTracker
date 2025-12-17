"""Tests for extractor registry and discovery system."""
import pytest
from decimal import Decimal
from bs4 import BeautifulSoup

from ExtractorPatternAgent.generated_extractors import (
    get_parser,
    has_parser,
    extract_from_html,
    list_available_extractors,
    ExtractorResult,
    BaseExtractor,
)


class TestBaseExtractor:
    """Test BaseExtractor utility methods."""

    def test_clean_price_norwegian_format(self):
        """Test Norwegian price format: '1 990,-'"""
        result = BaseExtractor.clean_price("1 990,-")
        assert result == Decimal("1990")

    def test_clean_price_european_format(self):
        """Test European price format: '1.990,50'"""
        result = BaseExtractor.clean_price("1.990,50")
        assert result == Decimal("1990.50")

    def test_clean_price_us_format(self):
        """Test US price format: '1,990.50'"""
        result = BaseExtractor.clean_price("1,990.50")
        assert result == Decimal("1990.50")

    def test_clean_price_with_currency(self):
        """Test price with currency symbols."""
        assert BaseExtractor.clean_price("$199.99") == Decimal("199.99")
        assert BaseExtractor.clean_price("€99,50") == Decimal("99.50")
        assert BaseExtractor.clean_price("199 kr") == Decimal("199")

    def test_clean_price_invalid(self):
        """Test invalid price returns None."""
        assert BaseExtractor.clean_price("") is None
        assert BaseExtractor.clean_price("N/A") is None
        assert BaseExtractor.clean_price(None) is None

    def test_clean_text(self):
        """Test text cleaning."""
        assert BaseExtractor.clean_text("  Hello World  ") == "Hello World"
        assert BaseExtractor.clean_text("Hello\n\nWorld") == "Hello World"
        assert BaseExtractor.clean_text("") is None
        assert BaseExtractor.clean_text(None) is None

    def test_extract_json_field(self):
        """Test JSON field extraction."""
        data = {
            'tracking': {
                'item': {
                    'price': 199.99,
                    'name': 'Product'
                }
            }
        }

        assert BaseExtractor.extract_json_field(data, "tracking.item.price") == 199.99
        assert BaseExtractor.extract_json_field(data, "tracking.item.name") == "Product"
        assert BaseExtractor.extract_json_field(data, "tracking.invalid") is None
        assert BaseExtractor.extract_json_field(data, "") is None


class TestExtractorRegistry:
    """Test extractor discovery and registry."""

    def test_get_parser_exists(self):
        """Test getting parser for existing domain."""
        parser = get_parser("example.com")
        assert parser is not None
        assert hasattr(parser, 'extract_price')
        assert hasattr(parser, 'PATTERN_METADATA')

    def test_get_parser_not_exists(self):
        """Test getting parser for non-existent domain."""
        parser = get_parser("nonexistent-domain.com")
        assert parser is None

    def test_get_parser_normalizes_domain(self):
        """Test domain normalization (removes www., lowercase)."""
        parser1 = get_parser("example.com")
        parser2 = get_parser("www.example.com")
        parser3 = get_parser("EXAMPLE.COM")

        assert parser1 is not None
        assert parser1 is parser2
        assert parser1 is parser3

    def test_has_parser(self):
        """Test checking parser existence."""
        assert has_parser("example.com") is True
        assert has_parser("nonexistent.com") is False

    def test_list_available_extractors(self):
        """Test listing all available extractors."""
        extractors = list_available_extractors()

        assert isinstance(extractors, dict)
        assert "example.com" in extractors
        assert "domain" in extractors["example.com"]
        assert "confidence" in extractors["example.com"]


class TestExtractorResult:
    """Test ExtractorResult class."""

    def test_result_initialization(self):
        """Test result initialization."""
        result = ExtractorResult("example.com")

        assert result.domain == "example.com"
        assert result.price is None
        assert result.title is None
        assert result.errors == []
        assert result.warnings == []

    def test_result_success(self):
        """Test success property."""
        result = ExtractorResult("example.com")

        # No price = not success
        assert result.success is False

        # Price but with errors = not success
        result.price = Decimal("199.99")
        result.errors.append("Some error")
        assert result.success is False

        # Price and no errors = success
        result.errors = []
        assert result.success is True

    def test_result_to_dict(self):
        """Test converting result to dict."""
        result = ExtractorResult("example.com")
        result.price = Decimal("199.99")
        result.title = "Test Product"
        result.warnings.append("Minor issue")

        data = result.to_dict()

        assert data['domain'] == "example.com"
        assert data['price'] == "199.99"
        assert data['title'] == "Test Product"
        assert data['warnings'] == ["Minor issue"]

    def test_result_repr(self):
        """Test string representation."""
        result = ExtractorResult("example.com")
        result.price = Decimal("199.99")

        repr_str = repr(result)
        assert "example.com" in repr_str
        assert "SUCCESS" in repr_str
        assert "199.99" in repr_str


class TestExtractFromHTML:
    """Test high-level extract_from_html API."""

    def test_extract_no_parser(self):
        """Test extraction with no parser available."""
        html = "<html><body>Test</body></html>"
        result = extract_from_html("nonexistent.com", html)

        assert result.success is False
        assert len(result.errors) > 0
        assert "No extractor found" in result.errors[0]

    def test_extract_invalid_html(self):
        """Test extraction with invalid HTML."""
        # Note: BeautifulSoup is very forgiving, so this tests the try/except
        result = extract_from_html("example.com", None)

        # Should handle gracefully
        assert result.success is False

    def test_extract_success(self):
        """Test successful extraction."""
        html = """
        <html>
        <head>
            <meta property="og:title" content="Test Product">
            <meta property="og:image" content="https://example.com/image.jpg">
        </head>
        <body>
            <div class="product-price">$199.99</div>
            <h1 class="product-title">Test Product</h1>
            <div class="stock-status">In Stock</div>
            <span itemprop="sku">SKU123</span>
            <span class="model-number">MODEL-XYZ</span>
        </body>
        </html>
        """

        result = extract_from_html("example.com", html)

        assert result.success is True
        assert result.price == Decimal("199.99")
        assert result.title == "Test Product"
        assert result.availability == "In Stock"
        assert result.article_number == "SKU123"
        assert result.model_number == "MODEL-XYZ"

    def test_extract_partial_success(self):
        """Test extraction with some fields missing."""
        html = """
        <html>
        <body>
            <div class="product-price">$199.99</div>
        </body>
        </html>
        """

        result = extract_from_html("example.com", html)

        # Should succeed (price found)
        assert result.success is True
        assert result.price == Decimal("199.99")

        # But should have warnings for missing fields
        assert len(result.warnings) > 0
        assert any("Title not found" in w for w in result.warnings)

    def test_extract_handles_extraction_errors(self):
        """Test that extraction handles individual field errors gracefully."""
        html = "<html><body><div class='product-price'>invalid</div></body></html>"

        result = extract_from_html("example.com", html)

        # Price extraction should fail gracefully
        assert result.price is None
        # Should have warnings or errors
        assert len(result.warnings) > 0 or len(result.errors) > 0


class TestExampleExtractor:
    """Test the example.com extractor specifically."""

    def test_extract_price(self):
        """Test price extraction."""
        from ExtractorPatternAgent.generated_extractors.example_com import extract_price

        html = '<div class="product-price">$199.99</div>'
        soup = BeautifulSoup(html, 'html.parser')

        price = extract_price(soup)
        assert price == Decimal("199.99")

    def test_extract_price_fallback(self):
        """Test price extraction fallback."""
        from ExtractorPatternAgent.generated_extractors.example_com import extract_price

        html = '<div data-price="299.99">Product</div>'
        soup = BeautifulSoup(html, 'html.parser')

        price = extract_price(soup)
        assert price == Decimal("299.99")

    def test_extract_title(self):
        """Test title extraction."""
        from ExtractorPatternAgent.generated_extractors.example_com import extract_title

        html = '<h1 class="product-title">Test Product</h1>'
        soup = BeautifulSoup(html, 'html.parser')

        title = extract_title(soup)
        assert title == "Test Product"

    def test_metadata(self):
        """Test extractor metadata."""
        from ExtractorPatternAgent.generated_extractors.example_com import PATTERN_METADATA

        assert PATTERN_METADATA['domain'] == 'example.com'
        assert 'confidence' in PATTERN_METADATA
        assert 'fields' in PATTERN_METADATA
        assert len(PATTERN_METADATA['fields']) == 6
