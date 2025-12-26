"""
Celery integration API for PriceFetcher.

This module provides clean wrapper functions with Celery-friendly signatures
that can be imported directly by Django Celery tasks, eliminating the need
for subprocess calls.
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
import importlib.util

import structlog

# Add PriceFetcher root to path for config and src imports
FETCHER_ROOT = Path(__file__).parent.parent
if str(FETCHER_ROOT) not in sys.path:
    sys.path.insert(0, str(FETCHER_ROOT))

# Import config using importlib to avoid collision with Django's config package
# Django's config module is already in sys.modules, so we need to import explicitly
_config_path = FETCHER_ROOT / "config" / "__init__.py"
_spec = importlib.util.spec_from_file_location("fetcher_config", _config_path)
_fetcher_config = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_fetcher_config)
load_config = _fetcher_config.load_config

from src.fetcher import PriceFetcher
from src.models import FetchSummary

logger = structlog.get_logger(__name__).bind(service='fetcher')


async def fetch_listing_price_direct(
    listing_id: str,
    db_path: str,
    config_path: Optional[str] = None
) -> Dict:
    """
    Fetch price for a specific listing by ID.

    This is a direct API for Celery tasks to import and call, eliminating
    the need for subprocess-based communication.

    Args:
        listing_id: ProductListing UUID (with or without hyphens)
        db_path: Path to shared SQLite database
        config_path: Optional path to config file (uses default if not provided)

    Returns:
        Dictionary with result:
        {
            'status': 'success' | 'failed' | 'error',
            'listing_id': str,
            'product_id': str (if found),
            'url': str (if found),
            'extraction': dict (if successful),
            'validation': dict (if successful),
            'duration_ms': int,
            'error': str (if failed)
        }
    """
    try:
        logger.info("fetch_listing_price_direct_started", listing_id=listing_id)

        # Load configuration
        config = load_config(config_path)

        # Initialize fetcher with provided db_path
        fetcher = PriceFetcher(
            db_path=db_path,
            request_delay=config["fetcher"]["request_delay"],
            timeout=config["fetcher"]["timeout"],
            max_retries=config["fetcher"]["max_retries"],
            min_confidence=config["validation"]["min_confidence"],
            browser_timeout=config["fetcher"].get("browser_timeout", 60.0),
            wait_for_js=config["fetcher"].get("wait_for_js", True),
            domain_delays=config["fetcher"].get("domain_delays", {}),
        )

        # Get product by listing ID
        product = fetcher.storage.get_product_by_listing_id(listing_id)
        if not product:
            logger.error("listing_not_found", listing_id=listing_id)
            return {
                'status': 'error',
                'listing_id': listing_id,
                'error': f'Listing {listing_id} not found'
            }

        # Fetch price
        started_at = datetime.utcnow()
        result = await fetcher.fetch_product(product)
        duration = (datetime.utcnow() - started_at).total_seconds() * 1000

        # Build response
        response = {
            'status': 'success' if result.success else 'failed',
            'listing_id': listing_id,
            'product_id': result.product_id,
            'url': result.url,
            'duration_ms': result.duration_ms,
        }

        if result.success:
            # Include extraction and validation data
            if result.extraction:
                response['extraction'] = result.extraction.model_dump()
            if result.validation:
                response['validation'] = {
                    'valid': result.validation.valid,
                    'confidence': result.validation.confidence,
                    'errors': result.validation.errors,
                    'warnings': result.validation.warnings,
                }
        else:
            response['error'] = result.error or 'Unknown error'

        logger.info(
            "fetch_listing_price_direct_completed",
            listing_id=listing_id,
            status=response['status'],
            duration_ms=result.duration_ms
        )

        return response

    except Exception as e:
        logger.exception("fetch_listing_price_direct_error", listing_id=listing_id, error=str(e))
        return {
            'status': 'error',
            'listing_id': listing_id,
            'error': str(e)
        }


async def fetch_all_due_prices(
    db_path: str,
    config_path: Optional[str] = None
) -> Dict:
    """
    Fetch prices for all products due for update.

    This is a direct API for Celery tasks to import and call, eliminating
    the need for subprocess-based communication.

    Args:
        db_path: Path to shared SQLite database
        config_path: Optional path to config file (uses default if not provided)

    Returns:
        Dictionary with summary:
        {
            'status': 'success' | 'error',
            'total': int,
            'success': int,
            'failed': int,
            'duration_seconds': float,
            'products': list of product results (if status is success),
            'error': str (if status is error)
        }
    """
    try:
        logger.info("fetch_all_due_prices_started")

        # Load configuration
        config = load_config(config_path)

        # Initialize fetcher
        fetcher = PriceFetcher(
            db_path=db_path,
            request_delay=config["fetcher"]["request_delay"],
            timeout=config["fetcher"]["timeout"],
            max_retries=config["fetcher"]["max_retries"],
            min_confidence=config["validation"]["min_confidence"],
            browser_timeout=config["fetcher"].get("browser_timeout", 60.0),
            wait_for_js=config["fetcher"].get("wait_for_js", True),
            domain_delays=config["fetcher"].get("domain_delays", {}),
        )

        # Fetch all due products
        summary = await fetcher.fetch_all()

        # Convert to dict
        response = {
            'status': 'success',
            'total': summary.total,
            'success': summary.success,
            'failed': summary.failed,
            'duration_seconds': summary.duration_seconds,
            'products': [
                {
                    'product_id': r.product_id,
                    'url': r.url,
                    'success': r.success,
                    'duration_ms': r.duration_ms,
                    'error': r.error,
                }
                for r in summary.products
            ]
        }

        logger.info(
            "fetch_all_due_prices_completed",
            total=summary.total,
            success=summary.success,
            failed=summary.failed,
            duration=summary.duration_seconds
        )

        return response

    except Exception as e:
        logger.exception("fetch_all_due_prices_error", error=str(e))
        return {
            'status': 'error',
            'error': str(e)
        }


async def backfill_images_direct(
    db_path: str,
    limit: int = 50,
    request_delay: float = 2.0
) -> Dict:
    """
    Backfill images for products without them.

    This is a direct API for Celery tasks to import and call, eliminating
    the need for subprocess-based communication.

    Args:
        db_path: Path to shared SQLite database
        limit: Maximum number of products to process
        request_delay: Delay between requests (seconds)

    Returns:
        Dictionary with statistics:
        {
            'status': 'success' | 'error',
            'total': int,
            'success': int,
            'failed': int,
            'skipped': int,
            'no_pattern': int,
            'duration_seconds': float,
            'error': str (if status is error)
        }
    """
    try:
        logger.info("backfill_images_direct_started", limit=limit)

        # Import ImageBackfiller here to avoid circular imports
        # We need to add the scripts directory to the path
        scripts_dir = FETCHER_ROOT / "scripts"
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))

        # Import after path is set
        from backfill_images import ImageBackfiller

        # Create backfiller
        backfiller = ImageBackfiller(
            db_path=db_path,
            request_delay=request_delay,
        )

        # Run backfill
        stats = await backfiller.run(limit=limit)

        # Build response
        response = {
            'status': 'success',
            'total': stats.get('total', 0),
            'success': stats.get('success', 0),
            'failed': stats.get('failed', 0),
            'skipped': stats.get('skipped', 0),
            'no_pattern': stats.get('no_pattern', 0),
            'duration_seconds': stats.get('duration_seconds', 0.0),
        }

        logger.info(
            "backfill_images_direct_completed",
            total=stats['total'],
            success=stats['success'],
            failed=stats['failed'],
            duration=stats['duration_seconds']
        )

        return response

    except Exception as e:
        logger.exception("backfill_images_direct_error", error=str(e))
        return {
            'status': 'error',
            'error': str(e)
        }
