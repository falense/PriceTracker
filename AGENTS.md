# PriceTracker - Agent Reference

## Running the Project

**Default: Docker Compose**
```bash
docker compose up -d
```

Services: `web` (8000), `celery`, `celery-beat`, `redis` (6379), `flower` (5555)

## Testing

All automated tests must run inside the already running Docker Compose stack so they use the exact deployment containers. Make sure `docker compose up -d` is active, then exec into the `web` service:

```bash
# Example invocations
docker compose exec web pytest
docker compose exec web python manage.py test
```

## Technology Stack

| Component | Technology |
|-----------|------------|
| Web Framework | Django 4.2+ |
| Frontend | HTMX + Tailwind CSS |
| Task Queue | Celery + Redis |
| Database | SQLite (shared `db.sqlite3`) |
| Browser Automation | Playwright |
| HTML Parsing | BeautifulSoup4, lxml |

## Component Relationships

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Compose                            │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────┐      ┌─────────────────────────────────────┐  │
│  │  Redis   │◄────►│  Celery Worker                      │  │
│  │  :6379   │      │  - Imports PatternGenerator         │  │
│  └────┬─────┘      │  - Imports celery_api               │  │
│       │            │  - Processes async tasks            │  │
│       │            └─────────────────────────────────────┘  │
│       │                         │                            │
│       │                         │ direct function calls      │
│       │                         ▼                            │
│       │            ┌─────────────────────────────────────┐  │
│       │            │  PatternGenerator.generate()        │  │
│       │            │  fetch_listing_price_direct()       │  │
│       │            │  backfill_images_direct()           │  │
│       │            └─────────────────────────────────────┘  │
│       │                         │                            │
│       ▼                         ▼                            │
│  ┌──────────┐      ┌─────────────────────────────────────┐  │
│  │  WebUI   │      │           db.sqlite3                │  │
│  │  :8000   │─────►│  - Products, Stores, Listings       │  │
│  └──────────┘      │  - Subscriptions, Patterns          │  │
│                    │  - Price History, Notifications     │  │
│                    └─────────────────────────────────────┘  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Data Model (Multi-Store)

```
Product (normalized)
  ├── ProductListing (per store, has URL + price)
  │     └── Store (domain, rate limits)
  └── UserSubscription (per user, has priority)
```

## Key Files

| Path | Purpose |
|------|---------|
| `docker-compose.yml` | Service orchestration |
| `WebUI/app/models.py` | Database models |
| `WebUI/app/tasks.py` | Celery task definitions (uses direct imports) |
| `WebUI/config/celery.py` | Beat schedule (5-min aggregated priority) |
| `ExtractorPatternAgent/src/pattern_generator.py` | PatternGenerator class API |
| `PriceFetcher/src/celery_api.py` | Direct Celery integration functions |

## Task Flow

1. **User adds product URL** → WebUI creates Product + Listing + Subscription
2. **Pattern needed?** → Celery task imports `PatternGenerator` and calls `generate()` method directly
3. **Every 5 minutes** → `fetch_prices_by_aggregated_priority` queues due products
4. **Price fetched** → Celery task imports `fetch_listing_price_direct()` and calls it directly
5. **Result stored** → Updates Listing, creates PriceHistory, triggers Notifications

## Architecture Details

### Direct Import Pattern

The system uses **direct Python imports** instead of subprocess calls:

**Old (subprocess-based):**
```python
# ❌ Legacy approach
subprocess.run(['python', '/extractor/generate_pattern.py', url])
```

**New (direct import):**
```python
# ✅ Current approach
from ExtractorPatternAgent import PatternGenerator
generator = PatternGenerator()
pattern_data = await generator.generate(url, domain)
```

**Benefits:**
- Better performance (no subprocess overhead)
- Proper async/await support
- Easier debugging and error handling
- Type safety and IDE support
- Shared logging context

### Celery Task Examples

**Pattern Generation:**
```python
from celery import shared_task
from ExtractorPatternAgent import PatternGenerator

@shared_task
def generate_pattern(url: str, domain: str):
    return asyncio.run(_generate_async(url, domain))

async def _generate_async(url: str, domain: str):
    generator = PatternGenerator()
    pattern_data = await generator.generate(url, domain)
    # Save to database...
    return pattern_data
```

**Price Fetching:**
```python
from celery import shared_task
from PriceFetcher.src.celery_api import fetch_listing_price_direct

@shared_task
def fetch_listing_price(listing_id: str):
    return asyncio.run(_fetch_async(listing_id))

async def _fetch_async(listing_id: str):
    db_path = str(settings.DATABASES['default']['NAME'])
    result = await fetch_listing_price_direct(
        listing_id=listing_id,
        db_path=db_path
    )
    return result
```
