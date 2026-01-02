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
from structlog.contextvars import bind_contextvars, clear_contextvars
import asyncio

# Use structlog with service='celery' for all task logging
logger = structlog.get_logger(__name__).bind(service="celery")

# Task timeout settings (in seconds)
FETCH_TASK_SOFT_LIMIT = 180  # 3 minutes - sends SoftTimeLimitExceeded
FETCH_TASK_HARD_LIMIT = 210  # 3.5 minutes - kills task
PATTERN_TASK_SOFT_LIMIT = 300  # 5 minutes
PATTERN_TASK_HARD_LIMIT = 330  # 5.5 minutes


@shared_task(
    bind=True,
    max_retries=3,
    soft_time_limit=PATTERN_TASK_SOFT_LIMIT,
    time_limit=PATTERN_TASK_HARD_LIMIT,
)
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
    # Bind context for all downstream loggers (PriceFetcher, etc.)
    clear_contextvars()
    bind_contextvars(
        task_id=self.request.id,
        task_name="generate_pattern",
        domain=domain,
        service="celery",
    )
    if listing_id:
        bind_contextvars(listing_id=listing_id)

    try:
        return asyncio.run(_generate_pattern_async(self, url, domain, listing_id))
    finally:
        clear_contextvars()


async def _generate_pattern_async(
    task_self, url: str, domain: str, listing_id: str = None
):
    """
    Deprecated: JSON pattern generation is no longer supported.
    The system now uses Python extractor modules tracked by git.
    """
    logger.warning(
        f"Pattern generation called for {domain} but JSON patterns are deprecated. "
        f"Please use Python extractor modules instead."
    )

    # Queue fetch task if listing_id provided (extractor should already exist)
    fetch_task_id = None
    if listing_id:
        try:
            fetch_task = fetch_listing_price.delay(listing_id)
            fetch_task_id = fetch_task.id
            logger.info(f"Queued price fetch task {fetch_task_id} for listing {listing_id}")
        except Exception as e:
            logger.error(f"Failed to queue price fetch for listing {listing_id}: {e}")

    return {
        "status": "deprecated",
        "domain": domain,
        "message": "JSON pattern generation is deprecated. Use Python extractor modules.",
        "fetch_task_id": fetch_task_id,
    }


@shared_task(
    bind=True,
    max_retries=3,
    soft_time_limit=FETCH_TASK_SOFT_LIMIT,
    time_limit=FETCH_TASK_HARD_LIMIT,
)
def fetch_listing_price(self, listing_id: str):
    """
    Trigger PriceFetcher to get current price for a product listing.

    Args:
        listing_id: ProductListing UUID

    Returns:
        dict: Price data and metadata
    """
    # Bind context for all downstream loggers (PriceFetcher, etc.)
    clear_contextvars()
    bind_contextvars(
        task_id=self.request.id,
        task_name="fetch_listing_price",
        listing_id=listing_id,
        service="celery",
    )

    try:
        return asyncio.run(_fetch_listing_price_async(self, listing_id))
    finally:
        clear_contextvars()


async def _fetch_listing_price_async(task_self, listing_id: str):
    """Async implementation of fetch_listing_price."""
    from django.conf import settings
    from PriceFetcher.src.celery_api import fetch_listing_price_direct
    from app.models import ProductListing
    from app.services import NotificationService
    from asgiref.sync import sync_to_async

    try:
        # Get listing using sync_to_async to avoid async context errors
        listing = await sync_to_async(
            lambda: ProductListing.objects.select_related("product", "store").get(
                id=listing_id
            )
        )()

        # Add product_id to shared context for downstream loggers
        bind_contextvars(
            product_id=str(listing.product.id),
            url=listing.url,
            store=listing.store.domain,
        )

        logger.info(
            "fetch_listing_started",
            url=listing.url,
            store=listing.store.domain,
        )

        # Get database path from Django settings
        db_path = str(settings.DATABASES["default"]["NAME"])

        # Call async function directly
        result = await fetch_listing_price_direct(
            listing_id=listing_id, db_path=db_path
        )

        logger.info(
            "fetch_listing_completed",
            status=result["status"],
            price=result.get("price"),
        )

        # Record extraction attempt on ExtractorVersion for statistics
        # Also refetch listing to get updated data for notification checks below
        updated_listing = None
        try:
            # Refetch listing to get the extractor_version that was set during save_price
            updated_listing = await sync_to_async(
                lambda: ProductListing.objects.select_related('extractor_version').get(id=listing_id)
            )()

            if updated_listing.extractor_version:
                success = result.get("status") == "success"
                await sync_to_async(updated_listing.extractor_version.record_attempt)(success)
                logger.debug(
                    "extractor_stats_updated",
                    extractor_version_id=updated_listing.extractor_version.id,
                    success=success,
                )
        except Exception as e:
            # Don't fail the task if stats update fails
            logger.warning(
                "extractor_stats_update_failed",
                listing_id=listing_id,
                error=str(e),
            )

        # Check for restock notifications after successful fetch
        if result.get("status") == "success":
            try:
                # Use the already-fetched listing if available, otherwise refetch
                if not updated_listing:
                    updated_listing = await sync_to_async(
                        lambda: ProductListing.objects.get(id=listing_id)
                    )()

                # Check if any subscriptions should trigger notifications
                await sync_to_async(
                    NotificationService.check_subscriptions_for_listing
                )(updated_listing)

                logger.debug(
                    "notification_check_completed",
                    listing_id=listing_id,
                )
            except Exception as e:
                # Don't fail the task if notification check fails
                logger.warning(
                    "notification_check_failed",
                    listing_id=listing_id,
                    error=str(e),
                )

        return result

    except ProductListing.DoesNotExist:
        logger.error(
            "fetch_listing_not_found",
            listing_id=listing_id,
        )
        return {
            "status": "error",
            "listing_id": listing_id,
            "error": "Listing not found",
        }
    except KeyError as e:
        # KeyError needs special handling - str(KeyError('key')) just returns 'key'
        error_msg = f"Missing required configuration key: {e}"
        logger.error(
            "fetch_listing_error",
            listing_id=listing_id,
            error=error_msg,
            exc_info=True,
        )
        return {"status": "error", "listing_id": listing_id, "error": error_msg}
    except Exception as e:
        # Include exception type in error message for better debugging
        error_msg = f"{type(e).__name__}: {str(e)}" if str(e) else type(e).__name__
        logger.error(
            "fetch_listing_error",
            listing_id=listing_id,
            error=error_msg,
            exc_info=True,
        )
        return {"status": "error", "listing_id": listing_id, "error": error_msg}


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

        return {"products_checked": product_count, "listings_queued": listing_count}

    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}" if str(e) else type(e).__name__
        logger.exception("Error in fetch_prices_by_aggregated_priority")
        return {"status": "error", "error": error_msg}


@shared_task
def check_pattern_health():
    """
    Daily task to check extractor success rates and flag low performers.
    """
    from app.models import ExtractorVersion, AdminFlag

    MIN_SUCCESS_RATE = 0.6

    # Check active extractors with at least 10 attempts
    extractors = ExtractorVersion.objects.filter(is_active=True, total_attempts__gte=10)

    flagged = 0
    for extractor in extractors:
        if extractor.success_rate < MIN_SUCCESS_RATE:
            # Check if already flagged
            existing_flag = AdminFlag.objects.filter(
                domain=extractor.domain,
                flag_type="pattern_low_confidence",
                status="pending",
            ).exists()

            if not existing_flag:
                AdminFlag.objects.create(
                    flag_type="pattern_low_confidence",
                    domain=extractor.domain,
                    url=f"Extractor for {extractor.domain}",
                    error_message=f"Success rate: {extractor.success_rate:.1%} ({extractor.successful_attempts}/{extractor.total_attempts})",
                    status="pending",
                )
                flagged += 1
                logger.warning(
                    f"Flagged low-confidence extractor: {extractor.domain} ({extractor.success_rate:.1%})"
                )

    logger.info(f"Extractor health check complete. Flagged {flagged} extractors.")
    return {"flagged": flagged}


@shared_task
def cleanup_old_logs():
    """
    Weekly task to clean up old operation logs.
    """
    from app.models import OperationLog
    from datetime import timedelta

    RETENTION_DAYS = 30
    cutoff = timezone.now() - timedelta(days=RETENTION_DAYS)

    deleted_count, _ = OperationLog.objects.filter(timestamp__lt=cutoff).delete()

    logger.info(f"Cleaned up {deleted_count} old operation logs")
    return {"deleted": deleted_count}


@shared_task(
    soft_time_limit=FETCH_TASK_SOFT_LIMIT,
    time_limit=FETCH_TASK_HARD_LIMIT,
)
def fetch_missing_images():
    """
    Daily task to fetch images for products that don't have them.

    Processes up to 50 products per run to avoid overload.
    This catches new products and retries for products where image extraction failed.
    """
    clear_contextvars()
    bind_contextvars(
        task_name="fetch_missing_images",
        service="celery",
    )

    try:
        return asyncio.run(_fetch_missing_images_async())
    finally:
        clear_contextvars()


async def _fetch_missing_images_async():
    """Async implementation of fetch_missing_images."""
    from django.conf import settings
    from PriceFetcher.src.celery_api import backfill_images_direct

    try:
        logger.info("Starting fetch_missing_images task")

        # Get database path from Django settings
        db_path = str(settings.DATABASES["default"]["NAME"])

        # Call async function directly
        result = await backfill_images_direct(
            db_path=db_path, limit=50, request_delay=2.0
        )

        logger.info(
            f"Missing images fetch completed: {result['success']}/{result['total']} successful"
        )
        return result

    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}" if str(e) else type(e).__name__
        logger.exception("Error in fetch_missing_images task")
        return {"status": "error", "error": error_msg}


@shared_task
def expire_referral_tiers():
    """
    Check for expired referral tiers and downgrade users to free tier.
    Runs daily at 2 AM via Celery Beat.
    """
    from django.utils import timezone
    from app.models import CustomUser, UserTierHistory
    from app.services import NotificationService

    try:
        logger.info("Starting expire_referral_tiers task")

        # Find users with expired referral tiers
        expired_users = CustomUser.objects.filter(
            referral_tier_source='referral',
            referral_tier_expires_at__lte=timezone.now()
        )

        expired_count = 0

        for user in expired_users:
            try:
                old_tier = user.tier
                old_expires_at = user.referral_tier_expires_at

                # Downgrade to free tier
                user.tier = 'free'
                user.referral_tier_source = 'none'
                user.referral_tier_expires_at = None
                user.save()

                # Log tier change
                UserTierHistory.objects.create(
                    user=user,
                    old_tier=old_tier,
                    new_tier='free',
                    source='expiration',
                    notes=f'Referral tier expired (was valid until {old_expires_at.isoformat()})'
                )

                # Send notification to user
                try:
                    NotificationService.create_notification(
                        user=user,
                        notification_type='warning',
                        title='Nivå utløpt',
                        message='Din Støttebruker-nivå fra henvisningssystemet har utløpt. '
                               'Du kan tjene et nytt nivå ved å dele henvisningslenken din!',
                        priority=2
                    )
                except Exception as e:
                    logger.error(f"Failed to create expiration notification for user {user.id}: {e}")

                expired_count += 1
                logger.info(
                    f"Expired referral tier for user {user.username}",
                    extra={
                        'user_id': user.id,
                        'old_tier': old_tier,
                        'expired_at': old_expires_at.isoformat() if old_expires_at else None
                    }
                )

            except Exception as e:
                logger.error(f"Error expiring tier for user {user.id}: {e}")
                continue

        logger.info(
            f"Referral tier expiration completed: {expired_count} users downgraded",
            extra={'expired_count': expired_count}
        )

        return {
            'status': 'success',
            'expired_count': expired_count
        }

    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}" if str(e) else type(e).__name__
        logger.exception("Error in expire_referral_tiers task")
        return {"status": "error", "error": error_msg}


@shared_task(bind=True, soft_time_limit=1800, time_limit=1900)  # 30 min soft, 31.67 min hard
def cache_all_product_images(self):
    """
    Background task to cache all product images to MinIO.

    Fetches and caches images for all products with image URLs.
    Skips images that are already cached. Can be run manually via management
    command or scheduled periodically.

    Returns:
        dict: Statistics (total, cached, skipped, failed)
    """
    from app.models import Product
    from app.storage import minio_client
    import httpx

    clear_contextvars()
    bind_contextvars(
        task_id=self.request.id,
        task_name="cache_all_product_images",
        service="celery",
    )

    try:
        # Get all products with image URLs (no 'active' field in Product model)
        products = Product.objects.exclude(image_url__isnull=True).exclude(image_url='')

        total = products.count()
        cached = 0
        skipped = 0
        failed = 0

        logger.info(f"image_cache_backfill_started", total_products=total)

        for i, product in enumerate(products, 1):
            try:
                # Check if already cached
                if minio_client.is_image_cached(product.image_url):
                    skipped += 1
                    logger.debug(f"image_already_cached", product_id=product.id, progress=f"{i}/{total}")
                    continue

                # Fetch image with hotlink protection headers
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Referer": product.image_url.split("/")[0] + "//" + product.image_url.split("/")[2] + "/",
                    "Accept": "image/*,*/*;q=0.8",
                }

                with httpx.Client(timeout=10.0, follow_redirects=True) as client:
                    response = client.get(product.image_url, headers=headers)

                    if response.status_code == 200:
                        content_type = response.headers.get("Content-Type", "image/jpeg")
                        minio_client.cache_image(product.image_url, response.content, content_type)
                        cached += 1
                        logger.info(
                            f"image_cached",
                            product_id=product.id,
                            product_name=product.name,
                            size=len(response.content),
                            progress=f"{i}/{total}",
                        )
                    else:
                        failed += 1
                        logger.warning(
                            f"image_fetch_failed",
                            product_id=product.id,
                            status_code=response.status_code,
                            url=product.image_url,
                        )

            except Exception as e:
                failed += 1
                logger.error(
                    f"image_cache_error",
                    product_id=product.id,
                    error=str(e),
                    url=product.image_url,
                )

        logger.info(
            f"image_cache_backfill_completed",
            total=total,
            cached=cached,
            skipped=skipped,
            failed=failed,
        )

        return {
            "status": "success",
            "total": total,
            "cached": cached,
            "skipped": skipped,
            "failed": failed,
        }

    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}" if str(e) else type(e).__name__
        logger.exception("Error in cache_all_product_images task")
        return {"status": "error", "error": error_msg}
