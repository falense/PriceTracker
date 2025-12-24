"""
Pattern Management Services.

Provides business logic for pattern management, testing, validation, and history tracking.
Supports both legacy JSON patterns and new Python extractor modules.
"""

import json
import subprocess
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from decimal import Decimal
from urllib.parse import urlparse

from django.utils import timezone
from django.db.models import Max, Q
from django.core.cache import cache

from .models import Pattern, ProductListing, Store

logger = logging.getLogger(__name__)

# Add ExtractorPatternAgent to path for generated_extractors import
REPO_ROOT = Path(__file__).parent.parent.parent
EXTRACTOR_PATH = REPO_ROOT / "ExtractorPatternAgent"
if str(EXTRACTOR_PATH) not in sys.path:
    sys.path.insert(0, str(EXTRACTOR_PATH))


class PatternManagementService:
    """Service for managing patterns (CRUD operations)."""

    @staticmethod
    def get_all_patterns(with_stats=True) -> Dict[str, Any]:
        """
        Get all patterns with optional statistics.

        Args:
            with_stats: Whether to include health statistics

        Returns:
            Dict with patterns list and stats
        """
        patterns = Pattern.objects.all().select_related("store").order_by("domain")

        if not with_stats:
            return {"patterns": patterns, "stats": None}

        # Calculate statistics
        total = patterns.count()
        healthy = patterns.filter(success_rate__gte=0.8).count()
        warning = patterns.filter(success_rate__gte=0.6, success_rate__lt=0.8).count()
        failing = patterns.filter(success_rate__lt=0.6).count()
        pending = patterns.filter(total_attempts=0).count()

        stats = {
            "total": total,
            "healthy": healthy,
            "warning": warning,
            "failing": failing,
            "pending": pending,
        }

        return {"patterns": patterns, "stats": stats}

    @staticmethod
    def get_pattern_detail(domain: str) -> Optional[Pattern]:
        """
        Get single pattern by domain.

        Args:
            domain: Pattern domain

        Returns:
            Pattern instance or None
        """
        try:
            return (
                Pattern.objects.select_related("store")
                .prefetch_related("history")
                .get(domain=domain)
            )
        except Pattern.DoesNotExist:
            return None

    @staticmethod
    def create_pattern(
        domain: str,
        extractor_module: str,
        user,
        change_reason: str = "Initial creation",
    ) -> Tuple[Pattern, bool]:
        """
        Create new pattern with Python extractor.

        Args:
            domain: Pattern domain
            extractor_module: Python extractor module name (e.g., "komplett_no")
            user: User creating the pattern
            change_reason: Reason for creation

        Returns:
            Tuple of (Pattern, created)
        """
        # Normalize domain
        domain = domain.lower().strip()
        if domain.startswith("www."):
            domain = domain[4:]

        # Get default currency for this domain
        from app.utils.currency import get_currency_from_domain

        default_currency, _ = get_currency_from_domain(domain)

        # Get or create store
        store, _ = Store.objects.get_or_create(
            domain=domain,
            defaults={
                "name": domain.split(".")[0].title(),
                "currency": default_currency,
            },
        )

        # Create pattern
        pattern, created = Pattern.objects.update_or_create(
            domain=domain,
            defaults={
                "extractor_module": extractor_module,
                "pattern_json": None,  # No longer using JSON
                "store": store,
                "last_validated": timezone.now(),
            },
        )

        # PatternHistory now stores Python module reference instead of JSON
        # (We may need to update PatternHistory model later to handle Python code)

        return pattern, created

    @staticmethod
    def update_pattern(
        domain: str, extractor_module: str, user, change_reason: str = "Manual edit"
    ) -> Pattern:
        """
        Update existing pattern's extractor module.

        Args:
            domain: Pattern domain
            extractor_module: New extractor module name
            user: User making the update
            change_reason: Reason for update

        Returns:
            Updated Pattern instance
        """
        pattern = Pattern.objects.get(domain=domain)

        # Update pattern
        pattern.extractor_module = extractor_module
        pattern.pattern_json = None  # Clear JSON pattern
        pattern.last_validated = timezone.now()
        pattern.save(
            update_fields=[
                "extractor_module",
                "pattern_json",
                "last_validated",
                "updated_at",
            ]
        )

        return pattern

    @staticmethod
    def delete_pattern(domain: str) -> bool:
        """
        Delete pattern (hard delete).

        Args:
            domain: Pattern domain

        Returns:
            True if deleted, False if not found
        """
        try:
            pattern = Pattern.objects.get(domain=domain)
            pattern.delete()
            return True
        except Pattern.DoesNotExist:
            return False

class PatternTestService:
    """Service for testing and validating patterns."""

    @staticmethod
    def extract_with_python_module(html: str, extractor_module: str) -> Dict[str, Any]:
        """
        Extract data using a Python extractor module.

        Args:
            html: HTML content
            extractor_module: Module name (e.g., "generated_extractors.komplett_no")

        Returns:
            Dict with extracted field data and extraction errors/warnings
        """
        try:
            # Import generated_extractors
            from generated_extractors import extract_from_html

            # Use the discovery API
            domain = extractor_module.replace("generated_extractors.", "")
            results = extract_from_html(domain, html)

            if results is None:
                logger.warning(
                    f"Python extractor {extractor_module} returned no results"
                )
                return {
                    "fields": {},
                    "errors": ["Extractor returned no results"],
                    "warnings": [],
                }

            # Convert ExtractorResult to dict format compatible with existing code
            field_names = [
                "price",
                "title",
                "image",
                "availability",
                "article_number",
                "model_number",
            ]
            formatted_results = {}
            for field_name in field_names:
                value = getattr(results, field_name, None)
                if value is not None:
                    formatted_results[field_name] = {
                        "value": str(value),
                        "method": "python_extractor",
                        "confidence": 1.0,  # Python extractors don't have confidence scores
                        "selector": extractor_module,
                    }
                else:
                    formatted_results[field_name] = {
                        "value": None,
                        "error": "Extractor returned None",
                    }

            return {
                "fields": formatted_results,
                "errors": list(getattr(results, "errors", []) or []),
                "warnings": list(getattr(results, "warnings", []) or []),
            }

        except ImportError as e:
            logger.error(f"Failed to import Python extractor {extractor_module}: {e}")
            return {
                "fields": {},
                "errors": [f"Extractor import failed: {e}"],
                "warnings": [],
            }
        except Exception as e:
            logger.exception(f"Python extractor {extractor_module} failed: {e}")
            return {
                "fields": {},
                "errors": [str(e)],
                "warnings": [],
            }

    @staticmethod
    def test_pattern_against_url(
        url: str, extractor_module: str, use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Test Python extractor against a URL.

        Args:
            url: URL to test against
            extractor_module: Python module name (e.g., "komplett_no")
            use_cache: Whether to use cached HTML

        Returns:
            Dict with test results and extraction data
        """
        try:
            # 1. Fetch HTML
            html, metadata = PatternTestService.fetch_html(url, use_cache=use_cache)

            # 2. Extract data using Python extractor
            extraction_payload = PatternTestService.extract_with_python_module(
                html, extractor_module
            )
            extraction_result = extraction_payload.get("fields", {})

            # 3. Validate results
            validation = PatternTestService._validate_extraction(
                extraction_result,
                extraction_payload.get("errors", []),
                extraction_payload.get("warnings", []),
            )

            return {
                "success": (
                    extraction_result.get("price", {}).get("value") is not None
                    and not extraction_payload.get("errors")
                ),
                "extraction": extraction_result,
                "errors": validation["errors"],
                "warnings": validation["warnings"],
                "metadata": metadata,
            }

        except Exception as e:
            logger.exception(f"Pattern test failed for {url}: {e}")
            return {
                "success": False,
                "extraction": {},
                "errors": [str(e)],
                "warnings": [],
                "metadata": {},
            }

    @staticmethod
    def fetch_html(url: str, use_cache: bool = True) -> Tuple[str, Dict]:
        """
        Fetch HTML from URL using stealth browser.

        Args:
            url: URL to fetch
            use_cache: Whether to use cached result

        Returns:
            Tuple of (html, metadata)
        """
        # Check cache first
        if use_cache:
            cache_key = f"pattern_test_html_{url}"
            cached = cache.get(cache_key)
            if cached:
                logger.info(f"Using cached HTML for {url}")
                return cached["html"], cached["metadata"]

        # Validate URL
        parsed = urlparse(url)
        if parsed.scheme not in ["http", "https"]:
            raise ValueError("URL must use HTTP or HTTPS")

        # Fetch using Playwright browser automation (same as PriceFetcher)
        import asyncio
        from time import time
        from playwright.async_api import async_playwright

        async def fetch_with_browser(url: str) -> tuple:
            """Fetch HTML using Playwright browser."""
            start_time = time()

            async with async_playwright() as p:
                # Launch browser with stealth mode
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--disable-features=IsolateOrigins,site-per-process",
                    ],
                )

                # Create context with realistic options
                context = await browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                )

                page = await context.new_page()

                # Navigate and wait for network idle (JavaScript rendering)
                await page.goto(url, wait_until="networkidle", timeout=30000)

                # Get rendered HTML
                html = await page.content()

                await browser.close()

                duration_ms = int((time() - start_time) * 1000)
                return html, duration_ms

        # Run async fetch in sync context
        html, duration_ms = asyncio.run(fetch_with_browser(url))

        metadata = {
            "fetch_time_ms": duration_ms,
            "html_size": len(html),
            "status_code": 200,
            "content_type": "text/html",
        }

        # Cache for 5 minutes
        if use_cache:
            cache_key = f"pattern_test_html_{url}"
            cache.set(cache_key, {"html": html, "metadata": metadata}, 300)

        return html, metadata

    @staticmethod
    def _validate_extraction(
        extraction: Dict,
        extraction_errors: Optional[List[str]] = None,
        extraction_warnings: Optional[List[str]] = None,
    ) -> Dict[str, List[str]]:
        """Validate extraction results."""
        errors = list(extraction_errors or [])
        warnings = list(extraction_warnings or [])

        # Check required fields
        if not extraction.get("price", {}).get("value"):
            errors.append("Price not found (required field)")

        if not extraction.get("title", {}).get("value"):
            warnings.append("Title not found")

        if not extraction.get("image", {}).get("value"):
            warnings.append("Image not found")

        return {"errors": errors, "warnings": warnings}

    @staticmethod
    def test_pattern_for_visualization(pattern: Pattern) -> Dict[str, Any]:
        """
        Test Python extractor pattern for visualization page.

        Args:
            pattern: Pattern instance to test

        Returns:
            Dict with {success, test_url, extraction_results, errors, warnings, metadata}
        """
        # Get test URL from most recent ProductListing
        test_url = (
            ProductListing.objects.filter(store__domain=pattern.domain, active=True)
            .order_by("-last_checked")
            .values_list("url", flat=True)
            .first()
        )

        if not test_url:
            return {
                "success": False,
                "error": "No active product listings for this domain",
                "test_url": None,
                "extraction_results": {},
            }

        if not pattern.extractor_module:
            return {
                "success": False,
                "error": "Pattern does not have a Python extractor module configured",
                "test_url": test_url,
                "extraction_results": {},
            }

        try:
            # Fetch HTML
            html, metadata = PatternTestService.fetch_html(test_url, use_cache=True)

            # Extract using Python module
            extraction_payload = PatternTestService.extract_with_python_module(
                html, pattern.extractor_module
            )
            extraction_results = extraction_payload.get("fields", {})

            return {
                "success": bool(extraction_results)
                and not extraction_payload.get("errors"),
                "test_url": test_url,
                "extraction_results": extraction_results,
                "errors": extraction_payload.get("errors", []),
                "warnings": extraction_payload.get("warnings", []),
                "metadata": metadata,
            }

        except Exception as e:
            logger.exception(f"Error testing pattern for visualization: {e}")
            return {
                "success": False,
                "error": f"Test failed: {str(e)}",
                "test_url": test_url,
                "extraction_results": {},
            }
