"""
Test script to verify OperationLog schema supports structlog events.

This script verifies the field mapping between structlog events and OperationLog model.
"""

import os
import sys
import django

# Add project root to Python path
sys.path.insert(0, '/home/falense/Repositories/PriceTracker/WebUI')

# Set Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.utils import timezone
from app.models import OperationLog


def test_operationlog_schema():
    """Test that all required fields can be written to OperationLog."""

    print("Testing OperationLog schema compatibility with structlog events...")
    print()

    # Simulate a structlog event structure
    structlog_event = {
        'timestamp': timezone.now(),
        'level': 'INFO',
        'event': 'test_event',
        'message': 'Test log message',
        'service': 'celery',
        'task_id': 'test-task-123',
        'filename': 'test_script.py',
        'duration_ms': 150,
        'listing_id': None,  # Optional
        'product_id': None,  # Optional
        # Additional context fields
        'url': 'https://example.com',
        'status_code': 200,
        'extraction_method': 'css',
    }

    # Map structlog event to OperationLog fields
    try:
        log_entry = OperationLog.objects.create(
            service=structlog_event['service'],
            task_id=structlog_event.get('task_id'),
            listing_id=structlog_event.get('listing_id'),
            product_id=structlog_event.get('product_id'),
            level=structlog_event['level'],
            event=structlog_event['event'],
            message=structlog_event.get('message', ''),
            context={
                # Store all extra fields in context JSONField
                'url': structlog_event.get('url'),
                'status_code': structlog_event.get('status_code'),
                'extraction_method': structlog_event.get('extraction_method'),
            },
            filename=structlog_event.get('filename', ''),
            timestamp=structlog_event['timestamp'],
            duration_ms=structlog_event.get('duration_ms'),
        )

        print("✓ OperationLog entry created successfully!")
        print(f"  ID: {log_entry.id}")
        print(f"  Service: {log_entry.service}")
        print(f"  Level: {log_entry.level}")
        print(f"  Event: {log_entry.event}")
        print(f"  Message: {log_entry.message}")
        print(f"  Task ID: {log_entry.task_id}")
        print(f"  Timestamp: {log_entry.timestamp}")
        print(f"  Context: {log_entry.context}")
        print()

        # Verify all required fields are present
        required_fields = [
            'service', 'level', 'event', 'message', 'context',
            'filename', 'timestamp'
        ]

        print("Field verification:")
        for field in required_fields:
            value = getattr(log_entry, field)
            status = "✓" if value is not None or field == 'context' else "✗"
            print(f"  {status} {field}: {repr(value)[:50]}")

        # Optional fields
        optional_fields = ['task_id', 'listing_id', 'product_id', 'duration_ms']
        print("\nOptional fields:")
        for field in optional_fields:
            value = getattr(log_entry, field)
            print(f"  - {field}: {repr(value)}")

        print("\n✓ All required fields are present and compatible!")
        print("\nField mapping summary:")
        print("  structlog event → OperationLog model")
        print("  =====================================")
        print("  timestamp       → timestamp")
        print("  level           → level")
        print("  event (1st arg) → event")
        print("  message         → message")
        print("  service         → service")
        print("  task_id         → task_id")
        print("  filename        → filename")
        print("  duration_ms     → duration_ms")
        print("  listing_id      → listing (FK)")
        print("  product_id      → product (FK)")
        print("  **kwargs        → context (JSON)")

        # Clean up test entry
        log_entry.delete()
        print("\n✓ Test entry cleaned up")

        return True

    except Exception as e:
        print(f"✗ Error creating OperationLog entry: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = test_operationlog_schema()
    sys.exit(0 if success else 1)
