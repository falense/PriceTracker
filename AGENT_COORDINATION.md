# PriceTracker - Agent Coordination Guide

## Overview

This file coordinates work across all three components of the PriceTracker system. Each component has its own `IMPLEMENTATION_STATUS.md` file with detailed tasks, but this file provides the big picture and dependencies.

## System Architecture (Quick Reference)

```
User Browser
    ↓ (HTTP/HTMX)
┌─────────────────────────┐
│  WebUI (Django)         │
│  - Add product          │
│  - View prices          │
│  - Manage alerts        │
└───────┬─────────────────┘
        │ (Celery Tasks)
        ↓
┌─────────────────────────┐         ┌──────────────────────────┐
│ ExtractorPatternAgent   │────────→│  Shared SQLite Database  │
│ - Generate patterns     │         │  - app_product           │
│ - Analyze HTML          │         │  - app_pricehistory      │
│ - Save to DB            │         │  - app_pattern           │
└─────────────────────────┘         │  - app_fetchlog          │
                                    └─────────┬────────────────┘
                                              │
┌─────────────────────────┐                   │
│  PriceFetcher           │←──────────────────┘
│  - Load patterns        │
│  - Fetch prices         │
│  - Store results        │
└─────────────────────────┘
```

## Component Status Summary

| Component | Status | Blocking Issues | Ready for |
|-----------|--------|-----------------|-----------|
| **WebUI** | 70% | Missing Celery tasks, Templates TBD | Agent work after P0 |
| **PriceFetcher** | 80% | Database path, Entry script | Agent work after P0 |
| **ExtractorPatternAgent** | 60% | Database storage, Tool testing | Agent work after P0 |

## Critical Path: Integration Points

These are the **must-fix** issues that block the entire system:

### 🔴 Issue 1: Database Consistency (ALL COMPONENTS)

**Problem**: ExtractorPatternAgent saves to wrong database

**Files Affected**:
- `ExtractorPatternAgent/src/tools/storage.py`
- `PriceFetcher/src/storage.py`
- `PriceFetcher/src/pattern_loader.py`

**Fix Priority**: P0 - CRITICAL
**Estimated Time**: 2-3 hours
**Dependencies**: None

**Action**:
1. Update ExtractorPatternAgent storage tools to use `../db.sqlite3`
2. Use Django table names: `app_pattern`, `app_product`, `app_pricehistory`
3. Test integration: pattern saved by agent → loaded by fetcher

**Test**:
```bash
# Run from root directory
cd ExtractorPatternAgent
python tests/test_storage_integration.py  # Should pass

cd ../PriceFetcher
python tests/test_django_integration.py   # Should pass
```

### 🔴 Issue 2: Missing Celery Tasks (WebUI)

**Problem**: WebUI references tasks that don't exist

**Files Affected**:
- `WebUI/app/tasks.py` (doesn't exist - needs creation)
- `WebUI/app/services.py` (imports broken tasks)

**Fix Priority**: P0 - CRITICAL
**Estimated Time**: 3-4 hours
**Dependencies**: Issue 1 must be fixed first

**Action**:
1. Create `WebUI/app/tasks.py` with three tasks:
   - `generate_pattern(url, domain)`
   - `fetch_product_price(product_id)`
   - `fetch_prices(priority)`
2. Update `app/services.py` to import tasks correctly
3. Test tasks run via Celery

**Test**:
```bash
cd WebUI
celery -A config inspect registered  # Should show tasks
python test_integration.py  # End-to-end test
```

### 🔴 Issue 3: Database Path Configuration (PriceFetcher)

**Problem**: Hardcoded relative paths break in Docker

**Files Affected**:
- `PriceFetcher/src/fetcher.py`
- `PriceFetcher/src/storage.py`
- `PriceFetcher/src/pattern_loader.py`

**Fix Priority**: P0 - CRITICAL
**Estimated Time**: 1-2 hours
**Dependencies**: None

**Action**:
1. Add environment variable support: `DATABASE_PATH`
2. Update all classes to accept optional `db_path` parameter
3. Test with custom database path

**Test**:
```bash
export DATABASE_PATH=/custom/path/db.sqlite3
cd PriceFetcher
python scripts/run_fetch.py --db-path $DATABASE_PATH
```

## Work Distribution Strategy

### Option A: Sequential (Recommended for Single Agent)

Work through components in dependency order:

**Week 1: Database Layer**
- Day 1-2: Fix ExtractorPatternAgent storage (Issue 1)
- Day 3-4: Fix PriceFetcher database paths (Issue 3)
- Day 5: Integration testing

**Week 2: WebUI Integration**
- Day 1-3: Create Celery tasks (Issue 2)
- Day 4: Test end-to-end flow
- Day 5: Fix bugs found in testing

**Week 3: Completion**
- Day 1-2: Templates and frontend
- Day 3-4: Docker deployment
- Day 5: Final testing and documentation

### Option B: Parallel (Multiple Agents)

Assign each component to a separate agent:

**Agent 1: WebUI**
- Read: `WebUI/IMPLEMENTATION_STATUS.md`
- Priority: P0 tasks (Celery tasks, Dockerfile)
- Coordinate: Needs Agent 2 to complete storage first

**Agent 2: ExtractorPatternAgent**
- Read: `ExtractorPatternAgent/IMPLEMENTATION_STATUS.md`
- Priority: P0 tasks (Database storage, Tool testing)
- **Start First**: This unblocks other agents

**Agent 3: PriceFetcher**
- Read: `PriceFetcher/IMPLEMENTATION_STATUS.md`
- Priority: P0 tasks (Database paths, Entry script)
- Can work in parallel with Agent 2

## Component-Specific Starting Points

### Working on WebUI?

**Read First**:
1. `WebUI/IMPLEMENTATION_STATUS.md` - Detailed task list
2. `WebUI/app/models.py` - Understand data model
3. `ARCHITECTURE.md` - System overview

**Start With**:
- Task 1: Create `app/tasks.py` (see IMPLEMENTATION_STATUS.md)
- Verify Django models work: `python manage.py migrate`
- Test admin: `python manage.py createsuperuser`, visit `/admin`

**Key Files**:
- `app/tasks.py` - **NEEDS CREATION**
- `app/services.py` - Update imports
- `config/celery.py` - Already configured
- `requirements.txt` - Add celery, redis

**Test Command**:
```bash
cd WebUI
python test_integration.py
```

### Working on PriceFetcher?

**Read First**:
1. `PriceFetcher/IMPLEMENTATION_STATUS.md` - Detailed task list
2. `PriceFetcher/src/fetcher.py` - Main orchestrator
3. `../WebUI/app/models.py` - Django table schema

**Start With**:
- Task 1: Fix database path (see IMPLEMENTATION_STATUS.md)
- Task 2: Test Django integration
- Task 3: Create entry script

**Key Files**:
- `src/fetcher.py` - Line 25: fix db_path
- `src/storage.py` - Fix table names
- `scripts/run_fetch.py` - **NEEDS CREATION**

**Test Command**:
```bash
cd PriceFetcher
python tests/test_django_integration.py
python scripts/run_fetch.py --verbose
```

### Working on ExtractorPatternAgent?

**Read First**:
1. `ExtractorPatternAgent/IMPLEMENTATION_STATUS.md` - Detailed task list
2. `ExtractorPatternAgent/ARCHITECTURE.md` - Agent design
3. Claude Agent SDK documentation (`.claude/skills/agent-sdk/`)

**Start With**:
- Task 1: Fix database storage (CRITICAL - see IMPLEMENTATION_STATUS.md)
- Task 2: Verify MCP tools work
- Task 3: Test agent generates patterns

**Key Files**:
- `src/tools/storage.py` - **FIX DATABASE PATH**
- `src/agent.py` - Main agent class
- `src/tools/` - All MCP tools

**Test Command**:
```bash
cd ExtractorPatternAgent
pytest tests/test_tools.py -v
uv run extractor-cli.py generate https://example.com/product
```

## Integration Testing (After P0 Complete)

Once all P0 tasks are done, run this end-to-end test:

**Script**: `scripts/test_end_to_end.sh`

```bash
#!/bin/bash
set -e

echo "=== PriceTracker End-to-End Integration Test ==="

# 1. Setup Django
echo "1. Setting up Django database..."
cd WebUI
python manage.py migrate
python manage.py shell <<EOF
from django.contrib.auth.models import User
User.objects.get_or_create(username='testuser', email='test@example.com')
EOF

# 2. Test ExtractorPatternAgent
echo "2. Testing ExtractorPatternAgent..."
cd ../ExtractorPatternAgent
uv run scripts/generate_pattern.py "https://example.com/product/123" --domain "example.com"

# 3. Verify pattern saved
echo "3. Verifying pattern in database..."
cd ../WebUI
python manage.py shell <<EOF
from app.models import Pattern
p = Pattern.objects.get(domain='example.com')
print(f"Pattern found: {p.domain}, confidence: {p.success_rate}")
EOF

# 4. Test PriceFetcher
echo "4. Testing PriceFetcher..."
cd ../PriceFetcher
python scripts/run_fetch.py --db-path ../db.sqlite3 --verbose

# 5. Verify price saved
echo "5. Verifying price in database..."
cd ../WebUI
python manage.py shell <<EOF
from app.models import Product, PriceHistory
products = Product.objects.all()
print(f"Products: {products.count()}")
for p in products:
    print(f"- {p.name}: ${p.current_price}")
    history = p.price_history.count()
    print(f"  Price history: {history} entries")
EOF

echo "=== Test Complete ==="
```

Run:
```bash
chmod +x scripts/test_end_to_end.sh
./scripts/test_end_to_end.sh
```

## Docker Deployment (After Integration Tests Pass)

Once integration tests pass, deploy with Docker Compose:

**Pre-flight Checklist**:
- [ ] All P0 tasks complete
- [ ] Integration tests pass
- [ ] Dockerfiles exist for all components
- [ ] `docker-compose.yml` updated

**Deploy**:
```bash
# Build all images
docker-compose build

# Start services
docker-compose up -d

# Check logs
docker-compose logs -f

# Run migrations
docker-compose exec web python manage.py migrate

# Create admin user
docker-compose exec web python manage.py createsuperuser

# Test health
curl http://localhost:8000/health
curl http://localhost:5555  # Flower (Celery monitoring)

# Add test product via admin or API
# Wait for pattern generation + price fetch
# Check results
```

## Troubleshooting Guide

### Problem: Celery tasks not running

**Symptoms**:
- Tasks queued but never execute
- Celery logs show no activity
- Product added but no pattern/price fetched

**Debug**:
```bash
# Check Celery worker is running
docker-compose ps celery

# Check task is registered
docker-compose exec celery celery -A config inspect registered

# Check Redis connection
docker-compose exec redis redis-cli ping

# Check task queue
docker-compose exec celery celery -A config inspect reserved

# Manual test
docker-compose exec web python manage.py shell
>>> from app.tasks import generate_pattern
>>> task = generate_pattern.delay('https://example.com/product', 'example.com')
>>> print(task.id)
>>> task.status  # Should be 'PENDING', then 'SUCCESS' or 'FAILURE'
```

### Problem: Database locked

**Symptoms**:
- `sqlite3.OperationalError: database is locked`
- Concurrent write failures

**Solution**:
```bash
# Reduce Celery concurrency
docker-compose up -d --scale celery=1

# In docker-compose.yml, change:
# command: celery -A config worker -l info --concurrency=1

# Long-term: Migrate to PostgreSQL
```

### Problem: Pattern not found for domain

**Symptoms**:
- PriceFetcher logs: "No pattern found for domain X"
- Product added but never fetched

**Debug**:
```bash
# Check if pattern exists
docker-compose exec web python manage.py shell
>>> from app.models import Pattern
>>> Pattern.objects.all()
>>> Pattern.objects.get(domain='example.com')  # Should exist

# Check ExtractorPatternAgent ran
docker-compose logs celery | grep generate_pattern

# Manually trigger pattern generation
docker-compose exec web python manage.py shell
>>> from app.tasks import generate_pattern
>>> generate_pattern.delay('https://example.com/product', 'example.com')
```

### Problem: Imports fail in Docker

**Symptoms**:
- `ModuleNotFoundError: No module named 'app'`
- `ImportError: attempted relative import`

**Solution**:
```dockerfile
# In Dockerfile, add:
ENV PYTHONPATH=/app:$PYTHONPATH
WORKDIR /app

# Check working directory
docker-compose exec web pwd  # Should be /app

# Check Python path
docker-compose exec web python -c "import sys; print(sys.path)"
```

## Success Criteria

System is ready for production when:

- [ ] **P0 Complete**: All critical issues fixed
  - [ ] Database consistency across components
  - [ ] Celery tasks implemented and working
  - [ ] Database paths configurable

- [ ] **Integration Tests Pass**
  - [ ] End-to-end test passes
  - [ ] Can add product via WebUI
  - [ ] Pattern generated and saved
  - [ ] Price fetched and displayed

- [ ] **Docker Deployment Works**
  - [ ] All containers start successfully
  - [ ] Health checks passing
  - [ ] Can access WebUI at localhost:8000
  - [ ] Celery tasks execute

- [ ] **Monitoring in Place**
  - [ ] Flower shows task activity
  - [ ] Logs structured and readable
  - [ ] Can track fetch success rate

## Next Steps After MVP

Once MVP is working:

1. **Security Hardening**
   - Add authentication (postponed for MVP)
   - Rate limiting
   - Input validation

2. **Scalability**
   - Migrate to PostgreSQL
   - Add Redis caching
   - Horizontal scaling

3. **Features**
   - Email notifications
   - Mobile app
   - Advanced analytics
   - Multi-user support

4. **Monitoring**
   - Prometheus metrics
   - Grafana dashboards
   - Alerting system

## Questions / Issues?

If you encounter issues not covered here:

1. Check component-specific `IMPLEMENTATION_STATUS.md`
2. Review `ARCHITECTURE.md` for design decisions
3. Check `DEPLOYMENT.md` for deployment specifics
4. Consult individual component READMEs

## Quick Reference

**Database Tables** (Django):
- `app_product` - Tracked products
- `app_pricehistory` - Historical prices
- `app_pattern` - Extraction patterns
- `app_fetchlog` - Fetch attempt logs
- `app_notification` - User notifications
- `app_userview` - Analytics
- `app_adminflag` - Admin alerts

**Key Environment Variables**:
- `DATABASE_PATH` - Path to shared SQLite database
- `REDIS_URL` - Redis connection string
- `CELERY_BROKER_URL` - Celery broker URL
- `DEBUG` - Django debug mode
- `SECRET_KEY` - Django secret key

**Common Commands**:
```bash
# Django
python manage.py migrate
python manage.py runserver
python manage.py shell

# Celery
celery -A config worker -l info
celery -A config beat -l info
celery -A config inspect registered

# Docker
docker-compose up -d
docker-compose logs -f [service]
docker-compose exec [service] [command]

# Testing
pytest tests/ -v
python test_integration.py
./scripts/test_end_to_end.sh
```

---

**Last Updated**: 2025-12-14
**Status**: Components implemented (draft), integration pending
**Next Milestone**: Complete P0 tasks, pass integration tests
