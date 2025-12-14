#!/usr/bin/env python
"""
Create admin user or promote existing user to admin.

Usage:
    python make_admin.py                    # Create default admin
    python make_admin.py username           # Make user admin
    python make_admin.py username password  # Create new admin
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User


def create_superuser(username='admin', email='admin@example.com', password='admin'):
    """Create a new superuser."""
    try:
        user = User.objects.create_superuser(
            username=username,
            email=email,
            password=password
        )
        print(f"✅ Created superuser: {username}")
        print(f"   Email: {email}")
        print(f"   Password: {password}")
        print(f"\n🔗 Login at: http://localhost:8000/admin")
        return user
    except Exception as e:
        print(f"❌ Error creating superuser: {e}")
        return None


def make_admin(username):
    """Make an existing user a superuser."""
    try:
        user = User.objects.get(username=username)
        user.is_staff = True
        user.is_superuser = True
        user.save()
        print(f"✅ User '{username}' is now an admin")
        print(f"   Email: {user.email}")
        print(f"\n🔗 Login at: http://localhost:8000/admin")
        return user
    except User.DoesNotExist:
        print(f"❌ User '{username}' does not exist")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


def list_users():
    """List all users and their admin status."""
    users = User.objects.all()

    if not users.exists():
        print("📋 No users found in database")
        return

    print("\n📋 Current Users:")
    print("-" * 60)
    for user in users:
        status = "🔑 ADMIN" if user.is_superuser else "👤 User"
        print(f"{status} {user.username:20} {user.email:30}")
    print("-" * 60)


def main():
    print("=" * 60)
    print("PriceTracker - Admin User Management")
    print("=" * 60)

    # List current users
    list_users()

    # Parse arguments
    if len(sys.argv) == 1:
        # No arguments - create default admin
        print("\n🔨 Creating default admin user...")
        print("   Username: admin")
        print("   Password: admin")
        print("   (Change this password after first login!)")
        create_superuser('admin', 'admin@example.com', 'admin')

    elif len(sys.argv) == 2:
        # One argument - make existing user admin
        username = sys.argv[1]
        print(f"\n🔨 Making '{username}' an admin...")
        result = make_admin(username)

        if result is None:
            print(f"\n💡 User doesn't exist. Creating new admin '{username}'...")
            create_superuser(username, f'{username}@example.com', 'admin123')

    elif len(sys.argv) >= 3:
        # Two+ arguments - create new admin with password
        username = sys.argv[1]
        password = sys.argv[2]
        email = sys.argv[3] if len(sys.argv) > 3 else f'{username}@example.com'

        print(f"\n🔨 Creating admin user '{username}'...")
        create_superuser(username, email, password)

    # Show final state
    list_users()


if __name__ == '__main__':
    main()
