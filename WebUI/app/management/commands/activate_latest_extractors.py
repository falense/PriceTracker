"""
Django management command to activate the most recent extractor version for each domain.

This ensures that:
1. Only the most recent (by created_at) extractor version is active per domain
2. Older versions are deactivated
3. Statistics are tracked on the correct active version

Usage:
    python manage.py activate_latest_extractors
    python manage.py activate_latest_extractors --dry-run
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from app.models import ExtractorVersion
import structlog

logger = structlog.get_logger(__name__)


class Command(BaseCommand):
    help = "Activate the most recent extractor version for each domain"

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))

        # Get all domains (excluding None)
        domains = ExtractorVersion.objects.exclude(
            domain__isnull=True
        ).values_list('domain', flat=True).distinct()

        activated_count = 0
        deactivated_count = 0

        for domain in domains:
            # Get all versions for this domain, ordered by created_at (newest first)
            versions = ExtractorVersion.objects.filter(
                domain=domain
            ).order_by('-created_at')

            if not versions.exists():
                continue

            # The most recent version should be active
            latest_version = versions.first()

            # Count versions for this domain
            total_versions = versions.count()

            if total_versions == 1:
                # Only one version - ensure it's active
                if not latest_version.is_active:
                    self.stdout.write(
                        f'  {domain}: Activating only version {latest_version.commit_hash[:7]}'
                    )
                    if not dry_run:
                        latest_version.is_active = True
                        latest_version.save(update_fields=['is_active'])
                    activated_count += 1
            else:
                # Multiple versions - activate latest, deactivate others
                self.stdout.write(
                    f'  {domain}: {total_versions} versions found'
                )

                # Activate latest if not already active
                if not latest_version.is_active:
                    self.stdout.write(
                        f'    → Activating latest version {latest_version.commit_hash[:7]} '
                        f'(created {latest_version.created_at.date()})'
                    )
                    if not dry_run:
                        latest_version.is_active = True
                        latest_version.save(update_fields=['is_active'])
                    activated_count += 1
                else:
                    self.stdout.write(
                        f'    ✓ Latest version {latest_version.commit_hash[:7]} already active'
                    )

                # Deactivate all other versions
                older_versions = versions.exclude(id=latest_version.id).filter(is_active=True)
                if older_versions.exists():
                    for old_version in older_versions:
                        self.stdout.write(
                            f'    → Deactivating old version {old_version.commit_hash[:7]} '
                            f'(created {old_version.created_at.date()})'
                        )
                        if not dry_run:
                            old_version.is_active = False
                            old_version.save(update_fields=['is_active'])
                        deactivated_count += 1

        # Handle versions with domain=None
        none_versions = ExtractorVersion.objects.filter(domain__isnull=True)
        if none_versions.exists():
            self.stdout.write(
                self.style.WARNING(
                    f'\nWarning: {none_versions.count()} extractor(s) have domain=None:'
                )
            )
            for v in none_versions:
                self.stdout.write(f'  - {v.extractor_module} ({v.commit_hash[:7]})')

        self.stdout.write('\nSummary:')
        self.stdout.write(f'  Domains processed: {len(domains)}')
        self.stdout.write(f'  Versions activated: {activated_count}')
        self.stdout.write(f'  Versions deactivated: {deactivated_count}')

        if dry_run:
            self.stdout.write(self.style.WARNING('\nDRY RUN - No changes were made'))
        else:
            self.stdout.write(self.style.SUCCESS('\n✓ Extractor activation complete'))
