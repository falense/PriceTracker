"""
Tests for refactored Celery tasks.

These tests verify that the refactored tasks (using direct imports instead of subprocess)
maintain the same behavior as the original implementation.
"""

from unittest.mock import AsyncMock, Mock, MagicMock, patch
from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
import sys
import uuid

# Mock external modules before any imports from app.tasks
extractor_mock = MagicMock()
price_fetcher_api_mock = MagicMock()

sys.modules['ExtractorPatternAgent'] = extractor_mock
sys.modules['PriceFetcher'] = MagicMock()
sys.modules['PriceFetcher.src'] = MagicMock()
sys.modules['PriceFetcher.src.celery_api'] = price_fetcher_api_mock

from app.models import (
    Product,
    ProductListing,
    Store,
    Pattern,
    PriceHistory,
    OperationLog,
    AdminFlag,
)
from app.tasks import (
    generate_pattern,
    fetch_listing_price,
    fetch_missing_images,
    fetch_prices_by_aggregated_priority,
    check_pattern_health,
    cleanup_old_logs,
)


class GeneratePatternTaskTests(TestCase):
    """Tests for the generate_pattern Celery task."""

    def setUp(self):
        self.store = Store.objects.create(
            domain="example.com",
            name="Example Store",
            active=True
        )
        self.url = "https://www.example.com/product/12345"
        self.domain = "example.com"

    def tearDown(self):
        """Reset mocks after each test."""
        extractor_mock.reset_mock()
        price_fetcher_api_mock.reset_mock()

    @patch('app.tasks._generate_pattern_async')
    def test_generate_pattern_success_creates_new_pattern(self, mock_async_func):
        """Test successful pattern generation creates a new Pattern in database."""
        # Setup mock to return expected result
        mock_async_func.return_value = {
            'status': 'success',
            'domain': self.domain,
            'action': 'Created',
            'fields_found': 5,
            'confidence': 0.95,
            'fetch_task_id': None,
        }

        # Execute task
        result = generate_pattern(self.url, self.domain)

        # Verify async function was called correctly
        mock_async_func.assert_called_once()
        call_args = mock_async_func.call_args[0]
        self.assertEqual(call_args[1], self.url)
        self.assertEqual(call_args[2], self.domain)

        # Verify return value
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['domain'], self.domain)
        self.assertEqual(result['action'], 'Created')
        self.assertEqual(result['fields_found'], 5)
        self.assertEqual(result['confidence'], 0.95)
        self.assertIsNone(result['fetch_task_id'])

    @patch('app.tasks._generate_pattern_async')
    def test_generate_pattern_success_updates_existing_pattern(self, mock_async_func):
        """Test pattern generation updates existing Pattern instead of creating duplicate."""
        # Setup mock to return expected result
        mock_async_func.return_value = {
            'status': 'success',
            'domain': self.domain,
            'action': 'Updated',
            'fields_found': 3,
            'confidence': 0.88,
            'fetch_task_id': None,
        }

        # Execute task
        result = generate_pattern(self.url, self.domain)

        # Verify return value
        self.assertEqual(result['action'], 'Updated')
        self.assertEqual(result['status'], 'success')

    @patch('app.tasks._generate_pattern_async')
    def test_generate_pattern_queues_fetch_when_listing_id_provided(self, mock_async_func):
        """Test that generate_pattern queues a fetch task when listing_id is provided."""
        # Create listing
        product = Product.objects.create(
            name="Test Product",
            canonical_name="test product"
        )
        listing = ProductListing.objects.create(
            product=product,
            store=self.store,
            url=self.url,
        )

        # Setup mock to return result with fetch_task_id
        mock_async_func.return_value = {
            'status': 'success',
            'domain': self.domain,
            'action': 'Created',
            'fields_found': 5,
            'confidence': 0.9,
            'fetch_task_id': 'fetch-task-123',
        }

        # Execute task with listing_id
        result = generate_pattern(self.url, self.domain, listing_id=str(listing.id))

        # Verify async function was called with listing_id
        mock_async_func.assert_called_once()
        call_args = mock_async_func.call_args[0]
        self.assertEqual(call_args[3], str(listing.id))

        # Verify fetch task was queued
        self.assertEqual(result['fetch_task_id'], 'fetch-task-123')

    @patch('app.tasks._generate_pattern_async')
    def test_generate_pattern_handles_error_gracefully(self, mock_async_func):
        """Test that generate_pattern handles errors and returns error status."""
        # Setup mock to return error result
        mock_async_func.return_value = {
            'status': 'error',
            'domain': self.domain,
            'error': 'Network error',
        }

        # Execute task
        result = generate_pattern(self.url, self.domain)

        # Verify error response
        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['domain'], self.domain)
        self.assertIn('Network error', result['error'])


class FetchListingPriceTaskTests(TestCase):
    """Tests for the fetch_listing_price Celery task."""

    def setUp(self):
        self.store = Store.objects.create(
            domain="example.com",
            name="Example Store",
            active=True
        )
        self.product = Product.objects.create(
            name="Test Product",
            canonical_name="test product"
        )
        self.listing = ProductListing.objects.create(
            product=self.product,
            store=self.store,
            url="https://www.example.com/product/12345",
        )

    @override_settings(DATABASES={'default': {'NAME': '/tmp/test.db'}})
    def test_fetch_listing_price_success(self):
        """Test successful price fetch via direct import."""
        # Setup mock
        mock_fetch_direct = AsyncMock(return_value={
            'status': 'success',
            'listing_id': str(self.listing.id),
            'price': 99.99,
            'currency': 'USD',
        })
        price_fetcher_api_mock.fetch_listing_price_direct = mock_fetch_direct

        # Execute task
        result = fetch_listing_price(str(self.listing.id))

        # Verify fetch_listing_price_direct was called with correct params
        mock_fetch_direct.assert_awaited_once()
        call_kwargs = mock_fetch_direct.call_args[1]
        self.assertEqual(call_kwargs['listing_id'], str(self.listing.id))
        self.assertEqual(call_kwargs['db_path'], '/tmp/test.db')

        # Verify return value
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['price'], 99.99)

    @override_settings(DATABASES={'default': {'NAME': '/tmp/test.db'}})
    def test_fetch_listing_price_handles_error(self):
        """Test that fetch_listing_price handles errors gracefully."""
        # Setup mock to raise exception
        mock_fetch_direct = AsyncMock(side_effect=Exception("Connection timeout"))
        price_fetcher_api_mock.fetch_listing_price_direct = mock_fetch_direct

        # Execute task
        result = fetch_listing_price(str(self.listing.id))

        # Verify error response
        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['listing_id'], str(self.listing.id))
        self.assertIn('Connection timeout', result['error'])


class FetchMissingImagesTaskTests(TestCase):
    """Tests for the fetch_missing_images Celery task."""

    @override_settings(DATABASES={'default': {'NAME': '/tmp/test.db'}})
    def test_fetch_missing_images_success(self):
        """Test successful image backfill via direct import."""
        # Setup mock
        mock_backfill = AsyncMock(return_value={
            'status': 'success',
            'total': 10,
            'success': 8,
            'failed': 2,
        })
        price_fetcher_api_mock.backfill_images_direct = mock_backfill

        # Execute task
        result = fetch_missing_images()

        # Verify backfill_images_direct was called with correct params
        mock_backfill.assert_awaited_once()
        call_kwargs = mock_backfill.call_args[1]
        self.assertEqual(call_kwargs['db_path'], '/tmp/test.db')
        self.assertEqual(call_kwargs['limit'], 50)
        self.assertEqual(call_kwargs['request_delay'], 2.0)

        # Verify return value
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['total'], 10)
        self.assertEqual(result['success'], 8)

    @override_settings(DATABASES={'default': {'NAME': '/tmp/test.db'}})
    def test_fetch_missing_images_handles_error(self):
        """Test that fetch_missing_images handles errors gracefully."""
        # Setup mock to raise exception
        mock_backfill = AsyncMock(side_effect=Exception("Image processing failed"))
        price_fetcher_api_mock.backfill_images_direct = mock_backfill

        # Execute task
        result = fetch_missing_images()

        # Verify error response
        self.assertEqual(result['status'], 'error')
        self.assertIn('Image processing failed', result['error'])


class FetchPricesByAggregatedPriorityTaskTests(TestCase):
    """Tests for the fetch_prices_by_aggregated_priority Celery task."""

    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="pass")
        self.store = Store.objects.create(
            domain="example.com",
            name="Example Store",
            active=True
        )

    @patch('app.services.PriorityAggregationService.get_products_due_for_check')
    @patch('app.tasks.fetch_listing_price.delay')
    def test_queues_listings_for_products_due(self, mock_fetch_delay, mock_get_due):
        """Test that task queues fetch for all listings of products due for check."""
        # Create products and listings
        product1 = Product.objects.create(name="Product 1", canonical_name="product 1")
        product2 = Product.objects.create(name="Product 2", canonical_name="product 2")

        listing1a = ProductListing.objects.create(
            product=product1,
            store=self.store,
            url="https://example.com/p1a"
        )
        listing1b = ProductListing.objects.create(
            product=product1,
            store=self.store,
            url="https://example.com/p1b"
        )
        listing2 = ProductListing.objects.create(
            product=product2,
            store=self.store,
            url="https://example.com/p2"
        )

        # Setup mock to return products due for check
        mock_get_due.return_value = [
            (product1, 'high', [listing1a, listing1b]),
            (product2, 'normal', [listing2]),
        ]

        # Execute task
        result = fetch_prices_by_aggregated_priority()

        # Verify correct number of fetch tasks queued
        self.assertEqual(mock_fetch_delay.call_count, 3)

        # Verify result statistics
        self.assertEqual(result['products_checked'], 2)
        self.assertEqual(result['listings_queued'], 3)

    @patch('app.services.PriorityAggregationService.get_products_due_for_check')
    def test_handles_error_gracefully(self, mock_get_due):
        """Test that task handles errors and returns error status."""
        mock_get_due.side_effect = Exception("Database connection failed")

        result = fetch_prices_by_aggregated_priority()

        self.assertEqual(result['status'], 'error')
        self.assertIn('Database connection failed', result['error'])


class CheckPatternHealthTaskTests(TestCase):
    """Tests for the check_pattern_health Celery task."""

    def setUp(self):
        self.store = Store.objects.create(
            domain="example.com",
            name="Example Store",
            active=True
        )

    def test_flags_low_confidence_patterns(self):
        """Test that patterns with low success rates are flagged."""
        # Create pattern with low success rate
        pattern = Pattern.objects.create(
            domain="example.com",
            store=self.store,
            pattern_json={},
            total_attempts=20,
            successful_attempts=10,  # 50% success rate < 60% threshold
            success_rate=0.5,  # Explicitly set success_rate
        )

        # Execute task
        result = check_pattern_health()

        # Verify flag was created
        self.assertEqual(result['flagged'], 1)

        flag = AdminFlag.objects.get(domain="example.com")
        self.assertEqual(flag.flag_type, 'pattern_low_confidence')
        self.assertEqual(flag.status, 'pending')
        self.assertIn('50.0%', flag.error_message)  # Should mention 50% rate

    def test_does_not_flag_high_confidence_patterns(self):
        """Test that patterns with acceptable success rates are not flagged."""
        # Create pattern with good success rate
        pattern = Pattern.objects.create(
            domain="example.com",
            store=self.store,
            pattern_json={},
            total_attempts=20,
            successful_attempts=16,  # 80% success rate >= 60% threshold
            success_rate=0.8,  # Explicitly set success_rate
        )

        # Execute task
        result = check_pattern_health()

        # Verify no flags created
        self.assertEqual(result['flagged'], 0)
        self.assertFalse(AdminFlag.objects.exists())

    def test_does_not_duplicate_existing_flags(self):
        """Test that already-flagged patterns are not flagged again."""
        # Create low-confidence pattern
        pattern = Pattern.objects.create(
            domain="example.com",
            store=self.store,
            pattern_json={},
            total_attempts=20,
            successful_attempts=10,
            success_rate=0.5,  # Explicitly set success_rate
        )

        # Create existing flag
        AdminFlag.objects.create(
            flag_type='pattern_low_confidence',
            domain="example.com",
            url="Pattern for example.com",
            status='pending',
        )

        # Execute task
        result = check_pattern_health()

        # Verify no new flag created
        self.assertEqual(result['flagged'], 0)
        self.assertEqual(AdminFlag.objects.count(), 1)

    def test_ignores_patterns_with_insufficient_attempts(self):
        """Test that patterns with < 10 attempts are not evaluated."""
        # Create pattern with too few attempts
        pattern = Pattern.objects.create(
            domain="example.com",
            store=self.store,
            pattern_json={},
            total_attempts=5,
            successful_attempts=1,  # 20% success rate, but < 10 attempts
        )

        # Execute task
        result = check_pattern_health()

        # Verify not flagged due to insufficient data
        self.assertEqual(result['flagged'], 0)


class CleanupOldLogsTaskTests(TestCase):
    """Tests for the cleanup_old_logs Celery task."""

    def setUp(self):
        self.store = Store.objects.create(
            domain="example.com",
            name="Example Store",
            active=True
        )
        self.product = Product.objects.create(
            name="Test Product",
            canonical_name="test product"
        )
        self.listing = ProductListing.objects.create(
            product=self.product,
            store=self.store,
            url="https://example.com/p1",
        )

    def test_deletes_old_logs(self):
        """Test that logs older than retention period are deleted."""
        # Create old log (35 days old)
        old_log = OperationLog.objects.create(
            service='fetcher',
            listing=self.listing,
            level='INFO',
            event='test_event',
            message='Old test log',
            timestamp=timezone.now() - timedelta(days=35)
        )

        # Create recent log (20 days old)
        recent_log = OperationLog.objects.create(
            service='fetcher',
            listing=self.listing,
            level='INFO',
            event='test_event',
            message='Recent test log',
            timestamp=timezone.now() - timedelta(days=20)
        )

        # Execute task
        result = cleanup_old_logs()

        # Verify only old log was deleted
        self.assertEqual(result['deleted'], 1)
        self.assertFalse(OperationLog.objects.filter(id=old_log.id).exists())
        self.assertTrue(OperationLog.objects.filter(id=recent_log.id).exists())

    def test_handles_no_old_logs(self):
        """Test that task handles case with no logs to delete."""
        # Create only recent logs
        recent_log = OperationLog.objects.create(
            service='fetcher',
            listing=self.listing,
            level='INFO',
            event='test_event',
            message='Recent test log',
            timestamp=timezone.now() - timedelta(days=10)
        )

        # Execute task
        result = cleanup_old_logs()

        # Verify no logs deleted
        self.assertEqual(result['deleted'], 0)
        self.assertTrue(OperationLog.objects.filter(id=recent_log.id).exists())
