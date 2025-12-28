"""
Management command to import specific user's data from backup database.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
import sqlite3
import uuid
from datetime import datetime

CustomUser = get_user_model()


class Command(BaseCommand):
    help = 'Import user subscriptions and related data from backup database'

    def add_arguments(self, parser):
        parser.add_argument('backup_db', type=str, help='Path to backup database')
        parser.add_argument('username', type=str, help='Username to import data for')

    def handle(self, *args, **options):
        backup_db = options['backup_db']
        username = options['username']

        # Get user in new database
        try:
            user = CustomUser.objects.get(username=username)
        except CustomUser.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'User {username} not found'))
            return

        # Connect to backup database
        conn = sqlite3.connect(backup_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get user ID from backup
        cursor.execute("SELECT id FROM auth_user WHERE username = ?", (username,))
        backup_user_row = cursor.fetchone()
        if not backup_user_row:
            self.stdout.write(self.style.ERROR(f'User {username} not found in backup'))
            conn.close()
            return

        backup_user_id = backup_user_row['id']

        # Import Stores
        cursor.execute("SELECT * FROM app_store")
        stores_map = {}
        from app.models import Store

        for row in cursor.fetchall():
            store, created = Store.objects.update_or_create(
                id=row['id'],
                defaults={
                    'name': row['name'],
                    'domain': row['domain'],
                    'country': row['country'] or '',
                    'currency': row['currency'] or 'NOK',
                    'logo_url': row['logo_url'] or '',
                    'active': bool(row['active']),
                    'verified': bool(row['verified']),
                    'rate_limit_seconds': row['rate_limit_seconds'] or 0,
                }
            )
            stores_map[row['id']] = store
            if created:
                self.stdout.write(f"  Imported store: {store.name}")

        # Import Products
        cursor.execute("SELECT * FROM app_product")
        products_map = {}
        from app.models import Product

        for row in cursor.fetchall():
            product, created = Product.objects.update_or_create(
                id=row['id'],
                defaults={
                    'name': row['name'],
                    'canonical_name': row['canonical_name'],
                    'brand': row['brand'] or '',
                    'model_number': row['model_number'] or '',
                    'category': row['category'] or '',
                    'ean': row['ean'] or None,
                    'upc': row['upc'] or None,
                    'isbn': row['isbn'] or None,
                    'image_url': row['image_url'] or '',
                    'subscriber_count': row['subscriber_count'] or 0,
                }
            )
            products_map[row['id']] = product
            if created:
                self.stdout.write(f"  Imported product: {product.name}")

        # Import ProductListings
        cursor.execute("SELECT * FROM app_productlisting")
        listings_map = {}
        from app.models import ProductListing

        for row in cursor.fetchall():
            listing, created = ProductListing.objects.update_or_create(
                id=row['id'],
                defaults={
                    'product_id': row['product_id'],
                    'store_id': row['store_id'],
                    'url': row['url'],
                    'store_product_id': row['store_product_id'] or '',
                    'current_price': row['current_price'],
                    'currency': row['currency'] or 'NOK',
                    'available': bool(row['available']),
                    'shipping_cost': row['shipping_cost'],
                    'seller_name': row['seller_name'] or '',
                    'seller_rating': row['seller_rating'],
                    'active': bool(row['active']),
                    'last_checked': row['last_checked'],
                    'last_available': row['last_available'],
                }
            )
            listings_map[row['id']] = listing
            if created:
                self.stdout.write(f"  Imported listing: {listing.url[:50]}...")

        # Import UserSubscriptions for specific user
        cursor.execute("""
            SELECT * FROM app_usersubscription
            WHERE user_id = ?
        """, (backup_user_id,))

        from app.models import UserSubscription
        imported_count = 0

        for row in cursor.fetchall():
            subscription, created = UserSubscription.objects.update_or_create(
                user=user,
                product_id=row['product_id'],
                defaults={
                    'priority': row['priority'],
                    'target_price': row['target_price'],
                    'notify_on_drop': bool(row['notify_on_drop']),
                    'notify_on_restock': bool(row['notify_on_restock']),
                    'notify_on_target': bool(row['notify_on_target']),
                    'view_count': row['view_count'] or 0,
                    'last_viewed': row['last_viewed'],
                    'active': bool(row['active']),
                    'created_at': row['created_at'],
                    'updated_at': row['updated_at'],
                }
            )
            if created:
                imported_count += 1
                self.stdout.write(f"  Imported subscription: {subscription.product.name}")

        conn.close()

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully imported {imported_count} subscriptions for {username}'
            )
        )
