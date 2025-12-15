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
    import json
    import os
    from app.models import Pattern

    try:
        logger.info(f"Generating pattern for {domain}: {url}")

        # Run ExtractorPatternAgent
        result = subprocess.run([
            'python',
            '/extractor/generate_pattern.py',
            url,
            '--domain', domain
        ], timeout=120, capture_output=True, text=True, cwd='/extractor')

        if result.returncode == 0:
            logger.info(f"Pattern generated successfully for {domain}")

            # Try multiple filename patterns to handle domain variations
            possible_filenames = [
                f"{domain.replace('.', '_')}_patterns.json",  # e.g., proshop_no_patterns.json
                f"www_{domain.replace('.', '_')}_patterns.json",  # e.g., www_proshop_no_patterns.json
            ]

            # If domain doesn't start with www, also try without www prefix
            if not domain.startswith('www.'):
                www_domain = f"www.{domain}"
                possible_filenames.insert(1, f"{www_domain.replace('.', '_')}_patterns.json")

            json_path = None
            for filename in possible_filenames:
                test_path = os.path.join('/extractor', filename)
                if os.path.exists(test_path):
                    json_path = test_path
                    logger.info(f"Found pattern file: {filename}")
                    break

            if json_path:
                try:
                    with open(json_path, 'r', encoding='utf-8') as f:
                        pattern_data = json.load(f)

                    # Save to database (domain already normalized by ExtractorPatternAgent)
                    pattern, created = Pattern.objects.update_or_create(
                        domain=domain,
                        defaults={
                            'pattern_json': pattern_data,
                            'last_validated': timezone.now()
                        }
                    )
                    action = "Created" if created else "Updated"
                    logger.info(f"{action} pattern in database for {domain}")

                    # Clean up JSON file (optional)
                    try:
                        os.remove(json_path)
                        logger.debug(f"Cleaned up temporary file: {json_path}")
                    except Exception:
                        pass  # Not critical if cleanup fails

                    return {
                        'status': 'success',
                        'domain': domain,
                        'action': action,
                        'fields_found': pattern_data.get('metadata', {}).get('fields_found', 0),
                        'confidence': pattern_data.get('metadata', {}).get('overall_confidence', 0)
                    }

                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse pattern JSON for {domain}: {e}")
                    return {
                        'status': 'failed',
                        'domain': domain,
                        'error': f'Invalid JSON output: {str(e)}'
                    }
            else:
                logger.warning(f"Pattern JSON file not found. Tried: {', '.join(possible_filenames)}")
                return {
                    'status': 'failed',
                    'domain': domain,
                    'error': f'Pattern file not generated. Tried: {", ".join(possible_filenames)}'
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
def fetch_listing_price(self, listing_id: str):
    """
    Trigger PriceFetcher to get current price for a product listing.

    Args:
        listing_id: ProductListing UUID

    Returns:
        dict: Price data and metadata
    """
    try:
        logger.info(f"Fetching price for listing {listing_id}")

        # Run PriceFetcher with listing ID
        result = subprocess.run([
            'python',
            '/fetcher/scripts/run_fetch.py',
            '--listing-id', listing_id
        ], timeout=30, capture_output=True, text=True)

        if result.returncode == 0:
            logger.info(f"Price fetched successfully for listing {listing_id}")
            return {
                'status': 'success',
                'listing_id': listing_id,
                'stdout': result.stdout
            }
        else:
            logger.error(f"Price fetch failed for listing {listing_id}: {result.stderr}")
            return {
                'status': 'failed',
                'listing_id': listing_id,
                'error': result.stderr
            }

    except subprocess.TimeoutExpired:
        logger.error(f"Price fetch timed out for listing {listing_id}")
        raise self.retry(countdown=30, max_retries=3)

    except Exception as e:
        logger.exception(f"Price fetch error for listing {listing_id}")
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
    try:
        logger.info("Starting fetch_missing_images task")

        # Run backfill script with limited batch size
        result = subprocess.run([
            'python',
            '/fetcher/scripts/backfill_images.py',
            '--limit', '50',
            '--delay', '2.0'
        ], timeout=600, capture_output=True, text=True, cwd='/fetcher/scripts')

        if result.returncode == 0:
            logger.info("Missing images fetch completed successfully")
            logger.info(f"Output: {result.stdout}")

            # Parse output for statistics (optional)
            return {
                'status': 'success',
                'stdout': result.stdout
            }
        else:
            logger.error(f"Missing images fetch failed: {result.stderr}")
            return {
                'status': 'failed',
                'error': result.stderr
            }

    except subprocess.TimeoutExpired:
        logger.error("Missing images fetch timed out")
        return {
            'status': 'timeout',
            'error': 'Fetch process exceeded 10 minute timeout'
        }

    except Exception as e:
        logger.exception("Error in fetch_missing_images task")
        return {
            'status': 'error',
            'error': str(e)
        }
