# Claude Code Development Notes

## Important Conventions

### Python Version

**ALWAYS use `python3` command**, not `python`.

This project requires Python 3 and the `python` command may not be available on all systems. Always use `python3` for running scripts, tests, and other Python commands.

### Docker Compose

**ALWAYS use `docker compose` command**, not `docker-compose`.

This project uses Docker Compose V2 which is integrated into the Docker CLI. The standalone `docker-compose` command may not be available on all systems. Always use `docker compose` (with a space) for all Docker Compose operations:

```bash
# Correct
docker compose up -d
docker compose exec webui python manage.py migrate
docker compose stop

# Incorrect - may not work
docker-compose up -d
docker-compose exec webui python manage.py migrate
```

### Database Migrations

**Always run migrations in the Docker container**, not on the host machine.

To create and run migrations:

```bash
# Create migrations
docker exec -it <webui-container> python manage.py makemigrations --name <migration_name>

# Run migrations
docker exec -it <webui-container> python manage.py migrate
```

Or using docker compose:

```bash
# Create migrations
docker compose exec webui python manage.py makemigrations --name <migration_name>

# Run migrations
docker compose exec webui python manage.py migrate
```

This ensures migrations are created with the correct Python environment and database configuration.

### Smoke Tests

**Always update smoke tests when adding or removing pages/URLs.**

The project has comprehensive smoke tests in `WebUI/app/test_smoke.py` that verify all pages render successfully. A Stop hook automatically runs these tests before Claude can stop working.

**When you add a new page/view:**
1. Add a corresponding test method to the appropriate test class in `test_smoke.py`
2. Run tests to verify: `docker exec pricetracker-web-1 python manage.py test app.test_smoke --parallel auto`
3. Ensure the new test passes before committing

**When you remove a page/view:**
1. Remove the corresponding test method from `test_smoke.py`
2. Verify remaining tests still pass

**Test organization:**
- `PublicPagesTest` - Unauthenticated pages
- `AuthenticatedPagesTest` - User-authenticated pages
- `AdminPagesTest` - Staff-only pages
- `PermissionsTest` - Authorization checks
- `POSTEndpointsTest` - POST-only endpoint validation
- `BrowserExtensionAPITest` - Extension API endpoints
- `UtilityEndpointsTest` - Utility endpoints

The Stop hook will block Claude from stopping if any smoke test fails, ensuring broken pages are fixed immediately.

### Screenshot Tool

**ALWAYS take screenshots when the user asks about visual/UI issues.**

This is MANDATORY - never make suggestions about visual styling, layout, or UI appearance without first taking a screenshot to see what it actually looks like.

When working on UI bugs, layout problems, or any visual issues, take screenshots to see what the page actually looks like:

```bash
# Screenshot with existing session
./scripts/screenshot.sh --session local http://localhost:8000/page-url

# Screenshots are saved to .screenshots/ directory
# View the most recent screenshot with:
Read .screenshots/screenshot_localhost_8000_local_TIMESTAMP.png
```

**Common scenarios requiring screenshots:**
- User mentions page looks "messy", "broken", "weird", or similar
- User asks about styling improvements
- User reports layout issues
- User asks "what can be improved" for UI/UX
- Any discussion about visual appearance

See `scripts/README_SCREENSHOT.md` for full documentation including interactive login for creating sessions.
