"""
Management command to import user data after CustomUser migration.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils.dateparse import parse_datetime
import json

CustomUser = get_user_model()


class Command(BaseCommand):
    help = 'Import user data from JSON backup'

    def add_arguments(self, parser):
        parser.add_argument('json_file', type=str, help='Path to JSON backup file')

    def handle(self, *args, **options):
        json_file = options['json_file']

        with open(json_file, 'r') as f:
            users_data = json.load(f)

        imported = 0
        for user_data in users_data:
            # Parse datetime fields
            date_joined = parse_datetime(user_data['date_joined'])
            last_login = parse_datetime(user_data['last_login']) if user_data['last_login'] else None

            # Create user with all fields from backup
            CustomUser.objects.create(
                id=user_data['id'],
                username=user_data['username'],
                email=user_data['email'],
                password=user_data['password'],  # Already hashed
                first_name=user_data['first_name'],
                last_name=user_data['last_name'],
                is_staff=bool(user_data['is_staff']),
                is_active=bool(user_data['is_active']),
                is_superuser=bool(user_data['is_superuser']),
                date_joined=date_joined,
                last_login=last_login,
                tier='free',  # All users default to free tier
            )
            imported += 1
            self.stdout.write(f"Imported user: {user_data['username']}")

        self.stdout.write(
            self.style.SUCCESS(f'Successfully imported {imported} users with free tier')
        )
