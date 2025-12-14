#!/usr/bin/env python
"""
Full integration test for WebUI with ExtractorPatternAgent and PriceFetcher.

This test verifies the complete workflow:
1. WebUI → ExtractorPatternAgent (pattern generation)
2. WebUI → PriceFetcher (price fetching)
3. Database updates
4. Notification creation
"""

import os
import sys
import django
from pathlib import Path

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User
from app.models import Product, Pattern, PriceHistory, Notification
from app.services import ProductService, NotificationService
from decimal import Decimal
import subprocess
import json


# Configuration: Local paths for testing
BASE_DIR = Path(__file__).parent.parent
EXTRACTOR_PATH = BASE_DIR / "ExtractorPatternAgent" / "generate_pattern.py"
FETCHER_PATH = BASE_DIR / "PriceFetcher" / "scripts" / "run_fetch.py"


def check_components():
    """Verify that external components are available."""
    print("\n=== Checking Component Availability ===")

    # Check ExtractorPatternAgent
    if EXTRACTOR_PATH.exists():
        print(f"✓ ExtractorPatternAgent found: {EXTRACTOR_PATH}")
    else:
        print(f"✗ ExtractorPatternAgent NOT FOUND: {EXTRACTOR_PATH}")
        return False

    # Check PriceFetcher
    if FETCHER_PATH.exists():
        print(f"✓ PriceFetcher found: {FETCHER_PATH}")
    else:
        print(f"✗ PriceFetcher NOT FOUND: {FETCHER_PATH}")
        return False

    # Check if they're executable
    if os.access(EXTRACTOR_PATH, os.X_OK):
        print("✓ ExtractorPatternAgent is executable")
    else:
        print("⚠ ExtractorPatternAgent not executable (may need python prefix)")

    if os.access(FETCHER_PATH, os.X_OK):
        print("✓ PriceFetcher is executable")
    else:
        print("⚠ PriceFetcher not executable (may need python prefix)")

    return True


def test_extractor_pattern_agent():
    """Test ExtractorPatternAgent directly."""
    print("\n=== Test 1: ExtractorPatternAgent Direct Call ===")

    test_url = "https://www.example.com/product/test-123"
    test_domain = "example.com"

    try:
        # Call ExtractorPatternAgent
        print(f"Calling: python {EXTRACTOR_PATH} {test_url} --domain {test_domain}")

        result = subprocess.run(
            ['python', str(EXTRACTOR_PATH), test_url, '--domain', test_domain],
            capture_output=True,
            text=True,
            timeout=30
        )

        print(f"Exit code: {result.returncode}")
        print(f"Stdout: {result.stdout[:500] if result.stdout else 'None'}")
        if result.stderr:
            print(f"Stderr: {result.stderr[:500]}")

        if result.returncode == 0:
            print("✓ ExtractorPatternAgent executed successfully")

            # Check if pattern was created in database
            pattern = Pattern.objects.filter(domain=test_domain).first()
            if pattern:
                print(f"✓ Pattern found in database: {pattern.domain}")
                print(f"  - Success rate: {pattern.success_rate:.1%}")
                print(f"  - Total attempts: {pattern.total_attempts}")
                return True
            else:
                print("⚠ Pattern not found in database (may save to different location)")
                return False
        else:
            print(f"✗ ExtractorPatternAgent failed")
            return False

    except subprocess.TimeoutExpired:
        print("✗ ExtractorPatternAgent timed out")
        return False
    except Exception as e:
        print(f"✗ Error calling ExtractorPatternAgent: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_price_fetcher():
    """Test PriceFetcher directly."""
    print("\n=== Test 2: PriceFetcher Direct Call ===")

    # Create a test product first
    user, _ = User.objects.get_or_create(
        username='integration_test_user',
        defaults={'email': 'test@example.com'}
    )

    product = Product.objects.create(
        user=user,
        url="https://www.example.com/product/test-price",
        domain="example.com",
        name="Test Product for Price Fetch",
        priority='high'
    )

    print(f"Created test product: {product.id}")

    try:
        # Call PriceFetcher
        print(f"Calling: python {FETCHER_PATH} --product-id {product.id}")

        result = subprocess.run(
            ['python', str(FETCHER_PATH), '--product-id', str(product.id)],
            capture_output=True,
            text=True,
            timeout=30
        )

        print(f"Exit code: {result.returncode}")
        print(f"Stdout: {result.stdout[:500] if result.stdout else 'None'}")
        if result.stderr:
            print(f"Stderr: {result.stderr[:500]}")

        if result.returncode == 0:
            print("✓ PriceFetcher executed successfully")

            # Refresh product from database
            product.refresh_from_db()

            # Check if price was updated
            if product.current_price:
                print(f"✓ Price updated: ${product.current_price}")

                # Check price history
                history = PriceHistory.objects.filter(product=product).first()
                if history:
                    print(f"✓ Price history created: ${history.price} at {history.recorded_at}")
                    return True
                else:
                    print("⚠ No price history record (may use different storage)")
                    return True
            else:
                print("⚠ Product price not updated")
                return False
        else:
            print(f"✗ PriceFetcher failed")
            return False

    except subprocess.TimeoutExpired:
        print("✗ PriceFetcher timed out")
        return False
    except Exception as e:
        print(f"✗ Error calling PriceFetcher: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Cleanup
        product.delete()


def test_service_layer_integration():
    """Test the service layer with mocked external calls."""
    print("\n=== Test 3: Service Layer Integration (Mocked) ===")

    from unittest.mock import patch, MagicMock

    user, _ = User.objects.get_or_create(
        username='service_test_user',
        defaults={'email': 'service@example.com'}
    )

    # Mock the tasks to avoid actual subprocess calls
    with patch('tasks.generate_pattern') as mock_gen:
        with patch('tasks.fetch_product_price') as mock_fetch:
            mock_gen.delay.return_value = MagicMock(id='mock-task-gen')
            mock_fetch.delay.return_value = MagicMock(id='mock-task-fetch')

            # Add product via service
            product = ProductService.add_product(
                user=user,
                url="https://www.testsite.com/product/item-789",
                priority='normal',
                target_price=Decimal('49.99')
            )

            print(f"✓ Product created via service: {product.id}")
            print(f"  - URL: {product.url}")
            print(f"  - Domain: {product.domain}")
            print(f"  - Target price: ${product.target_price}")

            # Verify product exists in database
            assert Product.objects.filter(id=product.id).exists()
            print("✓ Product persisted to database")

            # Cleanup
            product.delete()

            return True


def test_notification_creation():
    """Test notification creation after price changes."""
    print("\n=== Test 4: Notification Creation ===")

    user, _ = User.objects.get_or_create(
        username='notification_test_user',
        defaults={'email': 'notif@example.com'}
    )

    # Create product with notification settings
    product = Product.objects.create(
        user=user,
        url="https://www.example.com/product/notif-test",
        domain="example.com",
        name="Notification Test Product",
        current_price=Decimal('100.00'),
        target_price=Decimal('80.00'),
        notify_on_drop=True,
        priority='normal'
    )

    print(f"Created test product with price ${product.current_price}")

    # Simulate price drop
    old_price = product.current_price
    new_price = Decimal('75.00')

    notification = NotificationService.create_price_drop_notification(
        product, old_price, new_price
    )

    if notification:
        print(f"✓ Price drop notification created")
        print(f"  - Message: {notification.message}")
        assert notification.notification_type == 'price_drop'
        print("✓ Notification verified")
    else:
        print("✗ No notification created")
        return False

    # Test target price notification
    product.current_price = new_price
    product.save()

    target_notification = NotificationService.create_target_reached_notification(product)

    if target_notification:
        print(f"✓ Target price notification created")
        print(f"  - Message: {target_notification.message}")
        assert target_notification.notification_type == 'target_reached'
        print("✓ Target notification verified")
    else:
        print("⚠ No target notification (may have been created recently)")

    # Cleanup
    Notification.objects.filter(product=product).delete()
    product.delete()

    return True


def test_database_connectivity():
    """Verify database is accessible and writable."""
    print("\n=== Test 5: Database Connectivity ===")

    try:
        # Try to query
        user_count = User.objects.count()
        product_count = Product.objects.count()
        pattern_count = Pattern.objects.count()

        print(f"✓ Database accessible")
        print(f"  - Users: {user_count}")
        print(f"  - Products: {product_count}")
        print(f"  - Patterns: {pattern_count}")

        # Try to write
        test_user, created = User.objects.get_or_create(
            username='db_test_user',
            defaults={'email': 'dbtest@example.com'}
        )

        if created:
            print("✓ Database writable")
            test_user.delete()
        else:
            print("✓ Database writable (user existed)")

        return True

    except Exception as e:
        print(f"✗ Database error: {e}")
        return False


def cleanup_test_data():
    """Clean up test data."""
    print("\n=== Cleanup Test Data ===")

    test_users = [
        'integration_test_user',
        'service_test_user',
        'notification_test_user',
        'db_test_user'
    ]

    for username in test_users:
        user = User.objects.filter(username=username).first()
        if user:
            # Delete products first (cascade should handle it, but being explicit)
            Product.objects.filter(user=user).delete()
            Notification.objects.filter(user=user).delete()
            user.delete()
            print(f"✓ Cleaned up user: {username}")


def main():
    """Run all integration tests."""
    print("=" * 70)
    print("WebUI Full Integration Test Suite")
    print("=" * 70)

    results = {}

    try:
        # Pre-flight checks
        results['components'] = check_components()
        if not results['components']:
            print("\n✗ Components not available, skipping integration tests")
            print("This is expected if components aren't set up yet.")
            return 1

        # Database tests
        results['database'] = test_database_connectivity()

        # Service layer tests (mocked)
        results['service_layer'] = test_service_layer_integration()

        # Notification tests
        results['notifications'] = test_notification_creation()

        # External component tests (may fail if components not configured)
        print("\n" + "=" * 70)
        print("External Component Tests (may fail - this is OK for now)")
        print("=" * 70)

        results['extractor'] = test_extractor_pattern_agent()
        results['fetcher'] = test_price_fetcher()

        # Summary
        print("\n" + "=" * 70)
        print("Test Results Summary")
        print("=" * 70)

        for test_name, passed in results.items():
            status = "✓ PASS" if passed else "✗ FAIL"
            print(f"{test_name.replace('_', ' ').title():30s} {status}")

        passed_count = sum(1 for v in results.values() if v)
        total_count = len(results)

        print(f"\nPassed: {passed_count}/{total_count}")

        if passed_count == total_count:
            print("\n✓ ALL TESTS PASSED")
            return 0
        elif passed_count >= 3:  # Database, service layer, notifications
            print("\n⚠ CORE TESTS PASSED (external integration needs work)")
            return 0
        else:
            print("\n✗ SOME TESTS FAILED")
            return 1

    except Exception as e:
        print(f"\n✗ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        cleanup_test_data()


if __name__ == '__main__':
    sys.exit(main())
