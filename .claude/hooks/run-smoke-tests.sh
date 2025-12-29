#!/bin/bash
#
# Run smoke tests before Claude stops
# Exit 0: Tests pass, allow stop
# Exit 2: Tests fail, block stop and show errors to Claude

# Check if Docker container is running
if ! docker ps --filter "name=pricetracker-web-1" --format "{{.Names}}" | grep -q "pricetracker-web-1"; then
    echo "Warning: WebUI container is not running. Skipping smoke tests." >&2
    exit 0
fi

# Run smoke tests and capture output
TEST_OUTPUT=$(docker exec pricetracker-web-1 python manage.py test app.test_smoke 2>&1)
TEST_EXIT_CODE=$?

# If tests passed, allow Claude to stop
if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo "✓ All smoke tests passed (40/40)"
    exit 0
fi

# Tests failed - extract failure summary and block Claude from stopping
echo "❌ Smoke tests failed - pages are broken!" >&2
echo "" >&2
echo "Failed tests:" >&2
echo "$TEST_OUTPUT" | grep -E "FAIL:|ERROR:" | head -20 >&2
echo "" >&2
echo "You must fix these broken pages before stopping." >&2

exit 2
