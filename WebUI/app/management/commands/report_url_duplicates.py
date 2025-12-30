"""
Django management command to report duplicate ProductListings.

Identifies listings that would be considered duplicates under the new
URL normalization rules (same base URL without query params/fragments).
"""

from django.core.management.base import BaseCommand
from django.db.models import Count
from app.models import ProductListing, UserSubscription
from app.services import get_url_base_for_comparison
from collections import defaultdict
import json


class Command(BaseCommand):
    help = 'Report ProductListings with duplicate base URLs'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            type=str,
            help='Optional JSON file path to save the report',
        )
        parser.add_argument(
            '--min-duplicates',
            type=int,
            default=2,
            help='Minimum number of listings to consider a duplicate group (default: 2)',
        )

    def handle(self, *args, **options):
        self.stdout.write('Analyzing ProductListings for duplicates...\n')

        # Group listings by url_base
        url_base_groups = defaultdict(list)

        listings = ProductListing.objects.select_related('product', 'store').all()
        total_listings = listings.count()

        self.stdout.write(f'Analyzing {total_listings} listings...\n')

        for listing in listings:
            # Use url_base if populated, otherwise calculate it
            if listing.url_base:
                base_url = listing.url_base
            else:
                base_url = get_url_base_for_comparison(listing.url)

            url_base_groups[base_url].append(listing)

        # Filter to only groups with duplicates
        min_dups = options['min_duplicates']
        duplicate_groups = {
            base_url: listings_list
            for base_url, listings_list in url_base_groups.items()
            if len(listings_list) >= min_dups
        }

        if not duplicate_groups:
            self.stdout.write(self.style.SUCCESS(
                f'\n✓ No duplicate groups found (minimum {min_dups} listings per group)'
            ))
            return

        # Count total affected listings
        total_affected = sum(len(listings_list) for listings_list in duplicate_groups.values())

        self.stdout.write(self.style.WARNING(
            f'\nFound {len(duplicate_groups)} duplicate groups affecting {total_affected} listings:\n'
        ))

        # Prepare report data
        report_data = []

        for idx, (base_url, listings_list) in enumerate(sorted(duplicate_groups.items()), 1):
            self.stdout.write(f'\n{self.style.WARNING(f"Group {idx}:")} {base_url}')

            group_info = {
                'base_url': base_url,
                'listings': []
            }

            for listing in listings_list:
                # Count active subscriptions for this listing
                active_subs = UserSubscription.objects.filter(
                    product=listing.product,
                    active=True
                ).count()

                listing_info = {
                    'url': listing.url,
                    'product_name': listing.product.name,
                    'store': listing.store.name,
                    'active_subscriptions': active_subs,
                    'created_at': listing.created_at.isoformat(),
                    'listing_id': str(listing.id),
                }

                group_info['listings'].append(listing_info)

                # Format output
                self.stdout.write(
                    f'  - {listing.url}\n'
                    f'    Product: {listing.product.name}\n'
                    f'    Store: {listing.store.name}\n'
                    f'    Active subscriptions: {active_subs}\n'
                    f'    Created: {listing.created_at.strftime("%Y-%m-%d %H:%M")}\n'
                    f'    ID: {listing.id}'
                )

            report_data.append(group_info)

        # Summary
        self.stdout.write(f'\n{self.style.WARNING("="*80)}')
        self.stdout.write(self.style.WARNING(
            f'Summary: {len(duplicate_groups)} duplicate groups, {total_affected} total listings'
        ))

        # Save to JSON if requested
        if options['output']:
            output_file = options['output']
            report = {
                'total_duplicate_groups': len(duplicate_groups),
                'total_affected_listings': total_affected,
                'groups': report_data
            }

            with open(output_file, 'w') as f:
                json.dump(report, f, indent=2)

            self.stdout.write(self.style.SUCCESS(f'\n✓ Report saved to {output_file}'))
