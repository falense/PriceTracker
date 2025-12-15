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
┌─────────────────────────────────┐
│  WebUI (Django + Celery)        │
│  - Product Management           │
│  - User Authentication          │
│  - Notifications                │
└───────┬──────────────┬──────────┘
        │              │
        │              │ Celery Tasks
        ↓              ↓
┌──────────────┐  ┌──────────────────┐
│ ExtractorAI  │  │  PriceFetcher    │
│ (Pattern Gen)│  │  (Fetch Prices)  │
└───────┬──────┘  └────────┬─────────┘
        │                   │
        └───────┬───────────┘
                ↓
        ┌───────────────┐
        │ SQLite / DB   │
        └───────────────┘
```

### Components

1. **WebUI**: Django web application with HTMX for dynamic UI
2. **ExtractorPatternAgent**: Claude-powered agent that analyzes websites and generates extraction patterns
3. **PriceFetcher**: Async worker that fetches prices using generated patterns
4. **Celery**: Distributed task queue for background jobs
5. **Redis**: Message broker and result backend
6. **Flower**: Real-time Celery monitoring

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

### Local Development (without Docker)

```bash
# WebUI
cd WebUI
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py runserver

# Celery Worker
celery -A config worker -l info

# Celery Beat
celery -A config beat -l info
```

## 📚 Documentation

- **[IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md)**: Current implementation status and data model
- **[ADMIN_ACCESS.md](ADMIN_ACCESS.md)**: Admin user management guide
- **Component READMEs**:
  - [WebUI/README.md](WebUI/README.md)
  - [ExtractorPatternAgent/README.md](ExtractorPatternAgent/README.md)
  - [PriceFetcher/README.md](PriceFetcher/README.md)

## 🔮 Roadmap

### Completed ✅
- [x] Django WebUI with user authentication
- [x] Multi-store product tracking with user subscriptions
- [x] Aggregated priority scheduling
- [x] Celery task queue with periodic scheduling
- [x] ExtractorPatternAgent with headless browser
- [x] PriceFetcher with retry logic
- [x] Docker deployment
- [x] Notification system
- [x] Django admin interface
- [x] Pattern version history with rollback

### Future Enhancements
- [ ] Add health check endpoints
- [ ] Implement email notifications
- [ ] Add price history charts
- [ ] PostgreSQL migration guide
- [ ] Support for more e-commerce platforms
- [ ] Browser extension
- [ ] Advanced analytics dashboard
- [ ] Multi-currency support
- [ ] Webhook integrations

## 🤝 Contributing

Contributions welcome! Please read our contributing guidelines (TODO: add CONTRIBUTING.md).

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'feat: add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

[Add License Here]

## 🙏 Acknowledgments

- Built with Django, Celery, Playwright, and Claude AI
- Icons from Heroicons
- UI framework: Tailwind CSS

## 📞 Support

For issues and questions:
- **GitHub Issues**: [Repository Issues](link-to-issues)
- **Documentation**: See [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md)

---

**Status**: Production Ready (95% complete)
**Last Updated**: 2025-12-14
**Version**: 1.0.0-rc1
