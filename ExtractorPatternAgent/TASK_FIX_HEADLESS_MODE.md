# Task: Fix ExtractorPatternAgent Headless Browser Mode

**Priority:** P0 - BLOCKING
**Component:** ExtractorPatternAgent
**Estimated Time:** 30-60 minutes
**Assignee:** Next Agent

## Problem Statement

The ExtractorPatternAgent fails when executed from Docker/Celery because Playwright tries to launch a headed browser, but there's no X server available.

## Error Details

**Error Message:**
```
playwright._impl._errors.TargetClosedError: BrowserType.launch: Target page, context or browser has been closed

Browser logs:
╔════════════════════════════════════════════════════════════════════════════════════════════════╗
║ Looks like you launched a headed browser without having a XServer running.                     ║
║ Set either 'headless: true' or use 'xvfb-run <your-playwright-app>' before running Playwright. ║
╚════════════════════════════════════════════════════════════════════════════════════════════════╝

[pid=30][err] Missing X server or $DISPLAY
[pid=30][err] The platform failed to initialize.  Exiting.
```

**Where it fails:**
- File: `generate_pattern.py`
- Line: ~39 (in `fetch_page()` function)
- Code: `browser = await p.chromium.launch(...)`

## Current Integration Status

**✅ What's Working:**
- Celery tasks trigger ExtractorPatternAgent correctly
- Subprocess call works
- Volume mount is correct (`/extractor` in Docker)
- Python dependencies are installed
- Playwright browsers are installed

**❌ What's Broken:**
- Browser launches in headed mode (requires X server)
- No headless configuration option

## Required Fix

### Location: `ExtractorPatternAgent/generate_pattern.py`

**Current code (approximately line 39):**
```python
async def fetch_page(url: str) -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            # Missing: headless=True
        )
        page = await browser.new_page()
        # ...
```

**Required change:**
```python
async def fetch_page(url: str) -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,  # ← ADD THIS
            args=[
                '--no-sandbox',  # Required for Docker
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',  # Prevents shared memory issues
            ]
        )
        page = await browser.new_page()
        # ...
```

### Optional: Configuration File

**Better approach:** Add to `config/settings.yaml`:

```yaml
browser:
  headless: true
  timeout: 30000
  args:
    - '--no-sandbox'
    - '--disable-setuid-sandbox'
    - '--disable-dev-shm-usage'
```

Then in `generate_pattern.py`:
```python
from config import load_config

config = load_config()
browser = await p.chromium.launch(
    headless=config['browser']['headless'],
    args=config['browser']['args']
)
```

## Testing Instructions

### 1. Test Locally (Quick)

```bash
cd ExtractorPatternAgent

# Test with headless mode
python generate_pattern.py "https://www.example.com/product" --domain example.com

# Should complete without X server errors
```

### 2. Test from WebUI Docker Container

```bash
# From project root
docker compose restart celery

# Trigger a pattern generation task
docker compose exec web python -c "
import os, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
django.setup()

from app.tasks import generate_pattern
task = generate_pattern.delay('https://example.com/test', 'example.com')
print(f'Task ID: {task.id}')

import time
time.sleep(5)

result = task.get(timeout=30)
print(f'Status: {result[\"status\"]}')
if result['status'] != 'failed':
    print('✓ SUCCESS - Pattern generation worked!')
else:
    print(f'✗ FAILED: {result[\"error\"][:200]}')
"
```

### 3. Full Integration Test

```bash
docker compose exec celery python test_docker_integration.py
```

**Expected output:**
```
--- Test 1: Generate Pattern Task ---
✓ Task triggered: <uuid>
✓ Task completed!
✓ Result: {'status': 'success', 'domain': 'example.com', ...}
✓ Pattern created in database
```

## Success Criteria

- [ ] `generate_pattern.py` launches browser in headless mode
- [ ] No X server or $DISPLAY errors
- [ ] Task completes successfully in Docker
- [ ] Pattern is saved to database
- [ ] Pattern JSON contains valid extraction rules

## Files to Modify

**Must change:**
- `generate_pattern.py` - Add `headless=True` to browser.launch()

**Optional (recommended):**
- `config/settings.yaml` - Add browser configuration section
- `src/tools/browser.py` - If browser launch is abstracted here

## Additional Context

### Why This Happens
Docker containers don't have a graphical environment by default. Playwright's Chromium needs to run in headless mode (no GUI) in server environments.

### Other Components to Check
If there are other files that launch browsers, apply the same fix:
- `src/tools/browser.py`
- `extractor-cli.py`
- Any test files that use Playwright

### Docker Environment Details
- Container: `pricetracker-celery-1`
- Volume mount: `/extractor` → `./ExtractorPatternAgent`
- Python path: `/usr/local/bin/python`
- Working directory: `/app`

## Related Issues

- ExtractorPatternAgent is called from: `WebUI/app/tasks.py:generate_pattern()`
- Task path: `docker exec celery python /extractor/generate_pattern.py`
- Database: Shared SQLite at `/app/db.sqlite3`

## Questions to Resolve

1. **Should headless mode be configurable?**
   - Recommendation: Yes, via config file for flexibility

2. **Do we need xvfb as fallback?**
   - Recommendation: No, headless mode is sufficient

3. **Should we add retry logic for browser launch failures?**
   - Recommendation: Celery already handles retries, but add timeout

## Contact

If you need clarification:
- Check: `WebUI/DOCKER_INTEGRATION_RESULTS.md` for full integration test results
- Check: `WebUI/app/tasks.py` to see how this component is called
- Run: `docker compose logs celery` to see error details

## Expected Outcome

After this fix:
```
User adds product → WebUI triggers Celery task → Task calls ExtractorPatternAgent →
Browser launches in headless mode → Page scraped successfully → Pattern extracted →
Pattern saved to database → Task returns success → User sees pattern in admin
```

---

**Status:** ✅ COMPLETED
**Last Updated:** 2025-12-14
**Completed By:** Claude Code
**Blocks:** None (resolved)
