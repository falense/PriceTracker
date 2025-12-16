# Centralized Logging Configuration Guide

## Overview

PriceTracker now uses a centralized structlog configuration that provides:

- **Structured JSON logging** for Celery workers (easy log aggregation)
- **Colorful console logging** for development (easy debugging)
- **Automatic context enrichment** (app name, timestamps, log levels)
- **Django integration** (works seamlessly with Django's logging)
- **Request ID support** (ready for request tracking middleware)

## How It Works

The logging configuration is initialized automatically:

1. **Django dev server**: Configured in `app/apps.py` `AppConfig.ready()` method
2. **Celery workers**: Configured via Celery signal in `config/celery.py`
3. **Environment detection**: Auto-detects dev/production/celery based on environment variables

## Usage

### Basic Usage

```python
from config.logging_config import get_logger

logger = get_logger(__name__)

# Simple messages
logger.info("operation_started")
logger.info("operation_completed", status="success")

# Structured context
logger.info(
    "fetch_price_completed",
    product_id="abc-123",
    url="https://example.com/product",
    duration_ms=250,
    price=99.99
)

# Error logging
try:
    result = risky_operation()
except Exception as e:
    logger.exception("operation_failed", operation="risky_operation")
```

### In Celery Tasks

No special configuration needed! Just import and use:

```python
from celery import shared_task
from config.logging_config import get_logger

logger = get_logger(__name__)

@shared_task
def my_task(param):
    logger.info("task_started", param=param)
    # ... do work ...
    logger.info("task_completed", param=param, result="success")
```

### Legacy Code Migration

If your code currently uses standard Python logging:

```python
# Old way (still works but not structured)
import logging
logger = logging.getLogger(__name__)
logger.info("Something happened")

# New way (structured logging)
from config.logging_config import get_logger
logger = get_logger(__name__)
logger.info("something_happened", detail="extra context")
```

Both approaches work, but structured logging provides better queryability in production.

## Log Output Examples

### Development Mode (Console with Colors)

```
2025-12-15T21:00:00.000000Z [info     ] fetch_price_started        app=pricetracker product_id=abc-123
2025-12-15T21:00:00.250000Z [info     ] fetch_price_completed      app=pricetracker product_id=abc-123 duration_ms=250 status=success
```

### Production/Celery Mode (JSON)

```json
{"event": "fetch_price_started", "level": "info", "timestamp": "2025-12-15T21:00:00.000000Z", "app": "pricetracker", "product_id": "abc-123"}
{"event": "fetch_price_completed", "level": "info", "timestamp": "2025-12-15T21:00:00.250000Z", "app": "pricetracker", "product_id": "abc-123", "duration_ms": 250, "status": "success"}
```

## Environment Configuration

The logging system auto-detects environment:

- **Development**: `DEBUG=True` → Colorful console output
- **Celery**: `CELERY_WORKER_NAME` exists → JSON output
- **Production**: `DEBUG=False` → JSON output

You can also manually specify environment in code:

```python
from config.logging_config import configure_structlog

# Force specific environment
configure_structlog(environment='production')
```

## Best Practices

### 1. Use Structured Keys

```python
# Good: Structured and queryable
logger.info("price_fetch_completed", product_id="123", price=99.99, currency="USD")

# Bad: Unstructured strings
logger.info(f"Fetched price {price} for product {product_id}")
```

### 2. Use Snake_Case Event Names

```python
# Good
logger.info("task_started")
logger.info("price_updated")
logger.info("pattern_generation_failed")

# Avoid
logger.info("Task Started")
logger.info("Price Updated!")
```

### 3. Include Relevant Context

```python
logger.info(
    "task_completed",
    task_name="fetch_price",
    duration_ms=duration,
    status="success" if success else "failed",
    product_id=product_id,
)
```

### 4. Use Appropriate Log Levels

- **DEBUG**: Detailed diagnostic information
- **INFO**: Normal operations and state changes
- **WARNING**: Unexpected but handled conditions
- **ERROR**: Errors that need attention but don't crash the app
- **EXCEPTION**: Errors with full stack traces (use logger.exception())

## Testing

Test the logging configuration:

```bash
# In Docker
docker-compose exec web python config/test_logging.py

# Or in Django shell
docker-compose exec web python manage.py shell
>>> from config.test_logging import test_logging_django
>>> test_logging_django()
```

## Future Enhancements

The logging configuration is ready for:

1. **Request ID tracking**: Add middleware to inject request IDs into all logs
2. **Log aggregation**: JSON output is ready for ELK, Datadog, CloudWatch, etc.
3. **Performance monitoring**: Add timing decorators for automatic duration tracking
4. **User context**: Bind user information to log context for audit trails

## Files

- `config/logging_config.py` - Centralized structlog configuration
- `config/test_logging.py` - Test script for logging configuration
- `app/apps.py` - Django app initialization (calls configure_structlog)
- `config/celery.py` - Celery worker initialization (calls configure_structlog)
- `config/settings.py` - Minimal Django LOGGING dict (compatibility)
