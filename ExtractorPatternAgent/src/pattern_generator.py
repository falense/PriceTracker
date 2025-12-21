"""Web page fetcher with stealth capabilities and Python extractor generation."""

import structlog
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
from playwright.async_api import async_playwright
from urllib.parse import urlparse

from ExtractorPatternAgent.src.utils.stealth import (
    STEALTH_ARGS,
    apply_stealth,
    get_stealth_context_options,
)


class PatternGenerator:
    """
    Utility class for fetching web pages and generating Python extractor modules.

    This class provides:
    - Stealth web page fetching with Playwright
    - Python module generation from pattern dictionaries

    Note: Automatic heuristic pattern generation has been deprecated.
    Python extractors should be manually written or generated through other means.
    """

    def __init__(self, logger: Optional[structlog.BoundLogger] = None):
        """
        Initialize PatternGenerator.

        Args:
            logger: Optional structlog logger. If not provided, a default logger will be created.
        """
        self.logger = logger or structlog.get_logger()

    async def fetch_page(self, url: str) -> str:
        """
        Fetch page with comprehensive stealth to avoid bot detection.

        Args:
            url: URL to fetch

        Returns:
            HTML content as string
        """
        self.logger.info("fetch_page_started", url=url)

        async with async_playwright() as p:
            # Launch with stealth arguments
            browser = await p.chromium.launch(
                headless=True,  # Required for Docker/server environments
                args=STEALTH_ARGS,
            )

            # Create context with stealth options
            context_options = get_stealth_context_options()
            context = await browser.new_context(**context_options)

            page = await context.new_page()

            # Apply comprehensive stealth script
            await apply_stealth(page)

            try:
                # Navigate with realistic behavior
                await page.goto(url, wait_until="load", timeout=60000)

                # Wait for dynamic content (more realistic timing)
                await page.wait_for_timeout(2000)

                html = await page.content()
                self.logger.info("fetch_page_completed", url=url, html_length=len(html))
                return html
            finally:
                await browser.close()

    async def generate(self, url: str, domain: str) -> Dict[Any, Any]:
        """
        Generate or retrieve pattern metadata for a domain.

        This method checks if a Python extractor module exists for the domain
        and returns its metadata. If no extractor exists, it returns a stub
        indicating that a manual extractor needs to be created.

        Args:
            url: Product URL (for reference)
            domain: Domain name (e.g., "oda.com")

        Returns:
            Dict containing pattern metadata compatible with Pattern.pattern_json
        """
        from datetime import datetime

        # Normalize domain
        normalized_domain = domain.lower().replace("www.", "")

        self.logger.info("generate_pattern_started", url=url, domain=normalized_domain)

        try:
            # Try to import the extractor module and get its metadata
            from ExtractorPatternAgent.generated_extractors import get_parser

            extractor = get_parser(normalized_domain)

            if extractor and hasattr(extractor, "PATTERN_METADATA"):
                metadata = extractor.PATTERN_METADATA

                self.logger.info(
                    "pattern_metadata_retrieved",
                    domain=normalized_domain,
                    confidence=metadata.get("confidence"),
                    fields=metadata.get("fields", []),
                )

                # Return metadata in a format compatible with Pattern.pattern_json
                return {
                    "metadata": {
                        "domain": normalized_domain,
                        "generated_at": metadata.get(
                            "generated_at", datetime.utcnow().isoformat()
                        ),
                        "generator": metadata.get("generator", "python_extractor"),
                        "version": metadata.get("version", "1.0"),
                        "overall_confidence": metadata.get("confidence", 0.0),
                        "fields_found": len(metadata.get("fields", [])),
                        "notes": metadata.get("notes", ""),
                    },
                    "extractor_module": f"generated_extractors.{normalized_domain.replace('.', '_')}",
                    "fields": metadata.get("fields", []),
                }
            else:
                self.logger.warning(
                    "no_extractor_found",
                    domain=normalized_domain,
                    message="No Python extractor module found for domain",
                )

                # Return stub pattern indicating extractor needs to be created
                return {
                    "metadata": {
                        "domain": normalized_domain,
                        "generated_at": datetime.utcnow().isoformat(),
                        "generator": "stub",
                        "version": "0.0",
                        "overall_confidence": 0.0,
                        "fields_found": 0,
                        "notes": f"No extractor module found. Create {normalized_domain.replace('.', '_')}.py in generated_extractors/",
                    },
                    "extractor_module": None,
                    "fields": [],
                }

        except Exception as e:
            self.logger.error(
                "pattern_generation_error",
                domain=normalized_domain,
                error=str(e),
                exc_info=True,
            )
            raise
