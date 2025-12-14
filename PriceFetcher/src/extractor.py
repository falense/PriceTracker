"""Apply extraction patterns to HTML."""

import json
from typing import Any, List, Optional

import structlog
from bs4 import BeautifulSoup
from lxml import html as lxml_html

from .models import ExtractionPattern, ExtractionResult, ExtractedField, PatternSelector

logger = structlog.get_logger()


class Extractor:
    """Apply extraction patterns to HTML to extract product data."""

    def extract_with_pattern(
        self, html: str, pattern: ExtractionPattern
    ) -> ExtractionResult:
        """
        Extract data using pattern with fallback support.

        Args:
            html: Page HTML content
            pattern: ExtractionPattern with selectors

        Returns:
            ExtractionResult with extracted fields
        """
        logger.debug("extraction_started", domain=pattern.store_domain)

        results = {}
        for field_name, field_pattern in pattern.patterns.items():
            extracted_field = self._extract_field(html, field_pattern)
            results[field_name] = extracted_field

        extraction = ExtractionResult(**results)
        logger.info(
            "extraction_completed",
            domain=pattern.store_domain,
            price_found=extraction.price.value is not None,
            method=extraction.price.method,
        )

        return extraction

    def _extract_field(
        self, html: str, field_pattern: Any
    ) -> ExtractedField:
        """
        Extract single field with fallback chain.

        Args:
            html: HTML content
            field_pattern: FieldPattern with primary and fallback selectors

        Returns:
            ExtractedField with value and metadata
        """
        # Try primary pattern
        primary = field_pattern.primary
        value = self._apply_selector(html, primary)

        if value:
            return ExtractedField(
                value=value, method=primary.type, confidence=primary.confidence
            )

        # Try fallbacks
        for fallback in field_pattern.fallbacks:
            value = self._apply_selector(html, fallback)
            if value:
                logger.debug("fallback_used", method=fallback.type)
                return ExtractedField(
                    value=value, method=fallback.type, confidence=fallback.confidence
                )

        # All patterns failed
        logger.warning("field_extraction_failed")
        return ExtractedField(value=None, method=None, confidence=0.0)

    def _apply_selector(
        self, html: str, selector_config: PatternSelector
    ) -> Optional[str]:
        """
        Apply a single selector to HTML.

        Args:
            html: HTML content
            selector_config: PatternSelector configuration

        Returns:
            Extracted string value or None if extraction failed
        """
        selector_type = selector_config.type
        selector = selector_config.selector

        try:
            if selector_type == "css":
                return self._extract_css(html, selector, selector_config)
            elif selector_type == "xpath":
                return self._extract_xpath(html, selector, selector_config)
            elif selector_type == "jsonld":
                return self._extract_jsonld(html, selector)
            elif selector_type == "meta":
                return self._extract_meta(html, selector)
            else:
                logger.warning("unknown_selector_type", type=selector_type)
                return None

        except Exception as e:
            logger.debug("selector_failed", type=selector_type, error=str(e))
            return None

    def _extract_css(
        self, html: str, selector: str, config: PatternSelector
    ) -> Optional[str]:
        """
        Extract using CSS selector.

        Args:
            html: HTML content
            selector: CSS selector string
            config: Selector configuration

        Returns:
            Extracted value or None
        """
        soup = BeautifulSoup(html, "html.parser")
        element = soup.select_one(selector)

        if not element:
            return None

        # Check if we need attribute value
        if config.attribute:
            value = element.get(config.attribute)
            return str(value) if value else None

        # Get text content
        text = element.get_text(strip=True)
        return text if text else None

    def _extract_xpath(
        self, html: str, selector: str, config: PatternSelector
    ) -> Optional[str]:
        """
        Extract using XPath selector.

        Args:
            html: HTML content
            selector: XPath expression
            config: Selector configuration

        Returns:
            Extracted value or None
        """
        tree = lxml_html.fromstring(html)
        elements = tree.xpath(selector)

        if not elements:
            return None

        element = elements[0]

        # Check if we need attribute value
        if config.attribute:
            if hasattr(element, "get"):
                value = element.get(config.attribute)
                return str(value) if value else None
            return None

        # Get text content
        if hasattr(element, "text_content"):
            text = element.text_content().strip()
            return text if text else None
        elif isinstance(element, str):
            return element.strip()

        return None

    def _extract_jsonld(self, html: str, path: str) -> Optional[str]:
        """
        Extract from JSON-LD structured data.

        Args:
            html: HTML content
            path: Dot-separated path to value (e.g., "offers.price")

        Returns:
            Extracted value or None
        """
        soup = BeautifulSoup(html, "html.parser")
        scripts = soup.find_all("script", type="application/ld+json")

        for script in scripts:
            if not script.string:
                continue

            try:
                data = json.loads(script.string)

                # Handle @graph wrapper
                if isinstance(data, dict) and "@graph" in data:
                    data = data["@graph"]

                # If data is a list, try each item
                if isinstance(data, list):
                    for item in data:
                        value = self._get_nested(item, path.split("."))
                        if value:
                            return str(value)
                else:
                    # Navigate path like "offers.price"
                    value = self._get_nested(data, path.split("."))
                    if value:
                        return str(value)

            except json.JSONDecodeError as e:
                logger.debug("jsonld_parse_failed", error=str(e))
                continue
            except Exception as e:
                logger.debug("jsonld_extraction_failed", error=str(e))
                continue

        return None

    def _extract_meta(self, html: str, tag_name: str) -> Optional[str]:
        """
        Extract from meta tags.

        Args:
            html: HTML content
            tag_name: Meta tag property or name

        Returns:
            Meta tag content or None
        """
        soup = BeautifulSoup(html, "html.parser")

        # Try property attribute first (Open Graph)
        meta = soup.find("meta", property=tag_name)
        if not meta:
            # Try name attribute
            meta = soup.find("meta", attrs={"name": tag_name})

        if meta:
            content = meta.get("content")
            return str(content) if content else None

        return None

    def _get_nested(self, data: Any, path: List[str]) -> Any:
        """
        Navigate nested dict/list by path.

        Args:
            data: Nested data structure
            path: List of keys to traverse

        Returns:
            Value at path or None if not found
        """
        current = data

        for key in path:
            if isinstance(current, dict) and key in current:
                current = current[key]
            elif isinstance(current, list) and len(current) > 0:
                # If current is a list, try to find the key in the first item
                if isinstance(current[0], dict) and key in current[0]:
                    current = current[0][key]
                else:
                    return None
            else:
                return None

        return current
