"""
Smoke tests for PriceTracker WebUI.

Tests that all pages render successfully without errors.
This catches template syntax errors, missing templates, and view exceptions.
"""

import uuid
from django.test import TestCase, Client
from django.utils import timezone
from decimal import Decimal

from app.models import (
    CustomUser,
    Product,
    UserSubscription,
    ProductListing,
    Store,
    Notification,
)


class SmokeTestCase(TestCase):
    """Base class for smoke tests with common fixtures."""

    def setUp(self):
        """Create test data needed for all page tests."""
        # Create regular user
        self.user = CustomUser.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

        # Create staff user
        self.staff_user = CustomUser.objects.create_user(
            username="staffuser",
            email="staff@example.com",
            password="staffpass123",
            is_staff=True,
        )

        # Create a store
        self.store = Store.objects.create(
            domain="example.com",
            name="Example Store",
            active=True,
        )

        # Create a product
        self.product = Product.objects.create(
            canonical_name="Test Product",
            image_url="https://example.com/image.jpg",
        )

        # Create a product listing
        self.listing = ProductListing.objects.create(
            product=self.product,
            store=self.store,
            url="https://example.com/product/test-123",
            current_price=Decimal("99.99"),
            currency="NOK",
            available=True,
        )

        # Create a subscription for the user
        self.subscription = UserSubscription.objects.create(
            user=self.user,
            product=self.product,
            priority=2,  # Normal priority
        )

        # Create a notification
        self.notification = Notification.objects.create(
            user=self.user,
            subscription=self.subscription,
            listing=self.listing,
            notification_type="price_drop",
            message="Price dropped!",
            old_price=Decimal("149.99"),
            new_price=Decimal("99.99"),
        )


class PublicPagesTest(SmokeTestCase):
    """Test pages that don't require authentication."""

    def test_homepage(self):
        """Test homepage loads."""
        client = Client()
        response = client.get("/")
        self.assertIn(response.status_code, [200, 302])

    def test_login_page(self):
        """Test login page loads."""
        client = Client()
        response = client.get("/login/")
        self.assertEqual(response.status_code, 200)

    def test_register_page(self):
        """Test register page loads."""
        client = Client()
        response = client.get("/register/")
        self.assertEqual(response.status_code, 200)

    def test_pricing_page(self):
        """Test pricing page loads."""
        client = Client()
        response = client.get("/priser/")
        self.assertEqual(response.status_code, 200)

    def test_about_page(self):
        """Test about page loads."""
        client = Client()
        response = client.get("/om-oss/")
        self.assertEqual(response.status_code, 200)

    def test_product_detail_public(self):
        """Test product detail page loads for unauthenticated users."""
        client = Client()
        response = client.get(f"/products/{self.product.id}/")
        # Should work for public or redirect to login
        self.assertIn(response.status_code, [200, 302])

    def test_referral_landing_page(self):
        """Test referral landing page loads."""
        client = Client()
        response = client.get("/ref/TESTCODE/")
        # Should redirect to register with referral code
        self.assertIn(response.status_code, [200, 302])


class AuthenticatedPagesTest(SmokeTestCase):
    """Test pages requiring user authentication."""

    def setUp(self):
        super().setUp()
        self.client = Client()
        self.client.force_login(self.user)

    def test_homepage_authenticated(self):
        """Test homepage for authenticated users."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

    def test_product_list(self):
        """Test product list page loads."""
        response = self.client.get("/products/")
        self.assertEqual(response.status_code, 200)

    def test_product_add(self):
        """Test add product page loads."""
        response = self.client.get("/products/add/")
        self.assertEqual(response.status_code, 200)

    def test_product_settings(self):
        """Test product settings endpoint (POST-only, should reject GET)."""
        response = self.client.get(f"/products/{self.product.id}/settings/")
        # Should return 405 Method Not Allowed for GET
        self.assertEqual(response.status_code, 405)

    def test_product_chart(self):
        """Test product chart endpoint."""
        response = self.client.get(f"/products/{self.product.id}/chart/")
        # Returns JSON data
        self.assertEqual(response.status_code, 200)

    def test_product_status(self):
        """Test product status endpoint."""
        response = self.client.get(f"/products/{self.product.id}/status/")
        # Returns JSON or HTML fragment
        self.assertEqual(response.status_code, 200)

    def test_subscription_detail(self):
        """Test subscription detail page loads."""
        response = self.client.get(f"/subscriptions/{self.subscription.id}/")
        self.assertEqual(response.status_code, 200)

    def test_subscription_status(self):
        """Test subscription status endpoint."""
        response = self.client.get(f"/subscriptions/{self.subscription.id}/status/")
        # Can return 200 (loading) or 302 (ready, redirects to detail)
        self.assertIn(response.status_code, [200, 302])

    def test_notifications_list(self):
        """Test notifications page loads."""
        response = self.client.get("/notifications/")
        self.assertEqual(response.status_code, 200)

    def test_user_settings(self):
        """Test user settings page loads."""
        response = self.client.get("/settings/")
        self.assertEqual(response.status_code, 200)

    def test_change_password(self):
        """Test change password endpoint (POST-only, should reject GET)."""
        response = self.client.get("/settings/change-password/")
        # Should return 405 Method Not Allowed for GET
        self.assertEqual(response.status_code, 405)

    def test_referral_settings(self):
        """Test referral settings page loads."""
        response = self.client.get("/settings/referral/")
        self.assertEqual(response.status_code, 200)

    def test_search_autocomplete(self):
        """Test search autocomplete endpoint."""
        response = self.client.get("/search/autocomplete/", {"q": "test"})
        self.assertEqual(response.status_code, 200)


class AdminPagesTest(SmokeTestCase):
    """Test pages requiring staff permissions."""

    def setUp(self):
        super().setUp()
        self.client = Client()
        self.client.force_login(self.staff_user)

    def test_admin_dashboard(self):
        """Test admin dashboard loads."""
        response = self.client.get("/admin-dashboard/")
        self.assertEqual(response.status_code, 200)

    def test_admin_logs(self):
        """Test admin logs page loads."""
        response = self.client.get("/admin-dashboard/logs/")
        self.assertEqual(response.status_code, 200)

    def test_admin_operation_analytics(self):
        """Test operation analytics page loads."""
        response = self.client.get("/admin-dashboard/operation-analytics/")
        self.assertEqual(response.status_code, 200)

    def test_admin_operation_health(self):
        """Test operation health page loads."""
        response = self.client.get("/admin-dashboard/operation-health/")
        self.assertEqual(response.status_code, 200)

    def test_admin_patterns(self):
        """Test pattern status page loads."""
        response = self.client.get("/admin-dashboard/patterns/")
        self.assertEqual(response.status_code, 200)

    def test_admin_flags(self):
        """Test admin flags page loads."""
        response = self.client.get("/admin-dashboard/flags/")
        self.assertEqual(response.status_code, 200)

    def test_admin_users_list(self):
        """Test user management list page loads."""
        response = self.client.get("/admin-dashboard/users/")
        self.assertEqual(response.status_code, 200)

    def test_admin_user_detail(self):
        """Test user detail page loads."""
        response = self.client.get(f"/admin-dashboard/users/{self.user.id}/")
        self.assertEqual(response.status_code, 200)


class PermissionsTest(SmokeTestCase):
    """Test that authentication and permissions are enforced."""

    def test_authenticated_page_requires_login(self):
        """Test that authenticated pages redirect to login."""
        client = Client()
        response = client.get("/products/")
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_admin_page_requires_staff(self):
        """Test that admin pages are blocked for regular users."""
        client = Client()
        client.force_login(self.user)  # Regular user, not staff
        response = client.get("/admin-dashboard/")
        # Should redirect away or show error
        self.assertIn(response.status_code, [302, 403])

    def test_admin_page_accessible_to_staff(self):
        """Test that admin pages work for staff users."""
        client = Client()
        client.force_login(self.staff_user)
        response = client.get("/admin-dashboard/")
        self.assertEqual(response.status_code, 200)

    def test_user_can_only_see_own_subscription(self):
        """Test that users can't access other users' subscriptions."""
        # Create another user with a subscription
        other_user = CustomUser.objects.create_user(
            username="otheruser",
            email="other@example.com",
            password="otherpass123",
        )
        other_subscription = UserSubscription.objects.create(
            user=other_user,
            product=self.product,
            priority=2,
        )

        # Try to access other user's subscription
        client = Client()
        client.force_login(self.user)
        response = client.get(f"/subscriptions/{other_subscription.id}/")
        # Should return 404 (get_object_or_404 checks user ownership)
        self.assertEqual(response.status_code, 404)


class POSTEndpointsTest(SmokeTestCase):
    """Test POST-only endpoints respond correctly to GET requests."""

    def setUp(self):
        super().setUp()
        self.client = Client()
        self.client.force_login(self.user)

    def test_product_delete_rejects_get(self):
        """Test that delete endpoint rejects GET requests."""
        response = self.client.get(f"/products/{self.product.id}/delete/")
        # Should return 405 Method Not Allowed
        self.assertEqual(response.status_code, 405)

    def test_subscription_update_rejects_get(self):
        """Test that subscription update rejects GET requests."""
        response = self.client.get(f"/subscriptions/{self.subscription.id}/update/")
        # Should return 405 Method Not Allowed
        self.assertEqual(response.status_code, 405)

    def test_subscription_unsubscribe_rejects_get(self):
        """Test that unsubscribe endpoint rejects GET requests."""
        response = self.client.get(f"/subscriptions/{self.subscription.id}/unsubscribe/")
        # Should return 405 Method Not Allowed
        self.assertEqual(response.status_code, 405)

    def test_notifications_mark_read_rejects_get(self):
        """Test that mark read endpoint rejects GET requests."""
        response = self.client.get("/notifications/mark-read/")
        # Should return 405 Method Not Allowed
        self.assertEqual(response.status_code, 405)


class BrowserExtensionAPITest(SmokeTestCase):
    """Test browser extension API endpoints."""

    def setUp(self):
        super().setUp()
        self.client = Client()
        self.client.force_login(self.user)

    def test_csrf_token_endpoint(self):
        """Test CSRF token endpoint."""
        response = self.client.get("/api/addon/csrf-token/")
        self.assertEqual(response.status_code, 200)

    def test_check_tracking_endpoint(self):
        """Test check tracking endpoint."""
        response = self.client.get(
            "/api/addon/check-tracking/", {"url": "https://example.com/test"}
        )
        self.assertEqual(response.status_code, 200)


class UtilityEndpointsTest(SmokeTestCase):
    """Test utility endpoints."""

    def setUp(self):
        super().setUp()
        self.client = Client()
        self.client.force_login(self.user)

    def test_proxy_image(self):
        """Test image proxy endpoint."""
        response = self.client.get(
            "/proxy-image/", {"url": "https://example.com/image.jpg"}
        )
        # Should attempt to proxy or return error gracefully
        self.assertIn(response.status_code, [200, 400, 404])

    def test_search_endpoint(self):
        """Test search endpoint (requires POST)."""
        response = self.client.post("/search/", {"query": "test"})
        # Should return search results or empty results
        self.assertEqual(response.status_code, 200)
