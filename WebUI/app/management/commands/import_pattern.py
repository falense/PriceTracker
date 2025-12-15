"""Django management command to import/update an extraction pattern into the DB."""

import json
import sys
from pathlib import Path
from urllib.parse import urlparse

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone

from app.models import Pattern, PatternHistory, Store


def normalize_domain(domain: str) -> str:
    domain = (domain or "").strip().lower()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def infer_domain(pattern_data: dict, explicit_domain: str | None) -> str:
    if explicit_domain:
        return normalize_domain(explicit_domain)

    store_domain = pattern_data.get("store_domain")
    if store_domain:
        return normalize_domain(store_domain)

    url = pattern_data.get("url")
    if url:
        return normalize_domain(urlparse(url).netloc)

    raise CommandError(
        "Could not infer domain. Provide --domain or ensure JSON contains store_domain/url."
    )


def resolve_user(user_value: str | None):
    if not user_value:
        return None

    User = get_user_model()
    if user_value.isdigit():
        return User.objects.filter(pk=int(user_value)).first()

    return User.objects.filter(username=user_value).first() or User.objects.filter(
        email=user_value
    ).first()


class Command(BaseCommand):
    help = "Import/update a store extraction pattern JSON into the SQLite DB"

    def add_arguments(self, parser):
        parser.add_argument(
            "pattern_file",
            nargs="?",
            help="Path to pattern JSON file (omit when using --stdin)",
        )
        parser.add_argument(
            "--stdin",
            action="store_true",
            help="Read pattern JSON from stdin (useful with docker compose exec -T)",
        )
        parser.add_argument(
            "--domain",
            help="Override store domain (defaults to JSON store_domain/url)",
        )
        parser.add_argument(
            "--user",
            help="User id/username/email to attribute history change to",
        )
        parser.add_argument(
            "--change-reason",
            default="Imported pattern JSON",
            help="Reason stored in PatternHistory",
        )
        parser.add_argument(
            "--change-type",
            default="auto_generated",
            choices=[
                "manual_edit",
                "auto_generated",
                "api_update",
                "rollback",
                "auto_save",
            ],
            help="PatternHistory.change_type value",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate and show what would change without writing to DB",
        )
        parser.add_argument(
            "--no-history",
            action="store_true",
            help="Skip creating PatternHistory entries",
        )

    def handle(self, *args, **options):
        if options["stdin"]:
            try:
                pattern_data = json.loads(sys.stdin.read())
            except json.JSONDecodeError as e:
                raise CommandError(f"Invalid JSON from stdin: {e}") from e
        else:
            pattern_file = options.get("pattern_file")
            if not pattern_file:
                raise CommandError("Provide pattern_file or pass --stdin.")
            pattern_path = Path(pattern_file)
            if not pattern_path.exists():
                raise CommandError(f"Pattern file not found: {pattern_path}")
            try:
                pattern_data = json.loads(pattern_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                raise CommandError(f"Invalid JSON: {e}") from e

        if not isinstance(pattern_data, dict) or "patterns" not in pattern_data:
            raise CommandError("Pattern JSON must be an object with a top-level 'patterns' key.")

        domain = infer_domain(pattern_data, options.get("domain"))
        changed_by = resolve_user(options.get("user"))
        change_reason = options["change_reason"]
        change_type = options["change_type"]
        dry_run = options["dry_run"]
        no_history = options["no_history"]

        self.stdout.write(f"Domain: {domain}")
        if options.get("user"):
            self.stdout.write(f"Changed by: {changed_by or 'NOT FOUND (will be NULL)'}")

        with transaction.atomic():
            store = Store.objects.filter(domain=domain).first()
            if not store:
                try:
                    store = Store.objects.create(name=domain, domain=domain)
                except IntegrityError:
                    store = Store.objects.create(name=f"{domain} (store)", domain=domain)

            existing = Pattern.objects.filter(domain=domain).select_related("store").first()

            if dry_run:
                if existing:
                    self.stdout.write(
                        self.style.WARNING(
                            f"[DRY RUN] Would update Pattern for {domain} (id={existing.pk})"
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(f"[DRY RUN] Would create Pattern for {domain}")
                    )
                transaction.set_rollback(True)
                return

            if existing:
                if not no_history:
                    last_version = PatternHistory.objects.filter(pattern=existing).aggregate(
                        Max("version_number")
                    )["version_number__max"]
                    next_version = (last_version or 0) + 1
                    PatternHistory.objects.create(
                        pattern=existing,
                        domain=domain,
                        version_number=next_version,
                        pattern_json=existing.pattern_json,
                        changed_by=changed_by,
                        change_reason=change_reason,
                        change_type=change_type,
                        success_rate_at_time=existing.success_rate,
                        total_attempts_at_time=existing.total_attempts,
                    )

                Pattern.objects.filter(pk=existing.pk).update(
                    pattern_json=pattern_data,
                    store_id=store.pk,
                    last_validated=timezone.now(),
                    updated_at=timezone.now(),
                )
                self.stdout.write(self.style.SUCCESS(f"✓ Updated pattern for {domain}"))
                return

            pattern = Pattern.objects.create(
                domain=domain,
                store=store,
                pattern_json=pattern_data,
                last_validated=timezone.now(),
            )

            if not no_history:
                history, created = PatternHistory.objects.get_or_create(
                    pattern=pattern,
                    domain=domain,
                    version_number=1,
                    defaults={
                        "pattern_json": pattern_data,
                        "changed_by": changed_by,
                        "change_reason": change_reason,
                        "change_type": change_type,
                        "success_rate_at_time": 0.0,
                        "total_attempts_at_time": 0,
                    },
                )
                if not created and (
                    history.change_reason == "Initial pattern creation"
                    and history.change_type == "auto_generated"
                ):
                    PatternHistory.objects.filter(pk=history.pk).update(
                        changed_by=changed_by,
                        change_reason=change_reason,
                        change_type=change_type,
                    )

            self.stdout.write(self.style.SUCCESS(f"✓ Created pattern for {domain}"))
