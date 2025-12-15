#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "playwright>=1.40.0",
#     "beautifulsoup4>=4.12.0",
#     "lxml>=4.9.0",
#     "pyyaml>=6.0",
#     "pydantic>=2.0.0",
#     "structlog>=23.1.0",
# ]
# ///
"""
Manual execution script for price fetching.

Usage:
    uv run scripts/run_fetch.py                    # Fetch all due products
    uv run scripts/run_fetch.py --product-id ID    # Fetch specific product
    uv run scripts/run_fetch.py --domain DOMAIN    # Fetch all from domain
    uv run scripts/run_fetch.py --verbose          # Enable debug logging
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

import structlog

# Add PriceFetcher root to path so both 'config' and 'src' modules can be imported
FETCHER_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(FETCHER_ROOT))

from config import load_config
from src.fetcher import PriceFetcher
from src.models import FetchSummary


def setup_logging(verbose: bool = False, log_format: str = 'console'):
    """Configure structured logging."""
    log_level = "DEBUG" if verbose else "INFO"

    if log_format == 'json':
        # JSON output for parsing and storage
        processors = [
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.CallsiteParameterAdder(
                [structlog.processors.CallsiteParameter.FILENAME]
            ),
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Console output for human readability
        processors = [
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.CallsiteParameterAdder(
                [structlog.processors.CallsiteParameter.FILENAME]
            ),
            structlog.dev.ConsoleRenderer(),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )


async def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description="PriceFetcher - Fetch product prices")
    parser.add_argument(
        "--product-id",
        help="Fetch specific product by ID",
    )
    parser.add_argument(
        "--listing-id",
        help="Fetch specific listing by ID (will fetch the associated product)",
    )
    parser.add_argument(
        "--domain",
        help="Fetch all products from specific domain",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        default=True,
        help="Fetch all products due for checking (default)",
    )
    parser.add_argument(
        "--config",
        help="Path to config file (default: config/settings.yaml)",
    )
    parser.add_argument(
        "--db-path",
        help="Path to database file (default: ../db.sqlite3)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable debug logging",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )
    parser.add_argument(
        "--log-format",
        choices=["console", "json"],
        default="console",
        help="Log output format (default: console)",
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.verbose, args.log_format)
    logger = structlog.get_logger()

    # Load configuration
    try:
        config = load_config(args.config)
    except Exception as e:
        logger.error("config_load_failed", error=str(e))
        sys.exit(1)

    # Override database path if specified
    db_path = args.db_path or config["storage"]["database"]

    # Initialize fetcher
    fetcher = PriceFetcher(
        db_path=db_path,
        request_delay=config["fetcher"]["request_delay"],
        timeout=config["fetcher"]["timeout"],
        max_retries=config["fetcher"]["max_retries"],
        user_agent=config["fetcher"]["user_agent"],
        min_confidence=config["validation"]["min_confidence"],
        browser_timeout=config["fetcher"].get("browser_timeout", 60.0),
        wait_for_js=config["fetcher"].get("wait_for_js", True),
        domain_delays=config["fetcher"].get("domain_delays", {}),
    )

    try:
        if args.listing_id:
            logger.info("fetching_single_listing", listing_id=args.listing_id)

            # Get product with the listing's URL
            product = fetcher.storage.get_product_by_listing_id(args.listing_id)
            if not product:
                logger.error("listing_not_found", listing_id=args.listing_id)
                sys.exit(1)

            # Fetch price for the product (this will fetch all its listings)
            started_at = datetime.utcnow()
            result = await fetcher.fetch_product(product)
            completed_at = datetime.utcnow()
            duration = (completed_at - started_at).total_seconds()

            # Create summary with single product
            summary = FetchSummary(
                total=1,
                success=1 if result.success else 0,
                failed=0 if result.success else 1,
                products=[result],
                started_at=started_at,
                completed_at=completed_at,
                duration_seconds=duration,
            )

        elif args.product_id:
            logger.info("fetching_single_product", product_id=args.product_id)

            # Get product from database
            product = fetcher.storage.get_product_by_id(args.product_id)
            if not product:
                logger.error("product_not_found", product_id=args.product_id)
                sys.exit(1)

            # Fetch price for single product
            started_at = datetime.utcnow()
            result = await fetcher.fetch_product(product)
            completed_at = datetime.utcnow()
            duration = (completed_at - started_at).total_seconds()

            # Create summary with single product
            summary = FetchSummary(
                total=1,
                success=1 if result.success else 0,
                failed=0 if result.success else 1,
                products=[result],
                started_at=started_at,
                completed_at=completed_at,
                duration_seconds=duration,
            )

        elif args.domain:
            logger.info("fetching_domain", domain=args.domain)
            # TODO: Implement domain-specific fetch
            logger.error("domain_fetch_not_implemented")
            sys.exit(1)

        else:
            # Fetch all products
            logger.info("fetching_all_products")
            summary = await fetcher.fetch_all()

            if args.json:
                # Output as JSON
                print(json.dumps(summary.model_dump(), indent=2, default=str))
            else:
                # Human-readable output
                print("\n" + "=" * 70)
                print("Price Fetch Summary")
                print("=" * 70)
                print(f"Total products:    {summary.total}")
                print(f"Successful:        {summary.success} ({summary.success/summary.total*100:.1f}%)" if summary.total > 0 else "Successful:        0")
                print(f"Failed:            {summary.failed}")
                print(f"Duration:          {summary.duration_seconds:.2f}s")
                print("=" * 70)

                # Show failed products
                if summary.failed > 0:
                    print("\nFailed Products:")
                    for result in summary.products:
                        if not result.success:
                            print(f"  - {result.product_id}: {result.error}")

                # Show warnings
                warnings = [
                    r for r in summary.products
                    if r.success and r.validation and r.validation.warnings
                ]
                if warnings:
                    print("\nWarnings:")
                    for result in warnings:
                        print(f"  - {result.product_id}:")
                        for warning in result.validation.warnings:
                            print(f"      {warning}")

            sys.exit(0 if summary.failed == 0 else 1)

    except KeyboardInterrupt:
        logger.info("interrupted_by_user")
        sys.exit(130)
    except Exception as e:
        logger.error("fetch_failed", error=str(e), exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
