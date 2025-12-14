"""Main price fetcher orchestrator."""

import asyncio
import time
from datetime import datetime
from typing import Dict, List, Optional

import httpx
import structlog

from .extractor import Extractor
from .models import ExtractionResult, FetchResult, FetchSummary, Product
from .pattern_loader import PatternLoader
from .storage import PriceStorage
from .validator import Validator

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
    ):
        """
        Initialize price fetcher.

        Args:
            db_path: Path to shared SQLite database
            request_delay: Delay between requests (seconds)
            timeout: HTTP request timeout (seconds)
            max_retries: Maximum retry attempts
            user_agent: HTTP User-Agent string
            min_confidence: Minimum confidence threshold for validation
        """
        self.request_delay = request_delay
        self.timeout = timeout
        self.max_retries = max_retries
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )

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
                    await asyncio.sleep(self.request_delay)

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
            previous = self.storage.get_latest_price(product_id)
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
                self.storage.save_price(product_id, extraction, validation)
                self.storage.update_pattern_stats(product.domain, success=True)
            else:
                self.storage.update_pattern_stats(product.domain, success=False)

            # Log fetch attempt
            duration_ms = int((time.time() - start_time) * 1000)
            self.storage.log_fetch(
                product_id,
                success=validation.valid,
                extraction_method=extraction.price.method,
                errors=validation.errors,
                warnings=validation.warnings,
                duration_ms=duration_ms,
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
        Fetch HTML from URL with retry logic.

        Args:
            url: Product URL to fetch

        Returns:
            HTML content as string

        Raises:
            httpx.HTTPError: If fetch fails after retries
        """
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

        async with httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
        ) as client:
            for attempt in range(self.max_retries):
                try:
                    logger.debug("http_request", url=url, attempt=attempt + 1)

                    response = await client.get(url, headers=headers)
                    response.raise_for_status()

                    logger.debug(
                        "http_success",
                        url=url,
                        status=response.status_code,
                        size=len(response.text),
                    )

                    return response.text

                except httpx.HTTPStatusError as e:
                    logger.warning(
                        "http_status_error",
                        url=url,
                        status=e.response.status_code,
                        attempt=attempt + 1,
                    )

                    # Don't retry on client errors (4xx)
                    if 400 <= e.response.status_code < 500:
                        raise

                    # Retry on server errors (5xx)
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    else:
                        raise

                except (httpx.TimeoutException, httpx.NetworkError) as e:
                    logger.warning(
                        "http_network_error",
                        url=url,
                        error=str(e),
                        attempt=attempt + 1,
                    )

                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    else:
                        raise

        raise httpx.HTTPError(f"Failed to fetch {url} after {self.max_retries} attempts")
