# Smoke Tests for WebUI

## Purpose

The smoke tests in `test_smoke.py` verify that all pages in the WebUI can render successfully without errors. This catches:

- ✅ Template syntax errors
- ✅ Missing templates
- ✅ Python exceptions in views
- ✅ Missing URL routes
- ✅ Authentication/permission issues
- ✅ Database query errors

## Running the Tests

### In Docker (Recommended)

```bash
# Run all smoke tests
docker exec pricetracker-web-1 python manage.py test app.test_smoke

# Run specific test class
docker exec pricetracker-web-1 python manage.py test app.test_smoke.PublicPagesTest

# Run with verbose output
docker exec pricetracker-web-1 python manage.py test app.test_smoke -v 2
```

### On Host (if Django environment is set up)

```bash
cd WebUI
python3 manage.py test app.test_smoke
```

## Test Coverage

### Public Pages (7 tests)
- Homepage, login, register, pricing, about
- Product detail (public view)
- Referral landing pages

### Authenticated Pages (13 tests)
- Dashboard, product list, add product, product endpoints
- Subscriptions, notifications
- User settings, referral settings
- Search and autocomplete

### Admin Pages (8 tests)
- Admin dashboard, logs, analytics, health monitoring
- Pattern status, flags, user management

### Permissions (4 tests)
- Authentication requirements
- Staff-only access controls
- User data isolation

### Endpoints (8 tests)
- POST-only endpoint validation
- Browser extension API
- Utility endpoints (image proxy, search)

## Quick Test After Changes

Run this after making template, view, or URL changes:

```bash
# Sequential (slower, ~21s)
docker exec pricetracker-web-1 python manage.py test app.test_smoke

# Parallel (faster, ~8s) - Recommended
docker exec pricetracker-web-1 python manage.py test app.test_smoke --parallel auto
```

Expected output:
```
Ran 40 tests in 6.5s

OK
```

If any test fails, it means a page is broken and needs to be fixed before deployment.

## Automatic Testing with Stop Hook

A Claude Code Stop hook automatically runs these smoke tests whenever Claude finishes responding. This ensures that all pages still render successfully before Claude stops working.

**How it works:**
- Hook is configured in `.claude/settings.json`
- Script located at `.claude/hooks/run-smoke-tests.sh`
- Runs automatically when Claude tries to stop
- If tests fail (exit code 2): Claude is blocked from stopping and must fix broken pages
- If tests pass (exit code 0): Claude can stop normally

**Hook behavior:**
- ✓ Tests pass → "✓ All smoke tests passed (40/40)" - Claude stops
- ✗ Tests fail → "❌ Smoke tests failed - pages are broken!" - Claude must fix issues

This provides automatic safety checking after code changes.

## What These Tests Don't Cover

❌ JavaScript functionality
❌ Visual appearance/CSS
❌ HTMX dynamic interactions
❌ Form submission logic (covered by other tests)
❌ Business logic (covered by service tests)

For those, you would need Playwright or other E2E testing tools.
