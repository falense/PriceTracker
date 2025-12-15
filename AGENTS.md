# PriceTracker - Agent Reference

## Running the Project

**Default: Docker Compose**
```bash
docker compose up -d
```

Services: `web` (8000), `celery`, `celery-beat`, `redis` (6379), `flower` (5555)

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
│  │  :6379   │      │  - Runs ExtractorPatternAgent       │  │
│  └────┬─────┘      │  - Runs PriceFetcher                │  │
│       │            │  - Processes async tasks            │  │
│       │            └─────────────────────────────────────┘  │
│       │                         │                            │
│       │                         │ subprocess calls           │
│       │                         ▼                            │
│       │            ┌─────────────────────────────────────┐  │
│       │            │  /extractor/generate_pattern.py     │  │
│       │            │  /fetcher/scripts/run_fetch.py      │  │
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
| `WebUI/app/tasks.py` | Celery task definitions |
| `WebUI/config/celery.py` | Beat schedule (5-min aggregated priority) |
| `ExtractorPatternAgent/generate_pattern.py` | Pattern generation |
| `PriceFetcher/scripts/run_fetch.py` | Price fetching |

## Task Flow

1. **User adds product URL** → WebUI creates Product + Listing + Subscription
2. **Pattern needed?** → Celery triggers `generate_pattern.py` via subprocess
3. **Every 5 minutes** → `fetch_prices_by_aggregated_priority` queues due products
4. **Price fetched** → Updates Listing, creates PriceHistory, triggers Notifications
