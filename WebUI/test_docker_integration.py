#!/usr/bin/env python
"""
Test script to verify Docker integration.

This script tests the Celery tasks directly from within the Docker environment.
"""

import os
import sys
import django

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User
from app.models import Product, Pattern
from app.tasks import generate_pattern, fetch_product_price
from decimal import Decimal
import time


def test_task_triggering():
    """Test triggering Celery tasks."""
    print("\n=== Testing Celery Task Triggering ===")

    # Create test user
    user, created = User.objects.get_or_create(
        username='docker_test_user',
        defaults={'email': 'docker@example.com'}
    )
    print(f"✓ Test user: {user.username}")

    # Create test product
    product = Product.objects.create(
        user=user,
        url="https://www.example.com/product/docker-test",
        domain="example.com",
        name="Docker Test Product",
        priority='high'
    )
    print(f"✓ Test product created: {product.id}")

    # Test 1: Trigger pattern generation task
    print("\n--- Test 1: Generate Pattern Task ---")
    try:
        task = generate_pattern.delay(
            url=product.url,
            domain=product.domain,
            product_id=str(product.id)
        )
        print(f"✓ Task triggered: {task.id}")
        print(f"  Waiting for task to complete...")

        # Wait up to 30 seconds for task to complete
        result = task.get(timeout=30)
        print(f"✓ Task completed!")
        print(f"  Result: {result}")

        # Check if pattern was created
        pattern = Pattern.objects.filter(domain=product.domain).first()
        if pattern:
            print(f"✓ Pattern created in database")
        else:
            print(f"⚠ Pattern not found (task may have failed)")

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()

    # Test 2: Trigger price fetch task
    print("\n--- Test 2: Fetch Product Price Task ---")
    try:
        task = fetch_product_price.delay(str(product.id))
        print(f"✓ Task triggered: {task.id}")
        print(f"  Waiting for task to complete...")

        # Wait up to 30 seconds for task to complete
        result = task.get(timeout=30)
        print(f"✓ Task completed!")
        print(f"  Result: {result}")

        # Check if price was updated
        product.refresh_from_db()
        if product.current_price:
            print(f"✓ Price updated: ${product.current_price}")
        else:
            print(f"⚠ Price not updated (task may have failed)")

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()

    # Cleanup
    print("\n--- Cleanup ---")
    product.delete()
    user.delete()
    print("✓ Test data cleaned up")


def check_redis_connection():
    """Check Redis connection."""
    print("\n=== Checking Redis Connection ===")
    try:
        from celery import current_app
        conn = current_app.connection()
        conn.ensure_connection(max_retries=3)
        print("✓ Redis connection successful")
        return True
    except Exception as e:
        print(f"✗ Redis connection failed: {e}")
        return False


def check_mounted_components():
    """Check if ExtractorPatternAgent and PriceFetcher are mounted."""
    print("\n=== Checking Mounted Components ===")

    from pathlib import Path

    extractor_path = Path('/extractor')
    fetcher_path = Path('/fetcher')

    if extractor_path.exists():
        print(f"✓ ExtractorPatternAgent mounted at {extractor_path}")
        # List some files
        files = list(extractor_path.glob('*.py'))[:5]
        for f in files:
            print(f"  - {f.name}")
    else:
        print(f"✗ ExtractorPatternAgent NOT mounted")

    if fetcher_path.exists():
        print(f"✓ PriceFetcher mounted at {fetcher_path}")
        # List some files
        files = list(fetcher_path.glob('scripts/*.py'))[:5]
        for f in files:
            print(f"  - {f.name}")
    else:
        print(f"✗ PriceFetcher NOT mounted")


def main():
    """Run all tests."""
    print("=" * 70)
    print("Docker Integration Test")
    print("=" * 70)

    # Pre-flight checks
    if not check_redis_connection():
        print("\n✗ Redis connection failed. Exiting.")
        return 1

    check_mounted_components()

    # Main test
    test_task_triggering()

    print("\n" + "=" * 70)
    print("Docker Integration Test Complete")
    print("=" * 70)

    return 0


if __name__ == '__main__':
    sys.exit(main())
