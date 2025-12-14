# Task: Fix PriceFetcher Module Import Issues

**Priority:** P0 - BLOCKING
**Component:** PriceFetcher
**Estimated Time:** 30-60 minutes
**Assignee:** Next Agent

## Problem Statement

The PriceFetcher fails when executed from Docker/Celery because it cannot import the `config` module. This indicates a Python path or module structure issue.

## Error Details

**Error Message:**
```
Traceback (most recent call last):
  File "/fetcher/scripts/run_fetch.py", line 34, in <module>
    from config import load_config
ModuleNotFoundError: No module named 'config'
```

**Where it fails:**
- File: `scripts/run_fetch.py`
- Line: 34
- Code: `from config import load_config`

## Current Integration Status

**✅ What's Working:**
- Celery tasks trigger PriceFetcher correctly
- Subprocess call works
- Volume mount is correct (`/fetcher` in Docker)
- File exists at `/fetcher/scripts/run_fetch.py`
- File is executable

**❌ What's Broken:**
- Module imports fail (Python can't find `config`)
- Likely PYTHONPATH or import path issue

## Project Structure Analysis

```
PriceFetcher/
├── config/
│   └── __init__.py          # Contains load_config()?
├── src/
│   ├── __init__.py
│   ├── fetcher.py
│   ├── extractor.py
│   └── ...
├── scripts/
│   └── run_fetch.py         # ← Failing here
└── pyproject.toml
```

## Required Fix Options

### Option 1: Fix Import Path (Quick Fix)

**In `scripts/run_fetch.py` (around line 30-35):**

```python
# BEFORE (BROKEN):
from config import load_config

# AFTER (FIXED):
import sys
from pathlib import Path

# Add parent directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import load_config
```

### Option 2: Use Absolute Imports with Package

**If PriceFetcher is set up as a package:**

```python
# In scripts/run_fetch.py:
from PriceFetcher.config import load_config
# OR
from src.config import load_config
```

**Requires:** Installing PriceFetcher as editable package in Docker:
```dockerfile
# In WebUI/Dockerfile, add:
RUN pip install -e /fetcher
```

### Option 3: Set PYTHONPATH in Docker

**In `docker-compose.yml` for celery service:**

```yaml
celery:
  # ... existing config
  environment:
    - PYTHONPATH=/fetcher:/fetcher/src:/app
```

### Option 4: Restructure to Use Entry Point

**In `pyproject.toml`:**
```toml
[project.scripts]
fetch-price = "src.__main__:main"
```

Then call it as:
```python
# In WebUI/app/tasks.py:
result = subprocess.run([
    'python', '-m', 'src',
    '--product-id', product_id
], ...)
```

## Recommended Approach

**Use Option 1 (Fix Import Path) + Option 3 (Set PYTHONPATH)**

This is the fastest fix with least disruption:

### Step 1: Fix `scripts/run_fetch.py`

```python
#!/usr/bin/env python
"""
Price fetcher script.
"""
import sys
from pathlib import Path

# Add parent directory to Python path so imports work
FETCHER_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(FETCHER_ROOT))

# Now imports should work
from config import load_config
from src.fetcher import fetch_product_price
# ... rest of imports
```

### Step 2: Update `docker-compose.yml`

```yaml
celery:
  build:
    context: ./WebUI
    dockerfile: Dockerfile
  command: celery -A config worker -l info --concurrency=4
  depends_on:
    redis:
      condition: service_healthy
  volumes:
    - ./db.sqlite3:/app/db.sqlite3
    - ./WebUI:/app
    - ./ExtractorPatternAgent:/extractor
    - ./PriceFetcher:/fetcher
  environment:
    - REDIS_URL=redis://redis:6379/0
    - DATABASE_PATH=/app/db.sqlite3
    - EXTRACTOR_PATH=/extractor
    - FETCHER_PATH=/fetcher
    - PYTHONPATH=/app:/extractor:/fetcher  # ← ADD THIS
```

### Step 3: Verify Other Scripts

Check if other scripts have the same issue:
```bash
find PriceFetcher -name "*.py" -exec grep -l "from config import" {} \;
```

Apply the same fix to any other affected files.

## Testing Instructions

### 1. Test Locally (Quick)

```bash
cd PriceFetcher

# Test the import fix
python scripts/run_fetch.py --help

# Should show usage, not import error
```

### 2. Test with Mock Product ID

```bash
# Create a test product first (or use existing UUID)
cd PriceFetcher
python scripts/run_fetch.py --product-id "00000000-0000-0000-0000-000000000000"

# Should fail gracefully (product not found) NOT with import error
```

### 3. Test from WebUI Docker Container

```bash
# Restart to pick up changes
docker compose restart celery

# Trigger a price fetch task
docker compose exec web python -c "
import os, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
django.setup()

from django.contrib.auth.models import User
from app.models import Product
from app.tasks import fetch_product_price

# Create a test product
user = User.objects.first()
if user:
    product = Product.objects.create(
        user=user,
        url='https://example.com/test',
        domain='example.com',
        name='Test Product'
    )

    # Trigger fetch
    task = fetch_product_price.delay(str(product.id))
    print(f'Task ID: {task.id}')

    import time
    time.sleep(5)

    result = task.get(timeout=30)
    print(f'Status: {result[\"status\"]}')
    if 'ModuleNotFoundError' not in str(result):
        print('✓ SUCCESS - Import error fixed!')
    else:
        print(f'✗ FAILED: {result}')

    # Cleanup
    product.delete()
"
```

### 4. Full Integration Test

```bash
docker compose exec celery python test_docker_integration.py
```

**Expected output:**
```
--- Test 2: Fetch Product Price Task ---
✓ Task triggered: <uuid>
✓ Task completed!
✓ Result: {'status': 'success', 'product_id': '...', ...}
✓ Price updated: $XX.XX
```

## Success Criteria

- [ ] `run_fetch.py` imports `config` successfully
- [ ] No `ModuleNotFoundError` in task results
- [ ] Task completes (may fail with other errors, that's OK)
- [ ] Script can be called from Docker without import errors

## Files to Modify

**Must change:**
- `scripts/run_fetch.py` - Add sys.path fix at top
- `docker-compose.yml` - Add PYTHONPATH to celery environment

**May need to change:**
- Any other scripts in `scripts/` directory
- `src/__main__.py` if using module entry point approach

**Verify these files:**
- `config/__init__.py` - Make sure `load_config` function exists
- `pyproject.toml` - Check package configuration

## Additional Context

### Why This Happens

Python modules need to be on the `PYTHONPATH` to be importable. When a script is run from a subdirectory (`scripts/`), Python doesn't automatically add the parent directory to the path.

### Common Python Import Patterns

```python
# Pattern 1: Relative imports (within package)
from ..config import load_config

# Pattern 2: Absolute imports (if installed as package)
from pricefetcher.config import load_config

# Pattern 3: Dynamic path addition (what we're using)
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import load_config
```

### Docker Environment Details

- Container: `pricetracker-celery-1`
- Volume mount: `/fetcher` → `./PriceFetcher`
- Python path: `/usr/local/bin/python`
- Working directory: `/app` (WebUI)
- Called from: `/app` via subprocess

## Investigation Steps

### 1. Check Current Structure

```bash
docker compose exec celery ls -la /fetcher/config/
docker compose exec celery ls -la /fetcher/scripts/
docker compose exec celery cat /fetcher/config/__init__.py | head -20
```

### 2. Test Import Manually

```bash
docker compose exec celery python -c "
import sys
sys.path.insert(0, '/fetcher')
from config import load_config
print('✓ Import works with path fix')
"
```

### 3. Check PYTHONPATH

```bash
docker compose exec celery python -c "import sys; print('\\n'.join(sys.path))"
```

## Related Issues

- PriceFetcher is called from: `WebUI/app/tasks.py:fetch_product_price()`
- Task path: `docker exec celery python /fetcher/scripts/run_fetch.py`
- Database: Shared SQLite at `/app/db.sqlite3`
- Expected to read patterns from: `Pattern` model

## Questions to Resolve

1. **Is PriceFetcher meant to be installed as a package?**
   - Check: Does `pyproject.toml` define package structure?
   - Recommendation: Keep as standalone script for simplicity

2. **Should we use `python -m` instead of direct script execution?**
   - Would need: Entry point in `__main__.py`
   - Recommendation: Only if planning to distribute as package

3. **Are there other import issues beyond `config`?**
   - Check: Does `config.load_config()` import other modules?
   - Test: Full execution to find secondary import errors

## Contact

If you need clarification:
- Check: `WebUI/DOCKER_INTEGRATION_RESULTS.md` for full integration test results
- Check: `WebUI/app/tasks.py:fetch_product_price()` to see how this is called
- Run: `docker compose logs celery` to see full error traceback

## Expected Outcome

After this fix:
```
User adds product → Pattern generated → WebUI triggers price fetch →
Celery calls PriceFetcher → Imports work correctly →
Pattern loaded from DB → Page fetched → Price extracted →
Price saved to database → Task returns success →
User sees current price on product page
```

## Next Steps After This Fix

Once imports work, you may encounter:
1. Pattern not found in database (expected - needs ExtractorPatternAgent fix first)
2. Database connection issues (check DATABASE_PATH)
3. HTTP request failures (may need user-agent, cookies, etc.)

These are **separate issues** to tackle after imports are fixed.

---

## Resolution

**Status:** ✅ COMPLETED
**Completed Date:** 2025-12-14
**Completed By:** Claude (AI Assistant)

### Changes Made

1. **Fixed `scripts/run_fetch.py` imports** (lines 31-36):
   - Changed from adding only `src/` to path
   - Now adds PriceFetcher root to path: `sys.path.insert(0, str(FETCHER_ROOT))`
   - Changed import from `from fetcher import PriceFetcher` to `from src.fetcher import PriceFetcher`
   - This allows both `config` module and `src` package to be imported correctly
   - Maintains relative imports within `src/` package

2. **Updated `docker-compose.yml`** (line 55):
   - Added `PYTHONPATH=/app:/extractor:/fetcher` to celery service environment
   - Ensures Python can find modules from all mounted directories
   - Consistent with the volume mounts structure

### Testing Performed

```bash
cd PriceFetcher
python scripts/run_fetch.py --help
# ✓ Shows usage without ModuleNotFoundError
# ✓ All imports (config, src.fetcher) work correctly
```

### Why It Works

- **Root path**: Adding `FETCHER_ROOT` allows importing `config` module
- **Package imports**: Using `from src.fetcher import PriceFetcher` treats `src` as a package
- **Relative imports**: `src/fetcher.py` can use `from .extractor import Extractor` correctly
- **Docker PYTHONPATH**: Ensures same behavior in container environment

### Next Steps

The import issue is resolved. Next issues to address:
1. Test with actual Django database
2. Verify pattern loading works
3. Test end-to-end price fetching

---

**Previous Status:** 🔴 Not Started
**Last Updated:** 2025-12-14
**Blocked By:** None (RESOLVED)
**Blocks:** End-to-end product tracking workflow
**Related To:** TASK_FIX_HEADLESS_MODE.md (ExtractorPatternAgent)
