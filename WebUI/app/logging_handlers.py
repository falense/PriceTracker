"""
Custom logging handlers for PriceTracker.

This module provides handlers that integrate with Django models and external systems.
"""

import logging
from typing import Any, Dict

from django.utils import timezone
from django.apps import apps


class DatabaseLogHandler(logging.Handler):
    """
    Write structlog events to the OperationLog database table.

    This handler captures structured log events and persists them to the database
    for debugging, monitoring, and audit trails.

    Safety features:
    - Silently fails to prevent logging recursion
    - Checks Django app registry readiness
    - Handles missing fields gracefully
    """

    def __init__(self, level=logging.NOTSET):
        super().__init__(level)
        self._recursion_guard = False

    def emit(self, record: logging.LogRecord) -> None:
        """
        Write a log record to the OperationLog database.

        Args:
            record: Standard logging.LogRecord with optional event_dict attribute
        """
        # Prevent logging recursion
        if self._recursion_guard:
            return

        try:
            self._recursion_guard = True

            # Check if Django apps are ready (avoid AppRegistryNotReady errors)
            if not apps.ready:
                return

            # Import here to avoid circular imports and app registry issues
            from app.models import OperationLog

            # Extract structured context from structlog
            # structlog attaches event_dict to the LogRecord
            event_dict = getattr(record, 'event_dict', {})

            # Extract event name (first positional argument from structlog)
            # Falls back to the formatted message
            event = event_dict.get('event', record.getMessage())

            # Extract message (human-readable description)
            # Some events use 'event' as the message, others have a separate 'message' field
            message = event_dict.get('message', '') if 'message' in event_dict else event

            # Determine service (celery/fetcher/extractor)
            service = event_dict.get('service', 'webui')
            if service not in ['celery', 'fetcher', 'extractor']:
                service = 'celery'  # Default to celery for unrecognized services

            # Build the database record
            log_data = {
                'service': service,
                'task_id': event_dict.get('task_id'),
                'level': record.levelname,
                'event': str(event)[:100],  # Truncate to field max length
                'message': str(message),
                'context': event_dict,  # Store full event dict as JSON
                'timestamp': timezone.now(),
                'filename': record.filename[:100] if record.filename else '',
                'duration_ms': event_dict.get('duration_ms'),
            }

            # Add optional foreign keys if present
            listing_id = event_dict.get('listing_id')
            if listing_id:
                log_data['listing_id'] = listing_id

            product_id = event_dict.get('product_id')
            if product_id:
                log_data['product_id'] = product_id

            # Write to database
            OperationLog.objects.create(**log_data)

        except Exception as e:
            # Silently fail to avoid logging recursion and app crashes
            # In development, you might want to print this for debugging:
            # print(f"DatabaseLogHandler error: {e}", file=sys.stderr)
            pass

        finally:
            self._recursion_guard = False
