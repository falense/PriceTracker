"""
Management command to export user data before CustomUser migration.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
import json
from pathlib import Path


class Command(BaseCommand):
    help = 'Export user data to JSON for CustomUser migration'

    def handle(self, *args, **options):
        users_data = []

        for user in User.objects.all():
            users_data.append({
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'password': user.password,  # Already hashed
                'first_name': user.first_name,
                'last_name': user.last_name,
                'is_staff': user.is_staff,
                'is_active': user.is_active,
                'is_superuser': user.is_superuser,
                'date_joined': user.date_joined.isoformat(),
                'last_login': user.last_login.isoformat() if user.last_login else None,
            })

        # Save to file
        export_file = Path('/tmp/users_export.json')
        with open(export_file, 'w') as f:
            json.dump(users_data, f, indent=2)

        self.stdout.write(
            self.style.SUCCESS(f'Successfully exported {len(users_data)} users to {export_file}')
        )
