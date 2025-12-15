"""
Test script to verify centralized structlog configuration.

This script can be run standalone to test the logging setup:
    python test_logging.py

Or imported in Django shell to test in context:
    python manage.py shell
    >>> from config.test_logging import test_logging
    >>> test_logging()
"""

import os
import sys
from pathlib import Path

# Add WebUI to path for imports
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))


def test_logging_standalone():
    """Test structlog configuration outside Django context."""
    print("=== Testing Structlog Configuration (Standalone) ===\n")

    # Configure structlog
    from config.logging_config import configure_structlog, get_logger

    # Test different environments
    for environment in ['development', 'production', 'celery']:
        print(f"\n--- Testing {environment} environment ---")
        configure_structlog(environment=environment)

        logger = get_logger(__name__)

        # Test various log levels
        logger.debug("debug_message", user_id=123, action="test")
        logger.info("info_message", status="success", count=42)
        logger.warning("warning_message", threshold=0.8)
        logger.error("error_message", error_code="E001")

        # Test exception logging
        try:
            1 / 0
        except ZeroDivisionError:
            logger.exception("exception_occurred", operation="division")


def test_logging_django():
    """Test structlog configuration in Django context."""
    print("=== Testing Structlog Configuration (Django) ===\n")

    # Set up Django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    import django
    django.setup()

    from config.logging_config import get_logger

    logger = get_logger(__name__)

    print("\n--- Testing in Django context ---")
    logger.info("django_test_started", module="test_logging")
    logger.info(
        "sample_operation",
        operation="fetch_price",
        product_id="test-123",
        duration_ms=150,
        status="success"
    )
    logger.info("django_test_completed")


if __name__ == '__main__':
    # Run standalone test
    test_logging_standalone()

    # Optionally test Django context if Django is available
    try:
        print("\n" + "="*60 + "\n")
        test_logging_django()
    except Exception as e:
        print(f"\nDjango context test skipped: {e}")
