"""Django management command to add image extraction patterns to all existing patterns."""

import json
from django.core.management.base import BaseCommand
from django.db import transaction
from app.models import Pattern


class Command(BaseCommand):
    help = "Add image extraction patterns to all existing patterns that don't have them"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview changes without applying them",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Show detailed information for each pattern",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        verbose = options["verbose"]

        # Define the image pattern template
        image_pattern = {
            "primary": {
                "type": "meta",
                "selector": "og:image",
                "attribute": "content",
                "confidence": 0.95,
            },
            "fallbacks": [
                {
                    "type": "meta",
                    "selector": "twitter:image",
                    "attribute": "content",
                    "confidence": 0.9,
                },
                {
                    "type": "jsonld",
                    "selector": "image",
                    "confidence": 0.85,
                },
                {
                    "type": "css",
                    "selector": "img.product-image, .product-gallery img:first-child",
                    "attribute": "src",
                    "confidence": 0.7,
                },
            ],
        }

        # Get all patterns
        patterns = Pattern.objects.all()
        total_count = patterns.count()

        self.stdout.write(f"\nFound {total_count} patterns to process")

        if dry_run:
            self.stdout.write(
                self.style.WARNING("\n[DRY RUN MODE] No changes will be saved\n")
            )

        updated_count = 0
        skipped_count = 0
        error_count = 0

        with transaction.atomic():
            for pattern in patterns:
                try:
                    # Parse the pattern_json
                    pattern_data = pattern.pattern_json

                    # Check if image pattern already exists
                    if "image" in pattern_data.get("patterns", {}):
                        skipped_count += 1
                        if verbose:
                            self.stdout.write(
                                f"  SKIP: {pattern.domain} (already has image pattern)"
                            )
                        continue

                    # Add image pattern
                    if "patterns" not in pattern_data:
                        pattern_data["patterns"] = {}

                    pattern_data["patterns"]["image"] = image_pattern

                    # Update the pattern
                    if not dry_run:
                        pattern.pattern_json = pattern_data
                        pattern.save(update_fields=["pattern_json", "updated_at"])

                    updated_count += 1
                    if verbose:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"  UPDATE: {pattern.domain} (added image pattern)"
                            )
                        )

                except Exception as e:
                    error_count += 1
                    self.stdout.write(
                        self.style.ERROR(
                            f"  ERROR: {pattern.domain} - {str(e)}"
                        )
                    )

            # Rollback if dry run
            if dry_run:
                transaction.set_rollback(True)

        # Print summary
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("SUMMARY")
        self.stdout.write("=" * 60)
        self.stdout.write(f"Total patterns:   {total_count}")
        self.stdout.write(
            self.style.SUCCESS(f"Updated:          {updated_count}")
        )
        self.stdout.write(
            self.style.WARNING(f"Skipped:          {skipped_count}")
        )
        if error_count > 0:
            self.stdout.write(
                self.style.ERROR(f"Errors:           {error_count}")
            )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "\nDRY RUN: No changes were saved. Run without --dry-run to apply."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n✓ Successfully updated {updated_count} patterns with image extraction"
                )
            )
