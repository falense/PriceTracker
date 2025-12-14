"""
Celery tasks for WebUI.

These tasks handle async operations:
- Triggering ExtractorPatternAgent
- Triggering PriceFetcher
- Periodic price checks
"""

from celery import shared_task
from django.utils import timezone
import subprocess
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def generate_pattern(self, url: str, domain: str, product_id: str = None):
    """
    Trigger ExtractorPatternAgent to generate extraction patterns.

    Args:
        url: Product URL to analyze
        domain: Domain name (e.g., "amazon.com")
        product_id: Optional product ID for tracking

    Returns:
        dict: Status and pattern data
    """
    try:
        logger.info(f"Generating pattern for {domain}: {url}")

        # Run ExtractorPatternAgent
        result = subprocess.run([
            'python',
            '/extractor/scripts/generate_pattern.py',
            '--url', url,
            '--domain', domain,
            '--product-id', product_id or ''
        ], timeout=120, capture_output=True, text=True)

        if result.returncode == 0:
            logger.info(f"Pattern generated successfully for {domain}")
            return {
                'status': 'success',
                'domain': domain,
                'stdout': result.stdout
            }
        else:
            logger.error(f"Pattern generation failed for {domain}: {result.stderr}")
            return {
                'status': 'failed',
                'domain': domain,
                'error': result.stderr
            }

    except subprocess.TimeoutExpired:
        logger.error(f"Pattern generation timed out for {domain}")
        raise self.retry(countdown=60, max_retries=3)

    except Exception as e:
        logger.exception(f"Pattern generation error for {domain}")
        return {
            'status': 'error',
            'domain': domain,
            'error': str(e)
        }


@shared_task(bind=True, max_retries=3)
def fetch_product_price(self, product_id: str):
    """
    Trigger PriceFetcher to get current price for a product.

    Args:
        product_id: Product UUID

    Returns:
        dict: Price data and metadata
    """
    try:
        logger.info(f"Fetching price for product {product_id}")

        # Run PriceFetcher
        result = subprocess.run([
            'python',
            '/fetcher/scripts/run_fetch.py',
            '--product-id', product_id
        ], timeout=30, capture_output=True, text=True)

        if result.returncode == 0:
            logger.info(f"Price fetched successfully for {product_id}")
            return {
                'status': 'success',
                'product_id': product_id,
                'stdout': result.stdout
            }
        else:
            logger.error(f"Price fetch failed for {product_id}: {result.stderr}")
            return {
                'status': 'failed',
                'product_id': product_id,
                'error': result.stderr
            }

    except subprocess.TimeoutExpired:
        logger.error(f"Price fetch timed out for {product_id}")
        raise self.retry(countdown=30, max_retries=3)

    except Exception as e:
        logger.exception(f"Price fetch error for {product_id}")
        return {
            'status': 'error',
            'product_id': product_id,
            'error': str(e)
        }


@shared_task
def fetch_prices_by_priority(priority: str):
    """
    Periodic task to fetch prices for products of a given priority.

    Args:
        priority: "high" (15min), "normal" (1h), "low" (24h)
    """
    from app.models import Product

    # Map priority to check_interval
    intervals = {
        'high': 900,      # 15 minutes
        'normal': 3600,   # 1 hour
        'low': 86400,     # 24 hours
    }

    check_interval = intervals.get(priority)
    if not check_interval:
        logger.error(f"Invalid priority: {priority}")
        return

    # Get products due for checking
    now = timezone.now()
    products = Product.objects.filter(
        active=True,
        check_interval=check_interval
    ).filter(
        models.Q(last_checked__isnull=True) |
        models.Q(last_checked__lte=now - timezone.timedelta(seconds=check_interval))
    )

    count = 0
    for product in products:
        fetch_product_price.delay(str(product.id))
        count += 1

    logger.info(f"Queued {count} {priority} priority products for price checking")
    return {'priority': priority, 'count': count}


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
