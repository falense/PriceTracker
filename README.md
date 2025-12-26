# PriceTracker

**Intelligent price tracking system for e-commerce products**

Track product prices across multiple online stores, get alerts on price drops, and never miss a deal.

---

## 🚀 Features

- **Automatic Price Tracking**: Monitor product prices with configurable check intervals
- **AI-Powered Pattern Generation**: Automatically learns how to extract prices from any website
- **Smart Notifications**: Get alerts for price drops, target prices, and restocks
- **Priority Levels**: Normal and low priority tracking (1hr, 24hr intervals)
- **Multi-User Support**: Each user can track their own products
- **Price History**: View historical price data with charts
- **Django Admin**: Manage products, patterns, and view system health

## 📊 System Status

**Overall Completion**: 95% - Production Ready

| Component | Status | Description |
|-----------|--------|-------------|
| WebUI | ✅ 100% | Django app with HTMX, user management, dashboard |
| ExtractorPatternAgent | ✅ 95% | AI-powered web scraping pattern generator |
| PriceFetcher | ✅ 90% | Deterministic price fetching with retry logic |
| Infrastructure | ✅ 100% | Docker Compose with Celery, Redis, Flower |

## 🏗️ Architecture

```
┌─────────────────┐
│   User Browser  │
└────────┬────────┘
         │ HTTP/HTMX
         ↓
┌─────────────────────────────────────────────────┐
│  WebUI (Django + Celery)                        │
│  - Product Management                           │
│  - User Authentication                          │
│  - Notifications                                │
│                                                  │
│  Celery Tasks (tasks.py):                       │
│    ├─ generate_pattern()                        │
│    │   └─> PatternGenerator.generate()          │
│    │                                             │
│    ├─ fetch_listing_price()                     │
│    │   └─> fetch_listing_price_direct()         │
│    │                                             │
│    └─ fetch_missing_images()                    │
│        └─> backfill_images_direct()             │
└────────┬────────────────────┬───────────────────┘
         │                    │
         │ Direct Imports     │ Direct Imports
         ↓                    ↓
┌────────────────────┐  ┌─────────────────────┐
│ PatternGenerator   │  │ PriceFetcher API    │
│ (Python Class)     │  │ (celery_api.py)     │
│  - fetch_page()    │  │  - fetch_listing_   │
│  - analyze_html()  │  │    price_direct()   │
│  - generate()      │  │  - backfill_images_ │
└─────────┬──────────┘  │    direct()         │
          │             └──────────┬──────────┘
          └───────────┬────────────┘
                      ↓
              ┌───────────────┐
              │ SQLite / DB   │
              └───────────────┘
```

### Components

1. **WebUI**: Django web application with HTMX for dynamic UI
2. **PatternGenerator**: Python class that analyzes websites and generates extraction patterns using AI
3. **PriceFetcher API**: Async Python functions for fetching prices using generated patterns
4. **Celery**: Distributed task queue for background jobs (direct Python imports, no subprocesses)
5. **Redis**: Message broker and result backend
6. **Flower**: Real-time Celery monitoring

### Architecture Highlights

- **Direct Import Architecture**: Celery tasks import `PatternGenerator` and `PriceFetcher` APIs directly as Python modules
- **No Subprocess Overhead**: All components run within the same Python process for better performance
- **Async Support**: Both PatternGenerator and PriceFetcher support async/await for efficient I/O
- **Shared Database**: All components access a shared SQLite database for consistency

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Git

### Installation

```bash
# Clone repository
git clone <repository-url>
cd PriceTracker

# Start all services
docker compose up -d

# Run database migrations
docker compose exec web python manage.py migrate

# Create admin user
docker compose exec web python manage.py createsuperuser

# Access the application
open http://localhost:8000
```

### Services

- **WebUI**: http://localhost:8000
- **Django Admin**: http://localhost:8000/admin
- **Flower (Celery monitoring)**: http://localhost:5555

## 📖 Usage

### Adding Products

1. **Via Web UI**:
   - Navigate to http://localhost:8000
   - Paste product URL in search box
   - Set priority and target price
   - Click "Track Product"

2. **Via Django Admin**:
   - Navigate to http://localhost:8000/admin
   - Go to Products → Add Product
   - Fill in product details
   - Save

### Monitoring

- **Flower Dashboard**: View Celery task status, success rates, worker health
- **Django Admin**: View products, price history, patterns, notifications
- **Logs**: `docker compose logs -f celery`

## 🔧 Configuration

### Environment Variables

```bash
# Django
SECRET_KEY=your-secret-key
DEBUG=False
ALLOWED_HOSTS=localhost,yourdomain.com

# Database
DATABASE_PATH=/app/db.sqlite3

# Redis/Celery
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
```

### Priority System

The system uses aggregated priority scheduling. Celery Beat runs a single task every 5 minutes that checks all products and queues fetches based on the highest priority set by any subscriber.

Priority intervals:
- **Normal**: Check every hour (3600 seconds)
- **Low**: Check daily (86400 seconds)

## 🛠️ Development

### Project Structure

```
PriceTracker/
├── WebUI/              # Django web application
│   ├── app/            # Main Django app
│   ├── config/         # Django settings
│   └── templates/      # HTML templates
├── ExtractorPatternAgent/  # AI pattern generator
│   ├── src/            # Agent source code
│   └── scripts/        # CLI scripts
├── PriceFetcher/       # Price fetching worker
│   ├── src/            # Fetcher source code
│   └── scripts/        # CLI scripts
├── docker-compose.yml  # Service orchestration
└── README.md           # This file
```

### Running Tests

```bash
# WebUI tests
docker compose exec web python manage.py test

# Integration tests
docker compose exec celery python test_docker_integration.py

# All tests
docker compose exec web pytest
```

### Autonomous Extractor Generation

For creating new web scraping extractors, use the autonomous generator script:

```bash
# Generate a new extractor for any product URL
cd ExtractorPatternAgent
uv run generate_pattern.py https://www.komplett.no/product/1310167
```

**What it does**:
1. Fetches HTML sample using Playwright with stealth
2. Validates sample (detects CAPTCHA/blocking)
3. Analyzes HTML structure (JSON-LD, OpenGraph, CSS selectors)
4. Generates Python extractor module with 7 extraction functions
5. Tests extractor against the sample
6. Iterates on failures until tests pass
7. Commits the result to git

**Features**:
- Fully autonomous (no human intervention required)
- Fail-fast on site blocking (CAPTCHA, 403, etc.)
- Uses Claude Agent SDK for intelligent extraction
- Follows PATTERN_CREATION_GUIDE.md best practices
- Auto-commits successful extractors

**Requirements**:
- Claude Code CLI: `npm install -g @anthropic-ai/claude-code`
- Python 3.11+: Managed by uv

## 📚 Documentation

- **[IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md)**: Current implementation status and data model
- **[ADMIN_ACCESS.md](ADMIN_ACCESS.md)**: Admin user management guide
- **Component READMEs**:
  - [WebUI/README.md](WebUI/README.md)
  - [ExtractorPatternAgent/README.md](ExtractorPatternAgent/README.md)
  - [PriceFetcher/README.md](PriceFetcher/README.md)

## 🙏 Acknowledgments

- Built with Django, Celery, Playwright, and Claude AI
- Icons from Heroicons
- UI framework: Tailwind CSS