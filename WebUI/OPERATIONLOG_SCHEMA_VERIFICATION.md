# OperationLog Schema Verification Report

**Date:** 2025-12-16
**Issue:** PriceTracker-zpd
**Status:** ✓ VERIFIED - Schema is complete and compatible

## Summary

The OperationLog database schema has been verified to fully support structlog events. All required fields are present with appropriate types, constraints, and indexes.

## Schema Verification

### Required Fields Checklist

| Field | Type | Constraints | Status |
|-------|------|-------------|--------|
| `service` | varchar(50) | Choices: celery/fetcher/extractor, indexed | ✓ |
| `task_id` | varchar(100) | Nullable, indexed | ✓ |
| `listing` | ForeignKey | Nullable, references ProductListing | ✓ |
| `product` | ForeignKey | Nullable, references Product | ✓ |
| `level` | varchar(10) | Choices: DEBUG/INFO/WARNING/ERROR/CRITICAL, indexed | ✓ |
| `event` | varchar(100) | Indexed | ✓ |
| `message` | text | - | ✓ |
| `context` | JSONField | JSON_VALID check, default=dict | ✓ |
| `timestamp` | datetime | Indexed | ✓ |
| `filename` | varchar(100) | - | ✓ |
| `duration_ms` | integer | Nullable | ✓ |

### Database Schema (SQLite)

```sql
CREATE TABLE "app_operationlog" (
    "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
    "service" varchar(50) NOT NULL,
    "task_id" varchar(100) NULL,
    "level" varchar(10) NOT NULL,
    "event" varchar(100) NOT NULL,
    "message" text NOT NULL,
    "context" text NOT NULL CHECK ((JSON_VALID("context") OR "context" IS NULL)),
    "filename" varchar(100) NOT NULL,
    "timestamp" datetime NOT NULL,
    "duration_ms" integer NULL,
    "listing_id" char(32) NULL REFERENCES "app_productlisting" ("id") DEFERRABLE INITIALLY DEFERRED,
    "product_id" char(32) NULL REFERENCES "app_product" ("id") DEFERRABLE INITIALLY DEFERRED
);
```

### Indexes

The table has comprehensive indexing for efficient queries:

1. **Single-column indexes:**
   - `service`
   - `task_id`
   - `level`
   - `event`
   - `timestamp`
   - `listing_id`
   - `product_id`

2. **Composite indexes (optimized for time-series queries):**
   - `(service, timestamp DESC)`
   - `(task_id, timestamp DESC)`
   - `(level, timestamp DESC)`
   - `(listing_id, timestamp DESC)`
   - `(product_id, timestamp DESC)`
   - `(event, timestamp DESC)`

## Field Mapping: Structlog → OperationLog

| Structlog Event Field | OperationLog Field | Notes |
|----------------------|-------------------|-------|
| `timestamp` | `timestamp` | ISO format, UTC |
| `level` | `level` | DEBUG/INFO/WARNING/ERROR/CRITICAL |
| `event` (1st arg) | `event` | Structured event name |
| `message` | `message` | Human-readable message |
| `service` | `service` | celery/fetcher/extractor |
| `task_id` | `task_id` | Celery task ID for correlation |
| `filename` | `filename` | Source file (e.g., fetcher.py) |
| `duration_ms` | `duration_ms` | Operation duration |
| `listing_id` | `listing` | FK to ProductListing (optional) |
| `product_id` | `product` | FK to Product (optional) |
| **All other fields** | `context` | Stored as JSON |

## Live Database Test

A sample structlog event was successfully written to and retrieved from the database:

```sql
INSERT INTO app_operationlog (
    service, task_id, level, event, message, context,
    filename, timestamp, duration_ms, listing_id, product_id
) VALUES (
    'celery', 'test-task-123', 'INFO', 'fetch_page_started',
    'Fetching page for product',
    '{"url": "https://example.com", "method": "GET", "user_agent": "PriceTracker/1.0"}',
    'fetcher.py', datetime('now'), 150, NULL, NULL
);
```

**Result:** ✓ Insert successful, data retrieved correctly, test record cleaned up.

## Migration Status

- **Migration file:** `WebUI/app/migrations/0003_operationlog.py`
- **Created:** 2025-12-15 13:05
- **Status:** ✓ Applied to database

## Structlog Configuration Compatibility

The current structlog configuration (WebUI/config/logging_config.py) generates events with these standard fields:

- `level` - from `structlog.stdlib.add_log_level`
- `logger` - from `structlog.stdlib.add_logger_name`
- `timestamp` - from `structlog.processors.TimeStamper(fmt="iso", utc=True)`
- `app` - from `add_app_context` ("pricetracker")
- Custom context fields passed as kwargs

**Compatibility:** ✓ All fields can be mapped to OperationLog schema.

## Recommendations for DatabaseLogHandler Implementation

When implementing PriceTracker-w7s (DatabaseLogHandler), use this mapping:

```python
class DatabaseLogHandler(logging.Handler):
    def emit(self, record):
        try:
            from app.models import OperationLog

            # Extract structured context from record
            event_dict = getattr(record, 'event_dict', {})

            OperationLog.objects.create(
                service=event_dict.get('service', 'webui'),
                task_id=event_dict.get('task_id'),
                listing_id=event_dict.get('listing_id'),
                product_id=event_dict.get('product_id'),
                level=record.levelname,
                event=record.getMessage(),  # First positional arg
                message=event_dict.get('message', ''),
                context=event_dict,  # All fields as JSON
                timestamp=timezone.now(),
                filename=record.filename,
                duration_ms=event_dict.get('duration_ms')
            )
        except Exception:
            pass  # Silently fail to avoid logging recursion
```

## Conclusion

✓ **The OperationLog schema is complete and ready for structlog integration.**

No migration needed - all required fields are present with correct types and constraints. The schema supports:

- All service types (celery, fetcher, extractor)
- Product and listing context (nullable FKs)
- Structured event names and messages
- JSON context for flexible data storage
- Performance metrics (duration_ms)
- Efficient time-series queries (composite indexes)

**Next step:** Implement DatabaseLogHandler (PriceTracker-w7s) to write structlog events to this table.
