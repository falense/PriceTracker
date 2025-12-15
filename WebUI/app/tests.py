from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from app.models import Pattern, ProductListing, Store
from app.services import ProductService


class ProductServiceAddProductForUserTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tester", password="pass")

    @patch.object(ProductService, "_trigger_fetch_listing")
    @patch.object(ProductService, "_trigger_pattern_generation")
    def test_does_not_merge_distinct_urls_same_store(
        self, mock_trigger_pattern_generation, mock_trigger_fetch_listing
    ):
        url1 = "https://www.example.com/product/sku-111"
        url2 = "https://www.example.com/product/sku-222"

        product1, subscription1, listing1, _ = ProductService.add_product_for_user(
            user=self.user,
            url=url1,
            priority="normal",
        )
        product2, subscription2, listing2, _ = ProductService.add_product_for_user(
            user=self.user,
            url=url2,
            priority="normal",
        )

        self.assertNotEqual(product1.id, product2.id)
        self.assertNotEqual(listing1.id, listing2.id)
        self.assertNotEqual(subscription1.id, subscription2.id)
        self.assertNotEqual(listing1.product_id, listing2.product_id)
        self.assertEqual(listing1.store.domain, "example.com")
        self.assertEqual(listing2.store.domain, "example.com")
        self.assertNotEqual(product1.canonical_name, product2.canonical_name)

        self.assertTrue(ProductListing.objects.filter(url=url1).exists())
        self.assertTrue(ProductListing.objects.filter(url=url2).exists())

    @patch.object(ProductService, "_trigger_fetch_listing")
    @patch.object(ProductService, "_trigger_pattern_generation")
    def test_reuses_existing_listing_for_same_url(
        self, mock_trigger_pattern_generation, mock_trigger_fetch_listing
    ):
        url = "https://www.example.com/product/sku-111"

        product1, subscription1, listing1, _ = ProductService.add_product_for_user(
            user=self.user,
            url=url,
            priority="normal",
        )
        product2, subscription2, listing2, _ = ProductService.add_product_for_user(
            user=self.user,
            url=url,
            priority="normal",
        )

        self.assertEqual(product1.id, product2.id)
        self.assertEqual(listing1.id, listing2.id)
        self.assertEqual(subscription1.id, subscription2.id)

    @patch.object(ProductService, "_trigger_fetch_listing")
    @patch.object(ProductService, "_trigger_pattern_generation")
    def test_does_not_trigger_fetch_until_pattern_exists(
        self, mock_trigger_pattern_generation, mock_trigger_fetch_listing
    ):
        url = "https://www.example.com/product/sku-111"

        ProductService.add_product_for_user(
            user=self.user,
            url=url,
            priority="normal",
        )

        mock_trigger_pattern_generation.assert_called_once()
        mock_trigger_fetch_listing.assert_not_called()

    @patch.object(ProductService, "_trigger_fetch_listing")
    @patch.object(ProductService, "_trigger_pattern_generation")
    def test_triggers_fetch_immediately_when_pattern_exists(
        self, mock_trigger_pattern_generation, mock_trigger_fetch_listing
    ):
        store = Store.objects.create(domain="example.com", name="Example", active=True)
        Pattern.objects.create(domain="example.com", store=store, pattern_json={})

        url = "https://www.example.com/product/sku-111"

        ProductService.add_product_for_user(
            user=self.user,
            url=url,
            priority="normal",
        )

        mock_trigger_pattern_generation.assert_not_called()
        mock_trigger_fetch_listing.assert_called_once()
