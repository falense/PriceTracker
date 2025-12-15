"""Main price fetcher orchestrator."""

import asyncio
import time
from datetime import datetime
from typing import Dict, List, Optional

from playwright.async_api import async_playwright
import structlog

from .extractor import Extractor
from .models import ExtractionResult, FetchResult, FetchSummary, Product
from .pattern_loader import PatternLoader
from .storage import PriceStorage
from .validator import Validator
from .stealth import (
    STEALTH_ARGS,
    apply_stealth,
    get_stealth_context_options,
    get_enhanced_context_options,
    simulate_human_behavior,
    wait_for_stable_load,
)

logger = structlog.get_logger()


class PriceFetcher:
    """Main price fetcher orchestrator."""

    def __init__(
        self,
        db_path: str = "../db.sqlite3",
        request_delay: float = 2.0,
        timeout: float = 30.0,
        max_retries: int = 3,
        user_agent: Optional[str] = None,
        min_confidence: float = 0.6,
        browser_timeout: float = 60.0,
        wait_for_js: bool = True,
        domain_delays: Optional[Dict[str, float]] = None,
    ):
        """
        Initialize price fetcher.

        Args:
            db_path: Path to shared SQLite database
            request_delay: Delay between requests (seconds)
            timeout: Browser operation timeout (seconds)
            max_retries: Maximum retry attempts
            user_agent: Kept for backwards compatibility (not used - stealth UA applied)
            min_confidence: Minimum confidence threshold for validation
            browser_timeout: Navigation timeout for browser (seconds)
            wait_for_js: Whether to wait for JavaScript to finish rendering
            domain_delays: Per-domain request delays (seconds)
        """
        self.request_delay = request_delay
        self.timeout = timeout
        self.max_retries = max_retries
        self.browser_timeout = browser_timeout * 1000  # Convert to milliseconds
        self.wait_for_js = wait_for_js
        self.domain_delays = domain_delays or {}

        # Initialize components
        self.pattern_loader = PatternLoader(db_path)
        self.extractor = Extractor()
        self.validator = Validator(min_confidence=min_confidence)
        self.storage = PriceStorage(db_path)

        logger.info(
            "fetcher_initialized",
            request_delay=request_delay,
            timeout=timeout,
            max_retries=max_retries,
            browser_timeout=browser_timeout,
            wait_for_js=wait_for_js,
        )

    async def fetch_all(self) -> FetchSummary:
        """
        Fetch prices for all products due for update.

        Returns:
            FetchSummary with results
        """
        started_at = datetime.utcnow()
        logger.info("fetch_run_started")

        # Get products that need checking
        products = self.storage.get_products_to_fetch()

        if not products:
            logger.info("no_products_to_fetch")
            return FetchSummary(
                total=0,
                success=0,
                failed=0,
                products=[],
                started_at=started_at,
                completed_at=datetime.utcnow(),
                duration_seconds=0.0,
            )

        # Group by domain for rate limiting
        by_domain: Dict[str, List[Product]] = {}
        for product in products:
            if product.domain not in by_domain:
                by_domain[product.domain] = []
            by_domain[product.domain].append(product)

        logger.info(
            "products_grouped",
            total_products=len(products),
            domains=len(by_domain),
        )

        # Fetch products by domain
        fetch_results: List[FetchResult] = []
        success_count = 0
        failed_count = 0

        for domain, domain_products in by_domain.items():
            logger.info("processing_domain", domain=domain, products=len(domain_products))

            # Load pattern for domain
            pattern = self.pattern_loader.load_pattern(domain)
            if not pattern:
                logger.warning("no_pattern_found", domain=domain)
                # Mark all products as failed
                for product in domain_products:
                    result = FetchResult(
                        product_id=product.product_id,
                        url=product.url,
                        success=False,
                        error=f"No pattern found for domain {domain}",
                        duration_ms=0,
                    )
                    fetch_results.append(result)
                    failed_count += 1
                continue

            # Fetch each product with rate limiting
            for i, product in enumerate(domain_products):
                result = await self.fetch_product(product, pattern)
                fetch_results.append(result)

                if result.success:
                    success_count += 1
                else:
                    failed_count += 1

                # Rate limiting: wait between requests (except for last product)
                if i < len(domain_products) - 1:
                    # Use domain-specific delay if configured, otherwise use default
                    delay = self.domain_delays.get(domain, self.request_delay)
                    logger.debug("rate_limit_delay", domain=domain, delay=delay)
                    await asyncio.sleep(delay)

        completed_at = datetime.utcnow()
        duration = (completed_at - started_at).total_seconds()

        summary = FetchSummary(
            total=len(products),
            success=success_count,
            failed=failed_count,
            products=fetch_results,
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=duration,
        )

        logger.info(
            "fetch_run_completed",
            total=summary.total,
            success=summary.success,
            failed=summary.failed,
            duration=summary.duration_seconds,
        )

        return summary

    async def fetch_product(
        self,
        product: Product,
        pattern: Optional[object] = None,
    ) -> FetchResult:
        """
        Fetch price for single product.

        Args:
            product: Product to fetch
            pattern: Extraction pattern (loaded automatically if not provided)

        Returns:
            FetchResult with extraction and validation
        """
        start_time = time.time()
        product_id = product.product_id
        url = product.url

        logger.info("fetching_product", product_id=product_id, url=url)

        try:
            # Load pattern if not provided
            if pattern is None:
                pattern = self.pattern_loader.load_pattern(product.domain)
                if not pattern:
                    raise ValueError(f"No pattern found for domain {product.domain}")

            # Fetch HTML
            html = await self._fetch_html(url)

            # Extract data
            extraction = self.extractor.extract_with_pattern(html, pattern)

            # Get previous extraction for comparison
            previous = self.storage.get_latest_price(
                product_id=product_id, listing_id=product.listing_id
            )
            previous_extraction = None
            if previous and previous.get("extracted_data"):
                try:
                    previous_extraction = ExtractionResult(
                        **previous["extracted_data"]
                    )
                except Exception as e:
                    logger.debug("previous_extraction_parse_failed", error=str(e))

            # Validate extraction
            validation = self.validator.validate_extraction(
                extraction, previous_extraction
            )

            # Store if valid
            if validation.valid:
                self.storage.save_price(
                    product_id, extraction, validation, url, listing_id=product.listing_id
                )
                self.storage.update_pattern_stats(product.domain, success=True)
            else:
                self.storage.update_pattern_stats(product.domain, success=False)

            # Log fetch attempt
            duration_ms = int((time.time() - start_time) * 1000)
            self.storage.log_fetch(
                product_id=product_id,
                success=validation.valid,
                extraction_method=extraction.price.method,
                errors=validation.errors,
                warnings=validation.warnings,
                duration_ms=duration_ms,
                listing_id=product.listing_id,
            )

            return FetchResult(
                product_id=product_id,
                url=url,
                success=validation.valid,
                extraction=extraction,
                validation=validation,
                duration_ms=duration_ms,
            )

        except Exception as e:
            # Log failure
            duration_ms = int((time.time() - start_time) * 1000)
            error_msg = str(e)

            logger.error(
                "product_fetch_failed",
                product_id=product_id,
                url=url,
                error=error_msg,
            )

            self.storage.log_fetch(
                product_id,
                success=False,
                errors=[error_msg],
                duration_ms=duration_ms,
            )

            # Update pattern stats on failure
            try:
                self.storage.update_pattern_stats(product.domain, success=False)
            except Exception:
                pass

            return FetchResult(
                product_id=product_id,
                url=url,
                success=False,
                error=error_msg,
                duration_ms=duration_ms,
            )

    async def _fetch_html(self, url: str) -> str:
        """
        Fetch HTML from URL using Playwright with retry logic.

        Args:
            url: Product URL to fetch

        Returns:
            HTML content as string

        Raises:
            Exception: If fetch fails after retries
        """
        last_error = None

        # Extract domain for enhanced stealth detection
        from urllib.parse import urlparse
        domain = urlparse(url).netloc.lower()

        # Difficult sites that need enhanced stealth
        difficult_sites = ['amazon.com', 'amazon.co.uk', 'amazon.de', 'walmart.com']
        use_enhanced_stealth = any(site in domain for site in difficult_sites)

        for attempt in range(self.max_retries):
            browser = None
            try:
                logger.debug(
                    "browser_fetch_starting",
                    url=url,
                    attempt=attempt + 1,
                    enhanced_stealth=use_enhanced_stealth,
                )

                async with async_playwright() as p:
                    # Launch browser with stealth args
                    browser = await p.chromium.launch(
                        headless=True,
                        args=STEALTH_ARGS
                    )

                    # Create context with stealth options (enhanced for difficult sites)
                    if use_enhanced_stealth:
                        context_options = get_enhanced_context_options(domain)
                        logger.debug("using_enhanced_stealth", domain=domain)
                    else:
                        context_options = get_stealth_context_options()

                    context = await browser.new_context(**context_options)

                    # Create page and apply stealth
                    page = await context.new_page()
                    await apply_stealth(page)

                    # Navigate (wait for JS if configured)
                    wait_until = "load" if self.wait_for_js else "domcontentloaded"
                    await page.goto(
                        url,
                        wait_until=wait_until,
                        timeout=self.browser_timeout
                    )

                    # For difficult sites, simulate human behavior
                    if use_enhanced_stealth:
                        await wait_for_stable_load(page, timeout=30000)
                        await simulate_human_behavior(page, domain)
                        logger.debug("human_behavior_simulated", domain=domain)

                    # Get rendered HTML
                    html = await page.content()

                    logger.debug(
                        "browser_fetch_success",
                        url=url,
                        attempt=attempt + 1,
                        html_length=len(html),
                    )

                    await browser.close()
                    return html

            except Exception as e:
                last_error = e
                error_msg = str(e)

                # Close browser on error
                if browser:
                    try:
                        await browser.close()
                    except Exception:
                        pass

                # Categorize errors for retry logic
                should_retry = True

                # DNS/connection errors - don't retry
                if "ERR_NAME_NOT_RESOLVED" in error_msg:
                    error_type = "dns_resolution"
                    should_retry = False
                elif "ERR_CONNECTION_REFUSED" in error_msg:
                    error_type = "connection_refused"
                    should_retry = True
                elif "ERR_TIMED_OUT" in error_msg or "Timeout" in error_msg:
                    error_type = "timeout"
                    should_retry = True
                # Rate limiting - retry with longer delay
                elif "429" in error_msg or "Too Many Requests" in error_msg:
                    error_type = "rate_limited"
                    should_retry = True
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(5 * (attempt + 1))
                        continue
                # Bot detection - retry (might be intermittent)
                elif "403" in error_msg or "Forbidden" in error_msg:
                    error_type = "bot_detection"
                    should_retry = True
                    logger.warning("bot_detection_suspected", url=url, attempt=attempt + 1)
                elif "ERR_ABORTED" in error_msg:
                    error_type = "navigation_aborted"
                    should_retry = False
                else:
                    error_type = "unknown"
                    should_retry = True

                logger.warning(
                    "browser_fetch_error",
                    url=url,
                    attempt=attempt + 1,
                    error=error_msg,
                    error_type=error_type,
                    will_retry=should_retry and attempt < self.max_retries - 1,
                )

                if should_retry and attempt < self.max_retries - 1:
                    # Exponential backoff
                    await asyncio.sleep(2 ** attempt)
                elif not should_retry:
                    break

        # All retries failed
        raise Exception(
            f"Failed to fetch {url} after {self.max_retries} attempts. "
            f"Last error: {last_error}"
        )
