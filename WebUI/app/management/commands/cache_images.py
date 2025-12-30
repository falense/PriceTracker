"""
Django management command to cache all product images to MinIO.

Usage:
    python manage.py cache_images

This command triggers the cache_all_product_images Celery task and waits
for it to complete, displaying the results.
"""

from django.core.management.base import BaseCommand
from app.tasks import cache_all_product_images


class Command(BaseCommand):
    help = 'Cache all product images to MinIO'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Starting image cache backfill...'))
        self.stdout.write('This will fetch and cache images for all active products.')
        self.stdout.write('')

        # Call task synchronously (not via Celery queue)
        result = cache_all_product_images()

        # Display results
        if result.get('status') == 'success':
            self.stdout.write(self.style.SUCCESS('Image cache backfill completed!'))
            self.stdout.write('')
            self.stdout.write(f"  Total products:    {result['total']}")
            self.stdout.write(self.style.SUCCESS(f"  Cached:            {result['cached']}"))
            self.stdout.write(self.style.NOTICE(f"  Already cached:    {result['skipped']}"))

            if result['failed'] > 0:
                self.stdout.write(self.style.WARNING(f"  Failed:            {result['failed']}"))
            else:
                self.stdout.write(f"  Failed:            {result['failed']}")
        else:
            self.stdout.write(self.style.ERROR('Image cache backfill failed!'))
            self.stdout.write(f"  Error: {result.get('error', 'Unknown error')}")
