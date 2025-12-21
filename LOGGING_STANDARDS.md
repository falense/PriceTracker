# Logging Standards

## Structured Logging with Structlog

All services in PriceTracker use **structlog** for consistent, structured logging that outputs JSON logs to the database via `OperationLog`.

## Field Name Standards

### Error and Warning Fields

**RULE: `errors` and `warnings` fields MUST always be arrays of strings (lists)**

#### ✅ Correct Usage

```python
import structlog
logger = structlog.get_logger(__name__)

# Log with error messages
logger.error("validation_failed", errors=["Price not found", "Title too short"])

# Log with warnings
logger.warning("extraction_suspicious", warnings=["Price changed by 50%"])

# Empty arrays are OK
logger.info("validation_passed", errors=[], warnings=[])

# Single error - still wrap in array
logger.error("fetch_failed", errors=["Connection timeout"])
```

#### ❌ Incorrect Usage

```python
# DON'T: Log counts as integers
logger.info("validation_completed", errors=3, warnings=1)
# Use: errors=error_list instead, derive count with len() in template

# DON'T: Log single string
logger.error("fetch_failed", error="Connection timeout")
# Use: errors=["Connection timeout"]

# DON'T: Log with different types mixed
logger.error("validation_failed", errors=[1, 2, 3])
# Use: errors=["Error 1", "Error 2", "Error 3"]
```

### Why This Standard?

1. **Consistency**: Templates can always iterate over errors/warnings arrays
2. **No Type Checking**: No need to check if field is int, string, or list
3. **Better UX**: Users see actual error messages, not just counts
4. **Traceback Support**: Exception messages fit naturally in the array

### Common Patterns

#### Validation Results
```python
# In validation code
errors = []
warnings = []

if not price:
    errors.append("Price not found")
if price_change > 50:
    warnings.append(f"Price changed by {price_change}%")

logger.info("validation_completed", 
    valid=len(errors) == 0,
    errors=errors,
    warnings=warnings,
    confidence=confidence
)
```

#### Exception Handling
```python
try:
    result = fetch_page(url)
except Exception as e:
    logger.exception("fetch_failed", 
        url=url,
        errors=[str(e)]  # Wrap exception message in array
    )
    # logger.exception() automatically adds traceback to context
```

#### Storage Operations
```python
def log_fetch(self, success: bool, errors: List[str] = None, warnings: List[str] = None):
    logger.info("fetch_logged",
        success=success,
        errors=errors or [],  # Default to empty array
        warnings=warnings or []
    )
```

## Template Usage

With standardized array fields, templates can safely iterate:

```django
{% if errors %}
<div class="error-box">
    <strong>Errors:</strong>
    <ul>
        {% for error in errors %}
        <li>{{ error }}</li>
        {% endfor %}
    </ul>
</div>
{% endif %}
```

Count is derived automatically:
```django
<span>{{ errors|length }} error(s)</span>
```

## Migration Guide

### Before (Incorrect)
```python
logger.info("validation_completed", errors=len(errors), warnings=len(warnings))
```

### After (Correct)
```python
logger.info("validation_completed", errors=errors, warnings=warnings)
```

The template derives the count with `{{ errors|length }}`.

## Services Checklist

- [x] PriceFetcher - Uses structlog with `service="fetcher"`
- [x] ExtractorPatternAgent - Uses structlog with `service="extractor"`  
- [x] WebUI/Celery - Uses structlog with `service="celery"`
- [x] All logs stored in `OperationLog.context` as JSON

## References

- Structlog Documentation: https://www.structlog.org/
- OperationLog Model: `WebUI/app/models.py:861`
- Template Display: `WebUI/templates/product/subscription_detail.html`
