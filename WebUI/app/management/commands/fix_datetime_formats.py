"""
Django management command to fix datetime format inconsistencies.

This command converts all datetime fields from ISO format (T separator) to
Django SQLite format (space separator) to ensure proper comparison queries.
"""

from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Fix datetime format inconsistencies in the database'

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

        with connection.cursor() as cursor:
            # Fix app_productlisting.last_checked (T format -> space format)
            self.stdout.write('Checking app_productlisting.last_checked...')
            cursor.execute("""
                SELECT COUNT(*) FROM app_productlisting
                WHERE last_checked LIKE '%T%'
            """)
            count = cursor.fetchone()[0]

            if count > 0:
                self.stdout.write(f'Found {count} records with T separator')

                if not dry_run:
                    cursor.execute("""
                        UPDATE app_productlisting
                        SET last_checked = REPLACE(last_checked, 'T', ' ')
                        WHERE last_checked LIKE '%T%'
                    """)
                    self.stdout.write(self.style.SUCCESS(f'Fixed {count} records'))
                else:
                    self.stdout.write(f'Would fix {count} records')
            else:
                self.stdout.write(self.style.SUCCESS('No records need fixing'))

            # Fix app_productlisting.last_available
            self.stdout.write('\nChecking app_productlisting.last_available...')
            cursor.execute("""
                SELECT COUNT(*) FROM app_productlisting
                WHERE last_available LIKE '%T%'
            """)
            count = cursor.fetchone()[0]

            if count > 0:
                self.stdout.write(f'Found {count} records with T separator')

                if not dry_run:
                    cursor.execute("""
                        UPDATE app_productlisting
                        SET last_available = REPLACE(last_available, 'T', ' ')
                        WHERE last_available LIKE '%T%'
                    """)
                    self.stdout.write(self.style.SUCCESS(f'Fixed {count} records'))
                else:
                    self.stdout.write(f'Would fix {count} records')
            else:
                self.stdout.write(self.style.SUCCESS('No records need fixing'))

            # Fix app_pricehistory.recorded_at
            self.stdout.write('\nChecking app_pricehistory.recorded_at...')
            cursor.execute("""
                SELECT COUNT(*) FROM app_pricehistory
                WHERE recorded_at LIKE '%T%'
            """)
            count = cursor.fetchone()[0]

            if count > 0:
                self.stdout.write(f'Found {count} records with T separator')

                if not dry_run:
                    cursor.execute("""
                        UPDATE app_pricehistory
                        SET recorded_at = REPLACE(recorded_at, 'T', ' ')
                        WHERE recorded_at LIKE '%T%'
                    """)
                    self.stdout.write(self.style.SUCCESS(f'Fixed {count} records'))
                else:
                    self.stdout.write(f'Would fix {count} records')
            else:
                self.stdout.write(self.style.SUCCESS('No records need fixing'))

            # Fix app_fetchlog.fetched_at
            self.stdout.write('\nChecking app_fetchlog.fetched_at...')
            cursor.execute("""
                SELECT COUNT(*) FROM app_fetchlog
                WHERE fetched_at LIKE '%T%'
            """)
            count = cursor.fetchone()[0]

            if count > 0:
                self.stdout.write(f'Found {count} records with T separator')

                if not dry_run:
                    cursor.execute("""
                        UPDATE app_fetchlog
                        SET fetched_at = REPLACE(fetched_at, 'T', ' ')
                        WHERE fetched_at LIKE '%T%'
                    """)
                    self.stdout.write(self.style.SUCCESS(f'Fixed {count} records'))
                else:
                    self.stdout.write(f'Would fix {count} records')
            else:
                self.stdout.write(self.style.SUCCESS('No records need fixing'))

            if dry_run:
                self.stdout.write(self.style.WARNING('\nDRY RUN COMPLETE - No changes were made'))
            else:
                self.stdout.write(self.style.SUCCESS('\nAll datetime formats fixed!'))
