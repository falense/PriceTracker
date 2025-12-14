#!/usr/bin/env python3
"""
Backfill script to fetch images for products that don't have them.

Usage:
    python backfill_images.py [--limit N] [--domain example.com] [--delay SECONDS]
"""

import argparse
import asyncio
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.extractor import Extractor
from src.fetcher import PriceFetcher
from src.pattern_loader import PatternLoader
from src.storage import PriceStorage
from src.models import Product

import structlog

logger = structlog.get_logger()


class ImageBackfiller:
    """Backfills images for products without them."""

    def __init__(
        self,
        db_path: str = "../db.sqlite3",
        request_delay: float = 2.0,
        timeout: int = 30,
        max_retries: int = 3,
    ):
        self.storage = PriceStorage(db_path)
        self.pattern_loader = PatternLoader(db_path)
        self.extractor = Extractor()
        self.request_delay = request_delay
        self.timeout = timeout
        self.max_retries = max_retries

        # Initialize fetcher for HTML fetching
        self.fetcher = PriceFetcher(
            db_path=db_path,
            request_delay=request_delay,
            timeout=timeout,
            max_retries=max_retries,
        )

        self.stats = {
            "total": 0,
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "no_pattern": 0,
        }

    def group_by_domain(self, products: List[Product]) -> Dict[str, List[Product]]:
        """Group products by domain for rate limiting."""
        grouped = defaultdict(list)
        for product in products:
            grouped[product.domain].append(product)
        return grouped

    async def backfill_product(
        self, product: Product, pattern: object
    ) -> bool:
        """
        Fetch and update image for a single product.

        Args:
            product: Product to fetch image for
            pattern: Extraction pattern for the domain

        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if pattern has image field
            if "image" not in pattern.patterns:
                logger.warning(
                    "pattern_missing_image_field",
                    domain=product.domain,
                    product_id=product.product_id,
                )
                return False

            # Fetch HTML
            logger.info(
                "fetching_image",
                product_id=product.product_id,
                url=product.url,
            )
            html = await self.fetcher._fetch_html(product.url)

            # Extract ONLY image field
            image_field = self.extractor._extract_field(
                html, pattern.patterns["image"]
            )

            if image_field.value:
                # Normalize relative URLs
                image_url = image_field.value.strip()
                if image_url and not image_url.startswith(('http://', 'https://')):
                    from urllib.parse import urljoin, urlparse
                    parsed = urlparse(product.url)
                    base_url = f"{parsed.scheme}://{parsed.netloc}"
                    image_url = urljoin(base_url, image_url)

                # Update database
                self.storage.update_product_image(
                    product.product_id, image_url
                )

                logger.info(
                    "image_extracted",
                    product_id=product.product_id,
                    image_url=image_url,
                    method=image_field.method,
                    confidence=image_field.confidence,
                )
                return True
            else:
                logger.warning(
                    "image_extraction_failed",
                    product_id=product.product_id,
                    url=product.url,
                )
                return False

        except Exception as e:
            logger.error(
                "backfill_error",
                product_id=product.product_id,
                url=product.url,
                error=str(e),
            )
            return False

    async def backfill_domain(
        self, domain: str, products: List[Product]
    ) -> None:
        """
        Backfill images for all products in a domain.

        Args:
            domain: Domain name
            products: List of products for this domain
        """
        logger.info(
            "processing_domain",
            domain=domain,
            product_count=len(products),
        )

        # Load pattern
        try:
            pattern = self.pattern_loader.load_pattern(domain)
            if not pattern:
                logger.warning("no_pattern_found", domain=domain)
                self.stats["no_pattern"] += len(products)
                self.stats["skipped"] += len(products)
                return

            if "image" not in pattern.patterns:
                logger.warning("pattern_missing_image", domain=domain)
                self.stats["no_pattern"] += len(products)
                self.stats["skipped"] += len(products)
                return

        except Exception as e:
            logger.error("pattern_load_error", domain=domain, error=str(e))
            self.stats["skipped"] += len(products)
            return

        # Process each product
        for i, product in enumerate(products, 1):
            print(
                f"  [{i}/{len(products)}] Processing {product.name or product.url[:50]}...",
                end=" ",
            )

            success = await self.backfill_product(product, pattern)

            if success:
                self.stats["success"] += 1
                print("✓")
            else:
                self.stats["failed"] += 1
                print("✗")

            # Rate limiting between requests
            if i < len(products):
                await asyncio.sleep(self.request_delay)

    async def run(
        self, limit: int = None, domain_filter: str = None
    ) -> Dict:
        """
        Run the backfill process.

        Args:
            limit: Maximum number of products to process (None for all)
            domain_filter: Only process products from this domain

        Returns:
            Statistics dictionary
        """
        start_time = time.time()

        # Get products without images
        print(f"Loading products without images...")
        products = self.storage.get_products_without_images(limit=limit)

        if domain_filter:
            products = [p for p in products if p.domain == domain_filter]
            print(f"Filtered to domain '{domain_filter}': {len(products)} products")

        self.stats["total"] = len(products)

        if not products:
            print("No products found without images!")
            return self.stats

        print(f"\nFound {len(products)} products without images")

        # Group by domain
        grouped = self.group_by_domain(products)
        print(f"Across {len(grouped)} domains\n")

        # Process each domain
        for domain_idx, (domain, domain_products) in enumerate(
            grouped.items(), 1
        ):
            print(
                f"\n[{domain_idx}/{len(grouped)}] Domain: {domain} ({len(domain_products)} products)"
            )
            await self.backfill_domain(domain, domain_products)

        # Calculate duration
        duration = time.time() - start_time
        self.stats["duration_seconds"] = round(duration, 2)

        # Print summary
        self._print_summary()

        return self.stats

    def _print_summary(self):
        """Print summary statistics."""
        print("\n" + "=" * 60)
        print("BACKFILL SUMMARY")
        print("=" * 60)
        print(f"Total products:     {self.stats['total']}")
        print(f"✓ Successful:       {self.stats['success']}")
        print(f"✗ Failed:           {self.stats['failed']}")
        print(f"⊘ Skipped:          {self.stats['skipped']}")
        print(f"  (No pattern:      {self.stats['no_pattern']})")
        print(f"\nDuration:           {self.stats['duration_seconds']}s")

        if self.stats["total"] > 0:
            success_rate = (self.stats["success"] / self.stats["total"]) * 100
            print(f"Success rate:       {success_rate:.1f}%")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Backfill images for products without them"
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of products to process",
    )
    parser.add_argument(
        "--domain",
        type=str,
        help="Only process products from this domain",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="Delay between requests to same domain (seconds, default: 2.0)",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default="../db.sqlite3",
        help="Path to database (default: ../db.sqlite3)",
    )

    args = parser.parse_args()

    # Create backfiller
    backfiller = ImageBackfiller(
        db_path=args.db_path,
        request_delay=args.delay,
    )

    # Run backfill
    try:
        asyncio.run(backfiller.run(limit=args.limit, domain_filter=args.domain))
    except KeyboardInterrupt:
        print("\n\nBackfill interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error("backfill_failed", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
