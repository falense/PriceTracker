"""
Custom logging handlers for PriceTracker.

This module provides handlers that integrate with Django models and external systems.
"""

import asyncio
import logging
import sys
from typing import Any, Dict

from django.utils import timezone
from django.apps import apps


def _is_async_context() -> bool:
    """Check if we're running in an async context."""
    try:
        asyncio.get_running_loop()
        return True
    except RuntimeError:
        return False


class DatabaseLogHandler(logging.Handler):
    """
    Write structlog events to the OperationLog database table.

    This handler captures structured log events and persists them to the database
    for debugging, monitoring, and audit trails.

    Safety features:
    - Handles async contexts using sync_to_async
    - Uses recursion guard to prevent logging loops
    - Checks Django app registry readiness
    - Handles missing fields gracefully
    """

    def __init__(self, level=logging.NOTSET):
        super().__init__(level)
        self._recursion_guard = False
        self._error_count = 0
        self._max_errors_to_report = 5  # Limit error spam

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
            from config.logging_config import get_current_event_dict

            # Extract structured context from structlog
            # First try the record.event_dict attribute (attached during processor chain)
            # Then fall back to context variable
            event_dict = getattr(record, 'event_dict', None)
            if not event_dict:
                event_dict = get_current_event_dict()
            if not event_dict:
                event_dict = {}

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

            # Clean event_dict for JSON storage - remove non-serializable objects
            clean_context = {}
            for key, value in event_dict.items():
                # Skip internal keys and non-serializable objects
                if key.startswith('_') or isinstance(value, (logging.LogRecord,)):
                    continue
                try:
                    # Test if value is JSON serializable
                    import json
                    json.dumps(value, default=str)
                    clean_context[key] = value
                except (TypeError, ValueError):
                    # Convert non-serializable to string
                    clean_context[key] = str(value)

            # Build the database record
            log_data = {
                'service': service,
                'task_id': event_dict.get('task_id'),
                'level': record.levelname,
                'event': str(event)[:100],  # Truncate to field max length
                'message': str(message),
                'context': clean_context,  # Store cleaned event dict as JSON
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

            # Write to database - handle async context
            if _is_async_context():
                # We're in an async context - schedule the DB write
                # Use a thread to avoid blocking the event loop
                import threading
                def _write_log():
                    try:
                        OperationLog.objects.create(**log_data)
                    except Exception:
                        pass  # Silently fail in thread

                thread = threading.Thread(target=_write_log, daemon=True)
                thread.start()
            else:
                # Normal sync context
                OperationLog.objects.create(**log_data)

        except Exception as e:
            # Log errors to stderr instead of silently failing
            # This helps debug logging issues without causing recursion
            self._error_count += 1
            if self._error_count <= self._max_errors_to_report:
                print(
                    f"[DatabaseLogHandler] Error saving log to database: {e}",
                    file=sys.stderr
                )
                if self._error_count == self._max_errors_to_report:
                    print(
                        "[DatabaseLogHandler] Suppressing further error messages",
                        file=sys.stderr
                    )

        finally:
            self._recursion_guard = False
