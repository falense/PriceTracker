"""
Runtime extractor registry with automatic discovery.

This module provides a clean API for PriceFetcher to retrieve
domain-specific extractors without hardcoding.

Example:
    >>> from ExtractorPatternAgent.generated_extractors import get_parser, extract_from_html
    >>>
    >>> # Get parser for domain
    >>> parser = get_parser("komplett.no")
    >>> if parser:
    >>>     soup = BeautifulSoup(html, 'html.parser')
    >>>     price = parser.extract_price(soup)
    >>>
    >>> # Or use high-level API
    >>> result = extract_from_html("komplett.no", html)
    >>> if result.success:
    >>>     print(f"Price: {result.price}")
"""

import importlib
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from bs4 import BeautifulSoup

from ._base import ExtractorProtocol, ExtractorResult, BaseExtractor

logger = logging.getLogger(__name__)


class ExtractorRegistry:
    """Registry for runtime extractor discovery."""

    def __init__(self):
        self._extractors: Dict[str, Any] = {}
        self._loaded = False

    def discover(self):
        """
        Discover all extractor modules in this package.

        Scans the generated_extractors directory for Python modules
        and registers them by domain.
        """
        if self._loaded:
            return

        logger.debug("Discovering extractor modules...")

        # Get package directory
        package_dir = Path(__file__).parent

        # Scan for .py files (excluding __init__.py and _base.py)
        for file_path in package_dir.glob("*.py"):
            module_name = file_path.stem

            # Skip private/special modules
            if module_name.startswith("_"):
                continue

            try:
                # Import module
                module = importlib.import_module(
                    f"ExtractorPatternAgent.generated_extractors.{module_name}"
                )

                # Extract domain from metadata
                if hasattr(module, "PATTERN_METADATA"):
                    domain = module.PATTERN_METADATA.get("domain")
                    if domain:
                        self._extractors[domain] = module
                        logger.debug(f"Registered extractor for {domain}")
                    else:
                        logger.warning(
                            f"Module {module_name} has PATTERN_METADATA but no 'domain' key"
                        )
                else:
                    logger.warning(
                        f"Module {module_name} missing PATTERN_METADATA, skipping"
                    )

            except Exception as e:
                logger.error(f"Failed to load extractor {module_name}: {e}")

        self._loaded = True
        logger.info(f"Discovered {len(self._extractors)} extractors")

    def get_extractor(self, domain: str) -> Optional[Any]:
        """
        Get extractor module for a domain.

        Args:
            domain: Store domain (e.g., "komplett.no", "amazon.com")

        Returns:
            Extractor module or None if not found
        """
        if not self._loaded:
            self.discover()

        # Normalize domain (remove www., lowercase)
        domain = domain.lower().replace("www.", "")

        return self._extractors.get(domain)

    def has_extractor(self, domain: str) -> bool:
        """
        Check if extractor exists for domain.

        Args:
            domain: Store domain

        Returns:
            True if extractor exists
        """
        return self.get_extractor(domain) is not None

    def list_domains(self) -> List[str]:
        """
        Get list of all registered domains.

        Returns:
            List of domain strings
        """
        if not self._loaded:
            self.discover()
        return list(self._extractors.keys())

    def reload(self):
        """
        Reload all extractors (useful in development).

        Note: This clears the registry and re-discovers all modules.
        """
        logger.info("Reloading extractors...")

        # Reload modules that were previously loaded
        for domain, module in list(self._extractors.items()):
            try:
                importlib.reload(module)
                logger.info(f"Reloaded extractor for {domain}")
            except Exception as e:
                logger.error(f"Failed to reload {domain}: {e}")

        # Clear cache
        self._extractors.clear()
        self._loaded = False

        # Re-discover
        self.discover()


# Global singleton registry
_registry = ExtractorRegistry()


def get_parser(domain: str) -> Optional[Any]:
    """
    Get parser for a domain.

    This is the main entry point for retrieving domain-specific extractors.

    Args:
        domain: Store domain (e.g., "komplett.no")

    Returns:
        Extractor module with extract_* methods, or None if not found

    Example:
        >>> parser = get_parser("komplett.no")
        >>> if parser:
        >>>     soup = BeautifulSoup(html, 'html.parser')
        >>>     price = parser.extract_price(soup)
        >>> else:
        >>>     print("No extractor found")
    """
    return _registry.get_extractor(domain)


def has_parser(domain: str) -> bool:
    """
    Check if parser exists for domain.

    Args:
        domain: Store domain

    Returns:
        True if extractor exists

    Example:
        >>> if has_parser("komplett.no"):
        >>>     result = extract_from_html("komplett.no", html)
    """
    return _registry.has_extractor(domain)


def extract_from_html(domain: str, html: str) -> ExtractorResult:
    """
    High-level extraction API.

    Extracts all fields from HTML using the domain's extractor.
    Handles errors gracefully and returns detailed results.

    Args:
        domain: Store domain
        html: HTML content to extract from

    Returns:
        ExtractorResult with all extracted fields and any errors/warnings

    Example:
        >>> result = extract_from_html("komplett.no", html)
        >>> if result.success:
        >>>     print(f"Price: {result.price}")
        >>>     print(f"Title: {result.title}")
        >>> else:
        >>>     print(f"Errors: {result.errors}")
    """
    result = ExtractorResult(domain)

    # Get extractor
    extractor = get_parser(domain)
    if not extractor:
        result.errors.append(f"No extractor found for domain: {domain}")
        return result

    # Parse HTML
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception as e:
        result.errors.append(f"Failed to parse HTML: {e}")
        return result

    # Extract all fields (with error handling per field)
    try:
        result.price = extractor.extract_price(soup)
        if not result.price:
            result.warnings.append("Price not found")
    except Exception as e:
        result.errors.append(f"Price extraction failed: {e}")
        logger.exception(f"Price extraction error for {domain}")

    try:
        result.title = extractor.extract_title(soup)
        if not result.title:
            result.warnings.append("Title not found")
    except Exception as e:
        result.warnings.append(f"Title extraction failed: {e}")

    try:
        result.image = extractor.extract_image(soup)
    except Exception as e:
        result.warnings.append(f"Image extraction failed: {e}")

    try:
        result.availability = extractor.extract_availability(soup)
    except Exception as e:
        result.warnings.append(f"Availability extraction failed: {e}")

    try:
        result.article_number = extractor.extract_article_number(soup)
    except Exception as e:
        result.warnings.append(f"Article number extraction failed: {e}")

    try:
        result.model_number = extractor.extract_model_number(soup)
    except Exception as e:
        result.warnings.append(f"Model number extraction failed: {e}")

    try:
        result.currency = extractor.extract_currency(soup)
    except Exception as e:
        result.warnings.append(f"Currency extraction failed: {e}")

    return result


def list_available_extractors() -> Dict[str, Dict[str, Any]]:
    """
    List all available extractors with metadata.

    Returns:
        Dict mapping domain to metadata

    Example:
        >>> extractors = list_available_extractors()
        >>> for domain, meta in extractors.items():
        >>>     print(f"{domain}: confidence={meta['confidence']}")
    """
    _registry.discover()

    result = {}
    for domain in _registry.list_domains():
        extractor = _registry.get_extractor(domain)
        if extractor and hasattr(extractor, "PATTERN_METADATA"):
            result[domain] = extractor.PATTERN_METADATA

    return result


def reload_extractors():
    """
    Reload all extractors (development only).

    Warning: This should only be used in development environments
    where hot-reloading is needed.
    """
    _registry.reload()


# Public API
__all__ = [
    "get_parser",
    "has_parser",
    "extract_from_html",
    "list_available_extractors",
    "reload_extractors",
    "ExtractorResult",
    "BaseExtractor",
]
