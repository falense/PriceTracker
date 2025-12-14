#!/usr/bin/env python3
"""
Direct test of Django ORM integration without MCP tool wrappers.

This test directly uses Django models to verify database integration.
"""

import sys
from pathlib import Path
import json

# Setup Django
DJANGO_PATH = Path(__file__).parent.parent.parent / "WebUI"
sys.path.insert(0, str(DJANGO_PATH))

import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

# Now import Django models
from app.models import Pattern
from django.utils import timezone


def test_storage_integration():
    """Run comprehensive storage integration tests using Django ORM directly."""

    print("="*60)
    print("ExtractorPatternAgent Django ORM Direct Test")
    print("="*60)
    print()

    print("✓ Django ORM initialized successfully\n")

    # Test domain
    test_domain = "test-storage.example.com"

    # Test patterns
    test_patterns = {
        "price": {
            "primary": {
                "type": "css",
                "selector": ".product-price",
                "confidence": 0.95
            },
            "fallbacks": [
                {
                    "type": "xpath",
                    "selector": "//span[@class='price']",
                    "confidence": 0.85
                }
            ]
        },
        "title": {
            "primary": {
                "type": "css",
                "selector": "#product-title",
                "confidence": 0.90
            }
        }
    }

    test_confidence = 0.92

    # Test 1: Create pattern
    print("Test 1: Create Pattern")
    print("-" * 40)

    try:
        pattern_data = {
            "patterns": test_patterns,
            "metadata": {
                "confidence_score": test_confidence,
                "generated_at": timezone.now().isoformat()
            }
        }

        pattern_obj, created = Pattern.objects.update_or_create(
            domain=test_domain,
            defaults={
                'pattern_json': pattern_data,
                'last_validated': timezone.now()
            }
        )

        if created:
            print(f"✓ Pattern created successfully (ID: {pattern_obj.id})")
        else:
            print(f"✓ Pattern updated successfully (ID: {pattern_obj.id})")
        print(f"  Domain: {pattern_obj.domain}\n")
    except Exception as e:
        print(f"❌ Failed to create pattern: {e}\n")
        return False

    # Test 2: Load pattern
    print("Test 2: Load Pattern")
    print("-" * 40)

    try:
        pattern_obj = Pattern.objects.get(domain=test_domain)

        print(f"✓ Pattern loaded successfully")
        print(f"  ID: {pattern_obj.id}")
        print(f"  Domain: {pattern_obj.domain}")
        print(f"  Success Rate: {pattern_obj.success_rate:.1%}")
        print(f"  Total Attempts: {pattern_obj.total_attempts}")

        # Verify pattern data
        loaded_data = pattern_obj.pattern_json
        confidence = loaded_data.get("metadata", {}).get("confidence_score", 0.0)
        patterns = loaded_data.get("patterns", {})

        print(f"  Confidence: {confidence}")
        print(f"  Fields: {', '.join(patterns.keys())}\n")

        if "price" not in patterns or "title" not in patterns:
            print("❌ Pattern data structure incorrect\n")
            return False

    except Pattern.DoesNotExist:
        print(f"❌ Pattern not found\n")
        return False
    except Exception as e:
        print(f"❌ Failed to load pattern: {e}\n")
        return False

    # Test 3: Update pattern stats
    print("Test 3: Update Pattern Stats")
    print("-" * 40)

    try:
        pattern_obj = Pattern.objects.get(domain=test_domain)

        # Record successful attempts
        for i in range(5):
            pattern_obj.record_attempt(success=True)

        # Record one failure
        pattern_obj.record_attempt(success=False)

        pattern_obj.refresh_from_db()

        print(f"✓ Stats updated successfully")
        print(f"  Success Rate: {pattern_obj.success_rate:.1%}")
        print(f"  Total Attempts: {pattern_obj.total_attempts}")
        print(f"  Successful Attempts: {pattern_obj.successful_attempts}")
        print(f"  Is Healthy: {pattern_obj.is_healthy}\n")

    except Exception as e:
        print(f"❌ Failed to update stats: {e}\n")
        return False

    # Test 4: List patterns
    print("Test 4: List Patterns")
    print("-" * 40)

    try:
        patterns = Pattern.objects.all().order_by('-success_rate', '-updated_at')
        print(f"✓ Found {patterns.count()} pattern(s)")

        found_test = False
        for pattern in patterns:
            if pattern.domain == test_domain:
                found_test = True
                print(f"  ✓ Test pattern: {test_domain}")
                print(f"    Success Rate: {pattern.success_rate:.1%}")
                print(f"    Attempts: {pattern.total_attempts}")
                break

        if found_test:
            print()
        else:
            print("❌ Test pattern not found in list\n")
            return False

    except Exception as e:
        print(f"❌ Failed to list patterns: {e}\n")
        return False

    # Test 5: Update pattern
    print("Test 5: Update Existing Pattern")
    print("-" * 40)

    try:
        updated_patterns = test_patterns.copy()
        updated_patterns["image"] = {
            "primary": {
                "type": "css",
                "selector": ".product-image img",
                "confidence": 0.88
            }
        }

        pattern_data = {
            "patterns": updated_patterns,
            "metadata": {
                "confidence_score": 0.94,
                "generated_at": timezone.now().isoformat()
            }
        }

        pattern_obj, created = Pattern.objects.update_or_create(
            domain=test_domain,
            defaults={
                'pattern_json': pattern_data,
                'last_validated': timezone.now()
            }
        )

        if not created:
            print(f"✓ Pattern updated successfully (not created)")
            print(f"  Added 'image' field\n")
        else:
            print(f"❌ Pattern should have been updated, not created\n")
            return False

    except Exception as e:
        print(f"❌ Failed to update pattern: {e}\n")
        return False

    # Test 6: Delete pattern (cleanup)
    print("Test 6: Delete Pattern (Cleanup)")
    print("-" * 40)

    try:
        deleted_count, _ = Pattern.objects.filter(domain=test_domain).delete()

        if deleted_count > 0:
            print(f"✓ Pattern deleted successfully")
            print(f"  Deleted count: {deleted_count}\n")
        else:
            print(f"❌ No pattern found to delete\n")
            return False

    except Exception as e:
        print(f"❌ Failed to delete pattern: {e}\n")
        return False

    # Test 7: Verify deletion
    print("Test 7: Verify Deletion")
    print("-" * 40)

    try:
        pattern_obj = Pattern.objects.get(domain=test_domain)
        print(f"❌ Pattern still exists after deletion\n")
        return False
    except Pattern.DoesNotExist:
        print("✓ Pattern correctly not found after deletion\n")

    # All tests passed
    print("="*60)
    print("✓ ALL TESTS PASSED")
    print("="*60)
    print()
    print("Django ORM integration is working correctly!")
    print("Patterns are being saved to and loaded from the shared database.")
    print(f"Database location: {DJANGO_PATH / '../db.sqlite3'}")
    print()

    return True


def main():
    """Main entry point."""
    try:
        success = test_storage_integration()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
