# Price Tracker - Project Architecture

## Overview

AI-powered price tracking system consisting of:
1. **ExtractorPatternAgent** - AI agent that generates extraction patterns
2. **PriceFetcher** - Deterministic cron job that fetches prices using patterns
3. **WebUI** - Django + HTMX web interface for users

## System Design Philosophy

**AI where needed, deterministic where possible**
- Pattern generation is complex and benefits from AI reasoning
- Pattern execution is deterministic and doesn't need AI
- Cost-effective: AI calls only during pattern generation, not routine fetching

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  User (Browser)                         │
└────────────────────┬────────────────────────────────────┘
                     │ HTTP/HTMX
                     ▼
┌─────────────────────────────────────────────────────────┐
│              WebUI (Django + HTMX)                      │
│  - Dashboard (view tracked products)                    │
│  - Add product form                                     │
│  - Price history charts                                 │
│  - Notifications                                        │
│  - User tracking (views, engagement)                    │
│                                                          │
│  Triggers: ExtractorPatternAgent & PriceFetcher         │
└────────────────────┬────────────────────────────────────┘
                     │
                     │ Triggers on new product
                     ▼
┌─────────────────────────────────────────────────────────┐
│           ExtractorPatternAgent (AI)                    │
│  - Analyzes HTML structure                              │
│  - Generates CSS/XPath/JSON-LD patterns                 │
│  - Validates patterns work                              │
│  - Stores in patterns.db                                │
│                                                          │
│  Runs: Once per new product/domain                      │
│  Cost: ~$0.01-0.05 per pattern generation               │
└────────────────────┬────────────────────────────────────┘
                     │
                     │ Saves patterns
                     ▼
┌─────────────────────────────────────────────────────────┐
│              Shared SQLite Database                     │
│                                                          │
│  Tables:                                                │
│  - products (tracked items + user data)                 │
│  - price_history (time series data)                     │
│  - patterns (extraction rules)                          │
│  - user_views (engagement tracking)                     │
│  - notifications (price alerts)                         │
│  - fetch_logs (success/failure tracking)                │
└────────────────────┬────────────────────────────────────┘
                     │
                     │ Reads patterns & products
                     ▼
┌─────────────────────────────────────────────────────────┐
│          PriceFetcher (Cron Job)                        │
│  - Loads patterns                                        │
│  - Fetches product HTML                                 │
│  - Applies patterns (BeautifulSoup/XPath)               │
│  - Validates extracted data                             │
│  - Stores prices & creates notifications                │
│                                                          │
│  Runs: Every 15 min - 6 hours (configurable)            │
│  Cost: $0 (no AI calls)                                 │
└─────────────────────────────────────────────────────────┘
                     │
                     │ Updates displayed in real-time
                     ▼
┌─────────────────────────────────────────────────────────┐
│          WebUI (HTMX polling/updates)                   │
│  - Live price updates                                   │
│  - Notification badges                                  │
│  - Price drop alerts                                    │
│  - Historical charts                                    │
└─────────────────────────────────────────────────────────┘
```

## Component Interaction Flow

### Flow 1: New Product Added

```
1. User enters URL in WebUI form
   ↓
2. WebUI: ProductService.add_product()
   ↓
3. Check if pattern exists for domain
   ↓
4. NO → Trigger ExtractorPatternAgent (subprocess/Celery)
   ↓
5. Agent fetches page HTML
   ↓
6. Agent analyzes structure (LLM reasoning)
   ↓
7. Agent generates patterns
   ↓
8. Agent validates patterns
   ↓
9. Patterns saved to shared SQLite db
   ↓
10. Product record created with user association
   ↓
11. WebUI triggers immediate fetch
   ↓
12. PriceFetcher extracts first price
   ↓
13. HTMX updates UI with product card
```

### Flow 2: Routine Price Fetching

```
Cron triggers every 15 minutes
   ↓
1. PriceFetcher: Load patterns from db
   ↓
2. Get products due for checking
   ↓
3. For each product:
   a. Fetch HTML (httpx)
   b. Apply pattern (BeautifulSoup)
   c. Validate extraction
   d. Store price in price_history
   e. Update product.current_price
   f. Check for price drops
   ↓
4. Create notifications for significant changes
   ↓
5. Log results to fetch_logs
   ↓
6. WebUI polls for updates (HTMX every 30s)
   ↓
7. User sees live price updates
```

### Flow 3: Pattern Failure Recovery

```
PriceFetcher: Pattern extraction fails 3x
   ↓
1. Log failure in fetch_logs
   ↓
2. Alert/Queue for re-analysis
   ↓
3. ExtractorPatternAgent re-triggered
   ↓
4. Agent analyzes what changed
   ↓
5. Agent generates new patterns
   ↓
6. New patterns saved
   ↓
7. PriceFetcher resumes with new patterns
```

## Data Models

### Shared SQLite Database Schema

```sql
-- Single db.sqlite3 file used by all components

-- Django auth tables (auth_user, etc.)
-- Created by Django migrations

-- Products tracked by users
CREATE TABLE app_product (
    id VARCHAR(36) PRIMARY KEY,
    user_id INTEGER NOT NULL,
    url TEXT UNIQUE NOT NULL,
    domain TEXT NOT NULL,
    name TEXT,
    current_price DECIMAL(10, 2),
    currency VARCHAR(3) DEFAULT 'USD',
    available BOOLEAN DEFAULT TRUE,
    image_url TEXT,
    priority VARCHAR(10) DEFAULT 'normal',
    active BOOLEAN DEFAULT TRUE,
    check_interval INTEGER DEFAULT 3600,
    last_checked TIMESTAMP,
    view_count INTEGER DEFAULT 0,
    last_viewed TIMESTAMP,
    target_price DECIMAL(10, 2),
    notify_on_drop BOOLEAN DEFAULT TRUE,
    notify_on_restock BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    pattern_version VARCHAR(50),
    FOREIGN KEY (user_id) REFERENCES auth_user(id)
);

-- Price history time series
CREATE TABLE app_pricehistory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id VARCHAR(36) NOT NULL,
    price DECIMAL(10, 2),
    currency VARCHAR(3) DEFAULT 'USD',
    available BOOLEAN DEFAULT TRUE,
    extracted_data JSON,
    confidence REAL,
    recorded_at TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES app_product(id)
);

-- Extraction patterns per domain
CREATE TABLE app_pattern (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain VARCHAR(255) UNIQUE NOT NULL,
    pattern_json JSON NOT NULL,
    success_rate REAL DEFAULT 0.0,
    total_attempts INTEGER DEFAULT 0,
    successful_attempts INTEGER DEFAULT 0,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    last_validated TIMESTAMP
);

-- User product views (analytics)
CREATE TABLE app_userview (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    product_id VARCHAR(36) NOT NULL,
    viewed_at TIMESTAMP,
    duration_seconds INTEGER,
    FOREIGN KEY (user_id) REFERENCES auth_user(id),
    FOREIGN KEY (product_id) REFERENCES app_product(id)
);

-- User notifications
CREATE TABLE app_notification (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    product_id VARCHAR(36) NOT NULL,
    notification_type VARCHAR(20) NOT NULL,
    message TEXT,
    old_price DECIMAL(10, 2),
    new_price DECIMAL(10, 2),
    read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP,
    read_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES auth_user(id),
    FOREIGN KEY (product_id) REFERENCES app_product(id)
);

-- Fetch logs for debugging
CREATE TABLE app_fetchlog (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id VARCHAR(36) NOT NULL,
    success BOOLEAN NOT NULL,
    extraction_method VARCHAR(50),
    errors JSON,
    warnings JSON,
    duration_ms INTEGER,
    fetched_at TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES app_product(id)
);

-- Indexes
CREATE INDEX idx_product_user_active ON app_product(user_id, active);
CREATE INDEX idx_product_domain ON app_product(domain);
CREATE INDEX idx_product_last_checked ON app_product(last_checked);
CREATE INDEX idx_pricehistory_product_time ON app_pricehistory(product_id, recorded_at DESC);
CREATE INDEX idx_notification_user_read ON app_notification(user_id, read, created_at DESC);
CREATE INDEX idx_fetchlog_product_time ON app_fetchlog(product_id, fetched_at DESC);
```

## Technology Stack

### WebUI
- **Framework**: Django 4.2+
- **Frontend**: HTMX + TailwindCSS
- **Charts**: Chart.js
- **Auth**: Not implemented yet (postponed)
- **Async Tasks**: Celery + Redis
- **Storage**: SQLite (shared db.sqlite3)

### ExtractorPatternAgent
- **Language**: Python 3.11+
- **AI SDK**: claude-agent-sdk
- **Browser**: Playwright (for JS rendering)
- **Parsing**: BeautifulSoup4, lxml
- **Storage**: SQLite (shared db.sqlite3)

### PriceFetcher
- **Language**: Python 3.11+
- **HTTP**: httpx (async)
- **Parsing**: BeautifulSoup4, lxml
- **Storage**: SQLite (shared db.sqlite3)
- **Scheduler**: cron / systemd timers
- **Monitoring**: Prometheus metrics

### Shared
- **Database**: SQLite (single db.sqlite3 file)
- **Task Queue**: Celery + Redis
- **Data Validation**: Pydantic
- **Config**: YAML
- **Logging**: structlog
- **Testing**: pytest

## Directory Structure

```
PriceTracker/
├── ARCHITECTURE.md                    # This file
├── README.md
├── docker-compose.yml
├── db.sqlite3                         # Shared database (gitignored)
│
├── WebUI/                            # Django + HTMX interface
│   ├── ARCHITECTURE.md
│   ├── manage.py
│   ├── config/
│   │   ├── settings.py
│   │   ├── urls.py
│   │   └── wsgi.py
│   ├── app/
│   │   ├── models.py                 # Django models
│   │   ├── views.py                  # View functions
│   │   ├── services.py               # Business logic
│   │   └── forms.py
│   ├── templates/
│   │   ├── base.html
│   │   ├── dashboard.html
│   │   └── product/
│   │       └── partials/             # HTMX partials
│   ├── static/
│   │   ├── css/
│   │   └── js/
│   └── requirements.txt
│
├── ExtractorPatternAgent/
│   ├── ARCHITECTURE.md
│   ├── src/
│   │   ├── agent.py                  # Main agent class
│   │   ├── tools/                    # Custom MCP tools
│   │   │   ├── browser.py
│   │   │   ├── parser.py
│   │   │   ├── validator.py
│   │   │   └── storage.py
│   │   └── models/
│   │       └── pattern.py
│   ├── config/
│   │   └── settings.yaml
│   ├── scripts/
│   │   └── generate_pattern.py       # CLI interface
│   ├── tests/
│   └── requirements.txt
│
├── PriceFetcher/
│   ├── ARCHITECTURE.md
│   ├── src/
│   │   ├── fetcher.py               # Main orchestrator
│   │   ├── pattern_loader.py        # Load patterns
│   │   ├── extractor.py             # Apply patterns
│   │   ├── validator.py             # Validate extractions
│   │   └── storage.py               # Store prices
│   ├── config/
│   │   ├── settings.yaml
│   │   └── cron.yaml
│   ├── scripts/
│   │   ├── run_fetch.py
│   │   └── setup_cron.sh
│   ├── tests/
│   └── requirements.txt
│
├── shared/                          # Shared utilities
│   ├── models/                      # Shared data models
│   │   ├── product.py
│   │   └── pattern.py
│   └── utils/
│       └── db_utils.py
│
└── infrastructure/
    ├── docker/
    │   ├── Dockerfile.web
    │   ├── Dockerfile.agent
    │   └── Dockerfile.fetcher
    └── monitoring/
        └── prometheus.yml
```

## Key Design Decisions

### 1. Why Separate Agent and Fetcher?

**Pattern Generation (AI Agent)**
- Complex reasoning required
- Needs to adapt to different site structures
- Run infrequently (once per domain or on pattern failure)
- Worth the AI cost for reliability

**Price Fetching (Deterministic)**
- Simple pattern application
- No reasoning needed
- Runs very frequently (every 15 minutes)
- Zero cost at scale

### 2. Why SQLite for Storage?

**Development/MVP**
- Simple setup
- Single file storage
- No separate database server
- Good enough for 1000s of products

**Production Migration Path**
- patterns.db → PostgreSQL (rarely changes)
- prices.db → PostgreSQL + TimescaleDB (time-series optimization)
- fetch_logs → Loki (log aggregation)

### 3. Pattern Fallback Strategy

Patterns include multiple extraction methods:
1. **JSON-LD** (highest confidence: 0.95)
   - Structured data in `<script type="application/ld+json">`
   - Most reliable, rarely changes

2. **Meta Tags** (confidence: 0.85)
   - `<meta property="og:price">`
   - Semantic, stable

3. **CSS Selectors** (confidence: 0.80)
   - Semantic classes: `.product-price`
   - Balances reliability and specificity

4. **XPath** (confidence: 0.70)
   - Last resort with text matching
   - More brittle but catches edge cases

### 4. When to Re-run ExtractorPatternAgent

Trigger pattern regeneration when:
- Initial product addition
- Pattern fails 3 consecutive times
- Confidence drops below 0.6
- Manual user request
- Scheduled validation (monthly)

## Scalability Considerations

### Current Design (MVP)
- Supports: 1,000-10,000 products
- Fetch frequency: 15 min - 6 hours
- Infrastructure: Single server
- Cost: ~$5-20/month (Anthropic API)

### Scale to 100K Products

**Horizontal Scaling**
```
┌─────────────────┐
│  Pattern Agent  │  (1 instance)
└─────────────────┘
        │
        ▼
┌─────────────────┐
│   patterns.db   │
└─────────────────┘
        │
        ▼
┌──────────────────────────────────┐
│    Load Balancer                 │
└──────────────────────────────────┘
        │
        ├─────────┬─────────┬──────────
        ▼         ▼         ▼
   ┌────────┐ ┌────────┐ ┌────────┐
   │Fetcher1│ │Fetcher2│ │Fetcher3│  (Scale horizontally)
   └────────┘ └────────┘ └────────┘
        │         │         │
        └─────────┴─────────┘
                  ▼
          ┌─────────────┐
          │ PostgreSQL  │
          │ (TimescaleDB)│
          └─────────────┘
```

**Rate Limiting per Domain**
- Amazon: 1 req/sec max
- Distribute across workers
- Use Redis for coordination

### Scale to 1M Products

- **Message Queue**: RabbitMQ/Redis for fetch jobs
- **Distributed Storage**: PostgreSQL cluster + Cassandra for time-series
- **CDN**: Cache product pages (if allowed)
- **Multi-region**: Deploy in multiple regions for geo-distributed products

## Monitoring & Observability

### Key Metrics

**Pattern Health**
- Success rate per domain
- Average confidence score
- Time since last pattern update
- Fallback method usage distribution

**Fetcher Performance**
- Fetch success rate (target: >95%)
- Average latency per domain
- Throughput (products/minute)
- Queue depth

**Data Quality**
- Price change frequency
- Suspicious changes (>50% price jump)
- Null/invalid extractions
- Confidence score distribution

### Alerts

1. **Pattern Failure**: Domain success rate <80% for 1 hour
2. **Fetcher Down**: No successful fetches for 30 minutes
3. **Price Anomaly**: Price changed by >50%
4. **Queue Backlog**: >1000 products waiting >1 hour

## Cost Breakdown (Estimated)

### ExtractorPatternAgent
- Pattern generation: $0.02 per product (one-time)
- Pattern updates: $0.02 per update (rare)
- 1,000 products: ~$20 initial, ~$5/month maintenance

### PriceFetcher
- HTTP requests: Free (or minimal if using proxy)
- Compute: $5-10/month (single server)
- Storage: <$1/month (SQLite/small PostgreSQL)

### Total: ~$30-40/month for 1,000 products

### Comparison to Full-AI Scraping
If we used AI for every fetch:
- 1,000 products × 4 fetches/day × 30 days = 120,000 AI calls
- At $0.01/call = $1,200/month
- **Our approach: 97% cost savings**

## Security & Privacy

### Rate Limiting
- Respect robots.txt
- Max 1-2 requests/second per domain
- Exponential backoff on errors
- Randomized delays

### User Agents
- Rotate realistic user agents
- Identify as price comparison tool
- Provide contact email in UA string

### Data Retention
- Keep price history: 90 days (configurable)
- Fetch logs: 30 days
- Archived data: S3/compressed

### No Sensitive Data
- Don't track user payment info
- Don't track browsing behavior
- Only public product data

## Development Roadmap

### Phase 1: MVP (Current)
- [x] ExtractorPatternAgent architecture
- [x] PriceFetcher architecture
- [x] WebUI architecture
- [ ] Implement WebUI (Django + HTMX)
- [ ] Implement ExtractorPatternAgent
- [ ] Implement PriceFetcher
- [ ] Basic tests
- [ ] Support 3-5 major stores

### Phase 2: User Features
- [ ] User authentication & registration
- [ ] Multi-user support
- [ ] User profiles & preferences
- [ ] Monitoring dashboard
- [ ] Alerting system
- [ ] Pattern auto-regeneration
- [ ] Support 20+ stores

### Phase 3: Scale
- [ ] Message queue for fetch jobs
- [ ] Horizontal scaling
- [ ] Multi-region deployment
- [ ] Advanced analytics
- [ ] Price prediction ML

## Future Enhancements

1. **Smart Scheduling**: ML model to predict optimal fetch times
2. **Browser Fingerprinting**: Advanced anti-detection for JS-heavy sites
3. **Price Prediction**: Forecast price trends
4. **Competitor Analysis**: Track same product across stores
5. **Browser Extension**: One-click product tracking
6. **Mobile App**: Push notifications for price drops
7. **API**: Public API for developers

## Testing Strategy

### Unit Tests
- Pattern extraction logic
- Data validation
- Storage operations

### Integration Tests
- Agent → Storage
- Fetcher → Storage
- End-to-end: URL → Pattern → Price

### Test Fixtures
```
tests/fixtures/
├── html/
│   ├── amazon_product.html
│   ├── ebay_product.html
│   └── walmart_product.html
├── patterns/
│   └── amazon_pattern.json
└── expected_outputs/
    └── amazon_extraction.json
```

### Performance Tests
- Fetch 100 products concurrently
- Pattern application speed
- Database write throughput

## Deployment

### Architecture Decision: Docker Compose

Development and production use Docker Compose for simplicity.

```yaml
# docker-compose.yml
services:
  db:
    # SQLite (file-based, no separate container needed)

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  web:
    build: ./WebUI
    ports:
      - "8000:8000"
    depends_on:
      - redis
    volumes:
      - ./db.sqlite3:/app/db.sqlite3

  celery:
    build: ./WebUI
    command: celery -A config worker -l info
    depends_on:
      - redis
    volumes:
      - ./db.sqlite3:/app/db.sqlite3

  celery-beat:
    build: ./WebUI
    command: celery -A config beat -l info
    depends_on:
      - redis
    volumes:
      - ./db.sqlite3:/app/db.sqlite3
```

**Why Docker Compose:**
- Simple orchestration
- Easy to run locally
- Good enough for small-scale production
- Can migrate to Kubernetes later if needed

## Documentation

Each component maintains its own `ARCHITECTURE.md`:
- **This file**: Overall system design
- **ExtractorPatternAgent/ARCHITECTURE.md**: Agent details
- **PriceFetcher/ARCHITECTURE.md**: Fetcher details
- **README.md**: Setup and usage instructions

## Contributing

When adding new features:
1. Update relevant ARCHITECTURE.md
2. Add tests
3. Update README.md
4. Document any new dependencies

## Architecture Decisions Summary

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Database** | SQLite | Simple, single-file, good for MVP (< 10K products) |
| **Task Queue** | Celery + Redis | Async tasks, built-in scheduling, scalable |
| **Authentication** | Postponed | Focus on core functionality first |
| **Scaling** | Not a concern | MVP focus, can scale later if needed |
| **Deployment** | Docker Compose | Simple, portable, good for dev and small production |
| **Monitoring** | Not implemented | Not needed for MVP |
| **Testing** | Not specified | Implement as needed during development |

## Implementation Order

For developers starting implementation:

1. **WebUI Django Models** - Database schema foundation
2. **Celery Setup** - Task queue infrastructure
3. **ExtractorPatternAgent** - Pattern generation with custom tools
4. **PriceFetcher** - Price extraction using patterns
5. **WebUI Views & Templates** - User interface with HTMX
6. **Admin Dashboard** - Review flagged patterns
7. **Docker Compose** - Containerize everything

See `DEPLOYMENT.md` for Docker Compose setup details.

---

**Last Updated**: 2025-12-14
**Status**: Architecture Complete
**Next**: Implementation Phase
