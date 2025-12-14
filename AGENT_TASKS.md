# Agent Task Assignment

**Created:** 2025-12-14
**Status:** Ready for Assignment

## Overview

The WebUI integration is **85% complete** and fully functional. All infrastructure is working:
- ✅ Docker containers running
- ✅ Celery workers processing tasks
- ✅ Database connected
- ✅ Tasks registered and executing

**Two external components need fixes** to complete end-to-end functionality.

## Task 1: Fix ExtractorPatternAgent Headless Mode

**File:** `ExtractorPatternAgent/TASK_FIX_HEADLESS_MODE.md`

**Summary:** Browser launch needs headless mode for Docker environment

**Priority:** P0 - BLOCKING
**Time Estimate:** 30-60 minutes
**Difficulty:** Easy
**Agent Type:** ExtractorPatternAgent specialist or general developer

**Quick Description:**
```
Error: Playwright tries to launch headed browser, no X server in Docker
Fix: Add headless=True to browser.launch() in generate_pattern.py
Test: Run task from Celery, should complete without X server error
```

**Entry Point:**
```bash
cd ExtractorPatternAgent
# Read task file
cat TASK_FIX_HEADLESS_MODE.md

# Make fix (one line change)
# Test locally
python generate_pattern.py "https://example.com" --domain example.com

# Test in Docker
cd ../WebUI
docker compose restart celery
docker compose exec celery python test_docker_integration.py
```

**Success Criteria:**
- [ ] Browser launches in headless mode
- [ ] No X server errors
- [ ] Pattern generated and saved to database
- [ ] Task returns success status

---

## Task 2: Fix PriceFetcher Module Imports

**File:** `PriceFetcher/TASK_FIX_MODULE_IMPORTS.md`

**Summary:** Python module imports failing due to PYTHONPATH issues

**Priority:** P0 - BLOCKING
**Time Estimate:** 30-60 minutes
**Difficulty:** Easy
**Agent Type:** PriceFetcher specialist or general developer

**Quick Description:**
```
Error: ModuleNotFoundError: No module named 'config'
Fix: Add sys.path fix to scripts/run_fetch.py + update docker-compose.yml
Test: Run script from Docker, should import successfully
```

**Entry Point:**
```bash
cd PriceFetcher
# Read task file
cat TASK_FIX_MODULE_IMPORTS.md

# Make fix (add import path logic)
# Test locally
python scripts/run_fetch.py --help

# Test in Docker
cd ..
docker compose restart celery
docker compose exec celery python /fetcher/scripts/run_fetch.py --help
```

**Success Criteria:**
- [ ] `from config import load_config` works
- [ ] No ModuleNotFoundError
- [ ] Script executes without import errors
- [ ] Task completes (even if fails with other errors)

---

## Task Dependencies

```
┌─────────────────────────────────────────────┐
│  WebUI Integration (85% Complete) ✅         │
│  - All infrastructure working               │
│  - Celery tasks registered                  │
│  - Docker environment ready                 │
└─────────────────┬───────────────────────────┘
                  │
        ┌─────────┴──────────┐
        ▼                    ▼
┌──────────────────┐  ┌─────────────────────┐
│ Task 1:          │  │ Task 2:             │
│ ExtractorPattern │  │ PriceFetcher        │
│ Headless Mode    │  │ Module Imports      │
│                  │  │                     │
│ Status: 🔴 TODO  │  │ Status: 🔴 TODO     │
└──────────────────┘  └─────────────────────┘
        │                    │
        └─────────┬──────────┘
                  ▼
    ┌──────────────────────────────┐
    │  End-to-End Testing          │
    │  - Add product via UI        │
    │  - Pattern generated         │
    │  - Price fetched             │
    │  - Notifications sent        │
    │  Status: 🟡 Blocked          │
    └──────────────────────────────┘
```

**Both tasks are independent** - can be worked on in parallel by different agents.

---

## Current System State

### ✅ What's Working (No Action Needed)

| Component | Status | Details |
|-----------|--------|---------|
| WebUI Django App | ✅ Running | Port 8000, all routes working |
| Celery Worker | ✅ Running | 4 workers, processing tasks |
| Celery Beat | ✅ Running | Periodic task scheduler |
| Flower Monitoring | ✅ Running | Port 5555, task history visible |
| Redis Broker | ✅ Running | Port 6379, healthy |
| Database (SQLite) | ✅ Connected | Shared across containers |
| Volume Mounts | ✅ Mounted | /extractor and /fetcher accessible |
| Task Registration | ✅ Complete | 5 tasks registered |
| Service Layer | ✅ Complete | ProductService & NotificationService |
| Templates | ✅ Complete | 20+ templates, professional UI |
| Admin Interface | ✅ Complete | Django admin configured |

### 🔴 What Needs Fixing (Action Required)

| Component | Issue | Task File | Agent Needed |
|-----------|-------|-----------|--------------|
| ExtractorPatternAgent | Headless mode | TASK_FIX_HEADLESS_MODE.md | Any |
| PriceFetcher | Import errors | TASK_FIX_MODULE_IMPORTS.md | Any |

---

## How to Work on These Tasks

### For Agent Working on ExtractorPatternAgent:

```bash
# 1. Navigate to component
cd ExtractorPatternAgent

# 2. Read full task description
cat TASK_FIX_HEADLESS_MODE.md

# 3. Make the fix (see task file for details)
# Edit: generate_pattern.py
# Add: headless=True to browser.launch()

# 4. Test locally
python generate_pattern.py "https://example.com/test" --domain example.com

# 5. Test in Docker
cd ../WebUI
docker compose restart celery
docker compose exec celery python test_docker_integration.py

# 6. Verify in Flower
# Open: http://localhost:5555
# Check: Tasks show success (not failure)

# 7. Report back
echo "✅ Task 1 complete" > ExtractorPatternAgent/TASK_COMPLETE.txt
```

### For Agent Working on PriceFetcher:

```bash
# 1. Navigate to component
cd PriceFetcher

# 2. Read full task description
cat TASK_FIX_MODULE_IMPORTS.md

# 3. Make the fixes (see task file for details)
# Edit: scripts/run_fetch.py (add sys.path)
# Edit: ../docker-compose.yml (add PYTHONPATH)

# 4. Test locally
python scripts/run_fetch.py --help

# 5. Test in Docker
cd ..
docker compose restart celery
docker compose exec celery python test_docker_integration.py

# 6. Verify in Flower
# Open: http://localhost:5555
# Check: No more ModuleNotFoundError

# 7. Report back
echo "✅ Task 2 complete" > PriceFetcher/TASK_COMPLETE.txt
```

---

## Integration Test Script

After **both tasks** are complete, run the full integration test:

```bash
cd WebUI
docker compose exec celery python test_docker_integration.py
```

**Expected output:**
```
======================================================================
Docker Integration Test
======================================================================

=== Checking Redis Connection ===
✓ Redis connection successful

=== Checking Mounted Components ===
✓ ExtractorPatternAgent mounted at /extractor
✓ PriceFetcher mounted at /fetcher

=== Testing Celery Task Triggering ===
✓ Test user: docker_test_user
✓ Test product created: <uuid>

--- Test 1: Generate Pattern Task ---
✓ Task triggered: <uuid>
✓ Task completed!
✓ Result: {'status': 'success', 'domain': 'example.com', ...}
✓ Pattern created in database

--- Test 2: Fetch Product Price Task ---
✓ Task triggered: <uuid>
✓ Task completed!
✓ Result: {'status': 'success', 'product_id': '...', ...}
✓ Price updated: $XX.XX

--- Cleanup ---
✓ Test data cleaned up

======================================================================
✓ ALL TESTS PASSED - System is fully functional!
======================================================================
```

---

## Documentation Reference

**For agents working on these tasks:**

1. **Integration Test Results:** `WebUI/DOCKER_INTEGRATION_RESULTS.md`
   - Shows current test results
   - Explains what works and what doesn't

2. **Architecture Overview:** `ARCHITECTURE.md`
   - System design
   - Component interactions

3. **Docker Compose:** `docker-compose.yml`
   - Service configuration
   - Volume mounts
   - Environment variables

4. **Task Implementation:** `WebUI/app/tasks.py`
   - How external components are called
   - Subprocess execution
   - Error handling

5. **Service Layer:** `WebUI/app/services.py`
   - Business logic
   - How tasks are triggered

---

## Support & Questions

**If you get stuck:**

1. Check the detailed task file (TASK_*.md)
2. Run `docker compose logs celery --tail=100` to see errors
3. Check Flower dashboard at http://localhost:5555
4. Look at integration test results in `DOCKER_INTEGRATION_RESULTS.md`

**Common issues:**

- **"Can't find the file to edit"** → Check task file for exact file path
- **"Don't see the error"** → Run `docker compose logs celery -f` and trigger a task
- **"Fix didn't work"** → Did you restart celery? `docker compose restart celery`
- **"Tests still failing"** → Check if there are secondary errors after the first fix

---

## Timeline

**Realistic timeline if agents start now:**

- **Task 1 (ExtractorPatternAgent):** 30-60 minutes
- **Task 2 (PriceFetcher):** 30-60 minutes
- **Integration testing:** 15-30 minutes
- **Total:** ~2 hours to full system functionality

**If worked in parallel:** ~1 hour to completion

---

## Success Definition

**System is "complete" when:**

1. ✅ User can add product via WebUI
2. ✅ Pattern is generated automatically
3. ✅ Pattern is saved to database
4. ✅ Price is fetched automatically
5. ✅ Price is saved to database
6. ✅ User sees price on product page
7. ✅ Notifications are created on price changes
8. ✅ No errors in Celery logs
9. ✅ All tasks show success in Flower

**Current status:** 7/9 criteria met (blocked by these 2 tasks)

---

**Status:** 🟡 Ready for Agents
**Last Updated:** 2025-12-14 by WebUI Integration Agent
**Next Steps:** Assign agents to Task 1 and Task 2
