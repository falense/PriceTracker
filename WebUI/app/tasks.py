"""
Celery tasks for WebUI.

These tasks handle async operations:
- Triggering ExtractorPatternAgent
- Triggering PriceFetcher
- Periodic price checks
"""

from celery import shared_task
from django.utils import timezone
import structlog
import asyncio

# Use structlog with service='celery' for all task logging
logger = structlog.get_logger(__name__).bind(service='celery')


@shared_task(bind=True, max_retries=3)
def generate_pattern(self, url: str, domain: str, listing_id: str = None):
    """
    Trigger ExtractorPatternAgent to generate extraction patterns.

    Args:
        url: Product URL to analyze
        domain: Domain name (e.g., "amazon.com")
        listing_id: Optional ProductListing ID for tracking

    Returns:
        dict: Status and pattern data
    """
    return asyncio.run(_generate_pattern_async(self, url, domain, listing_id))


async def _generate_pattern_async(task_self, url: str, domain: str, listing_id: str = None):
    """Async implementation of generate_pattern."""
    from app.models import Pattern
    from ExtractorPatternAgent import PatternGenerator

    try:
        logger.info(f"Generating pattern for {domain}: {url}")

        # Create generator and run pattern generation
        generator = PatternGenerator()
        pattern_data = await generator.generate(url, domain)

        # Save to database
        pattern, created = Pattern.objects.update_or_create(
            domain=domain,
            defaults={
                'pattern_json': pattern_data,
                'last_validated': timezone.now()
            }
        )
        action = "Created" if created else "Updated"
        logger.info(f"{action} pattern in database for {domain}")

        # Queue fetch task if listing_id provided
        fetch_task_id = None
        if listing_id:
            try:
                fetch_task = fetch_listing_price.delay(listing_id)
                fetch_task_id = fetch_task.id
                logger.info(
                    f"Queued price fetch task {fetch_task_id} after pattern generation "
                    f"for listing {listing_id}"
                )
            except Exception as e:
                logger.error(
                    f"Failed to queue price fetch after pattern generation for listing "
                    f"{listing_id}: {e}"
                )

        return {
            'status': 'success',
            'domain': domain,
            'action': action,
            'fields_found': pattern_data.get('metadata', {}).get('fields_found', 0),
            'confidence': pattern_data.get('metadata', {}).get('overall_confidence', 0),
            'fetch_task_id': fetch_task_id,
        }

    except Exception as e:
        logger.exception(f"Pattern generation error for {domain}")
        return {
            'status': 'error',
            'domain': domain,
            'error': str(e)
        }


@shared_task(bind=True, max_retries=3)
def fetch_listing_price(self, listing_id: str):
    """
    Trigger PriceFetcher to get current price for a product listing.

    Args:
        listing_id: ProductListing UUID

    Returns:
        dict: Price data and metadata
    """
    return asyncio.run(_fetch_listing_price_async(self, listing_id))


async def _fetch_listing_price_async(task_self, listing_id: str):
    """Async implementation of fetch_listing_price."""
    from django.conf import settings
    from PriceFetcher.src.celery_api import fetch_listing_price_direct
    from app.models import ProductListing
    from asgiref.sync import sync_to_async

    try:
        # Get listing using sync_to_async to avoid async context errors
        listing = await sync_to_async(
            lambda: ProductListing.objects.select_related('product', 'store').get(id=listing_id)
        )()

        # Create task-specific logger with context
        task_logger = logger.bind(
            task_id=task_self.request.id,
            listing_id=str(listing.id),
            product_id=str(listing.product.id),
        )

        task_logger.info(
            "fetch_listing_started",
            url=listing.url,
            store=listing.store.domain,
        )

        # Get database path from Django settings
        db_path = str(settings.DATABASES['default']['NAME'])

        # Call async function directly
        result = await fetch_listing_price_direct(
            listing_id=listing_id,
            db_path=db_path
        )

        task_logger.info(
            "fetch_listing_completed",
            status=result['status'],
            price=result.get('price'),
        )
        return result

    except ProductListing.DoesNotExist:
        logger.error(
            "fetch_listing_not_found",
            task_id=task_self.request.id,
            listing_id=listing_id,
        )
        return {
            'status': 'error',
            'listing_id': listing_id,
            'error': 'Listing not found'
        }
    except Exception as e:
        logger.error(
            "fetch_listing_error",
            task_id=task_self.request.id,
            listing_id=listing_id,
            error=str(e),
            exc_info=True,
        )
        return {
            'status': 'error',
            'listing_id': listing_id,
            'error': str(e)
        }


@shared_task
def fetch_prices_by_aggregated_priority():
    """
    Periodic task to fetch prices for products based on aggregated user priorities.

    Uses PriorityAggregationService to determine which products are due for checking
    based on their highest user subscription priority.

    Returns:
        dict: Statistics about queued listings
    """
    from app.services import PriorityAggregationService
    from app.models import ProductListing

    try:
        # Get products due for checking
        products_due = PriorityAggregationService.get_products_due_for_check()

        listing_count = 0
        product_count = len(products_due)

        for product, priority, listings in products_due:
            # Fetch all listings for this product
            for listing in listings:
                fetch_listing_price.delay(str(listing.id))
                listing_count += 1

            logger.info(
                f"Queued {len(listings)} listings for product {product.name} "
                f"(priority={priority})"
            )

        logger.info(
            f"Aggregated priority check complete: "
            f"{product_count} products, {listing_count} listings queued"
        )

        return {
            'products_checked': product_count,
            'listings_queued': listing_count
        }

    except Exception as e:
        logger.exception("Error in fetch_prices_by_aggregated_priority")
        return {
            'status': 'error',
            'error': str(e)
        }


@shared_task
def check_pattern_health():
    """
    Daily task to check pattern success rates and flag low performers.
    """
    from app.models import Pattern, AdminFlag

    MIN_SUCCESS_RATE = 0.6

    patterns = Pattern.objects.filter(total_attempts__gte=10)

    flagged = 0
    for pattern in patterns:
        if pattern.success_rate < MIN_SUCCESS_RATE:
            # Check if already flagged
            existing_flag = AdminFlag.objects.filter(
                domain=pattern.domain,
                flag_type='pattern_low_confidence',
                status='pending'
            ).exists()

            if not existing_flag:
                AdminFlag.objects.create(
                    flag_type='pattern_low_confidence',
                    domain=pattern.domain,
                    url=f"Pattern for {pattern.domain}",
                    error_message=f"Success rate: {pattern.success_rate:.1%} ({pattern.successful_attempts}/{pattern.total_attempts})",
                    status='pending'
                )
                flagged += 1
                logger.warning(f"Flagged low-confidence pattern: {pattern.domain} ({pattern.success_rate:.1%})")

    logger.info(f"Pattern health check complete. Flagged {flagged} patterns.")
    return {'flagged': flagged}


@shared_task
def cleanup_old_logs():
    """
    Weekly task to clean up old fetch logs.
    """
    from app.models import FetchLog
    from datetime import timedelta

    RETENTION_DAYS = 30
    cutoff = timezone.now() - timedelta(days=RETENTION_DAYS)

    deleted_count, _ = FetchLog.objects.filter(fetched_at__lt=cutoff).delete()

    logger.info(f"Cleaned up {deleted_count} old fetch logs")
    return {'deleted': deleted_count}


@shared_task
def fetch_missing_images():
    """
    Daily task to fetch images for products that don't have them.

    Processes up to 50 products per run to avoid overload.
    This catches new products and retries for products where image extraction failed.
    """
    return asyncio.run(_fetch_missing_images_async())


async def _fetch_missing_images_async():
    """Async implementation of fetch_missing_images."""
    from django.conf import settings
    from PriceFetcher.src.celery_api import backfill_images_direct

    try:
        logger.info("Starting fetch_missing_images task")

        # Get database path from Django settings
        db_path = str(settings.DATABASES['default']['NAME'])

        # Call async function directly
        result = await backfill_images_direct(
            db_path=db_path,
            limit=50,
            request_delay=2.0
        )

        logger.info(
            f"Missing images fetch completed: {result['success']}/{result['total']} successful"
        )
        return result

    except Exception as e:
        logger.exception("Error in fetch_missing_images task")
        return {
            'status': 'error',
            'error': str(e)
        }
