"""
Management command to backfill ExtractorVersion statistics from PriceHistory.

This command counts successful extractions from PriceHistory records and updates
the statistics fields on ExtractorVersion models.
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count, Q
from app.models import ExtractorVersion, PriceHistory


class Command(BaseCommand):
    help = 'Backfill ExtractorVersion statistics from existing PriceHistory records'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))

        # Get all active extractors
        extractors = ExtractorVersion.objects.filter(is_active=True).select_related('store')

        total_updated = 0
        total_skipped = 0

        for extractor in extractors:
            # Count price history records for listings using this extractor version
            price_histories = PriceHistory.objects.filter(
                listing__extractor_version=extractor
            )

            total_attempts = price_histories.count()

            if total_attempts == 0:
                self.stdout.write(
                    f'  Skipping {extractor.domain}: No price history found'
                )
                total_skipped += 1
                continue

            # Count successful extractions (those with valid prices)
            # We consider an extraction successful if it has a price value
            successful_attempts = price_histories.filter(
                price__isnull=False
            ).count()

            # Calculate success rate
            success_rate = successful_attempts / total_attempts if total_attempts > 0 else 0.0

            # Show what would be updated
            old_stats = f'{extractor.successful_attempts}/{extractor.total_attempts} ({extractor.success_rate * 100:.1f}%)'
            new_stats = f'{successful_attempts}/{total_attempts} ({success_rate * 100:.1f}%)'

            self.stdout.write(
                f'  {extractor.domain}: {old_stats} → {new_stats}'
            )

            # Update if not dry run
            if not dry_run:
                with transaction.atomic():
                    extractor.total_attempts = total_attempts
                    extractor.successful_attempts = successful_attempts
                    extractor.success_rate = success_rate
                    extractor.save(update_fields=[
                        'total_attempts',
                        'successful_attempts',
                        'success_rate'
                    ])

            total_updated += 1

        # Summary
        self.stdout.write('')
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'DRY RUN: Would update {total_updated} extractors, skip {total_skipped}'
                )
            )
            self.stdout.write('Run without --dry-run to apply changes')
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully updated {total_updated} extractors, skipped {total_skipped}'
                )
            )
