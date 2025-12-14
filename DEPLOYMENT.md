# Deployment Guide

## Architecture Decisions

- **Database**: SQLite (shared db.sqlite3 file)
- **Task Queue**: Celery + Redis
- **Authentication**: Postponed (single user for now)
- **Orchestration**: Docker Compose
- **Scaling**: Not a concern for MVP

## System Components

```
┌─────────────────────────────────────────────┐
│         Docker Compose Stack                │
│                                             │
│  ┌─────────┐                                │
│  │ Redis   │ ← Message broker               │
│  └────┬────┘                                │
│       │                                     │
│  ┌────┴─────────────────────────────┐      │
│  │                                   │      │
│  ▼                  ▼                ▼      │
│ ┌────┐         ┌────────┐      ┌────────┐  │
│ │Web │         │Celery  │      │Celery  │  │
│ │8000│         │Worker  │      │Beat    │  │
│ └─┬──┘         └───┬────┘      └───┬────┘  │
│   │                │               │        │
│   └────────────────┴───────────────┘        │
│                    │                        │
│              ┌─────▼──────┐                 │
│              │ db.sqlite3 │                 │
│              └────────────┘                 │
└─────────────────────────────────────────────┘
```

## Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- 2GB RAM minimum
- 10GB disk space

## Quick Start

```bash
# Clone repository
git clone <repo-url>
cd PriceTracker

# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f web
docker-compose logs -f celery

# Access application
# Web UI: http://localhost:8000
# Flower (Celery monitoring): http://localhost:5555
```

## Initial Setup

```bash
# Run Django migrations
docker-compose exec web python manage.py migrate

# Create admin user (for admin dashboard)
docker-compose exec web python manage.py createsuperuser

# Collect static files
docker-compose exec web python manage.py collectstatic --noinput

# Test Celery is working
docker-compose exec celery celery -A config inspect ping
```

## Component Details

### Web Service (Django)

- **Port**: 8000
- **Purpose**: Serves WebUI
- **Access**: http://localhost:8000
- **Logs**: `docker-compose logs web`

### Celery Worker

- **Purpose**: Executes async tasks
- **Tasks**:
  - `generate_pattern`: Trigger ExtractorPatternAgent
  - `fetch_product_price`: Trigger PriceFetcher
  - Background jobs
- **Concurrency**: 4 workers
- **Logs**: `docker-compose logs celery`

### Celery Beat

- **Purpose**: Periodic task scheduler
- **Schedule**:
  - Fetch prices every 15 min / 1 hour / 24 hours (based on product priority)
  - Check pattern health daily
  - Cleanup old logs weekly
- **Logs**: `docker-compose logs celery-beat`

### Redis

- **Port**: 6379
- **Purpose**: Message broker for Celery
- **Data**: Task queue, results cache

### Flower (Optional)

- **Port**: 5555
- **Purpose**: Monitor Celery tasks
- **Access**: http://localhost:5555
- **Features**:
  - Task history
  - Worker status
  - Task retry/revoke
  - Real-time monitoring

## Database

### SQLite Location

```
./db.sqlite3  (mounted into all containers)
```

### Backup

```bash
# Backup database
docker-compose exec web python manage.py dumpdata > backup.json

# Or copy SQLite file
cp db.sqlite3 backups/db-$(date +%Y%m%d).sqlite3
```

### Migrations

```bash
# Create new migration
docker-compose exec web python manage.py makemigrations

# Apply migrations
docker-compose exec web python manage.py migrate

# Show migration status
docker-compose exec web python manage.py showmigrations
```

## Celery Task Configuration

### Task Definitions

```python
# WebUI/config/celery.py
from celery import Celery
from celery.schedules import crontab

app = Celery('pricetracker')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Periodic tasks
app.conf.beat_schedule = {
    'fetch-high-priority-products': {
        'task': 'app.tasks.fetch_prices',
        'schedule': 900.0,  # Every 15 minutes
        'args': ('high',)
    },
    'fetch-normal-priority-products': {
        'task': 'app.tasks.fetch_prices',
        'schedule': 3600.0,  # Every hour
        'args': ('normal',)
    },
    'fetch-low-priority-products': {
        'task': 'app.tasks.fetch_prices',
        'schedule': 86400.0,  # Daily
        'args': ('low',)
    },
    'check-pattern-health': {
        'task': 'app.tasks.check_pattern_health',
        'schedule': crontab(hour=2, minute=0),  # 2 AM daily
    },
}
```

### Task Routing

```python
# All tasks go to default queue for now
# Can add priority queues later:
# - high_priority (15 min checks)
# - normal_priority (hourly checks)
# - low_priority (daily checks)
```

## Monitoring

### Health Checks

```bash
# Check if web is responding
curl http://localhost:8000/health

# Check Redis
docker-compose exec redis redis-cli ping

# Check Celery workers
docker-compose exec celery celery -A config inspect active
```

### View Task Status

```bash
# Via Flower
open http://localhost:5555

# Via command line
docker-compose exec celery celery -A config inspect active
docker-compose exec celery celery -A config inspect scheduled
```

### Resource Usage

```bash
# View container stats
docker stats

# Specific service
docker stats pricetracker-web-1
docker stats pricetracker-celery-1
```

## Common Operations

### Restart Services

```bash
# Restart all
docker-compose restart

# Restart specific service
docker-compose restart web
docker-compose restart celery
```

### Update Code

```bash
# Pull latest changes
git pull

# Rebuild containers
docker-compose build

# Restart services
docker-compose up -d
```

### Scale Workers

```bash
# Run 8 Celery workers instead of 1 container with 4
docker-compose up -d --scale celery=2
```

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f web
docker-compose logs -f celery

# Last 100 lines
docker-compose logs --tail=100 celery
```

### Clean Up

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (⚠️ deletes database)
docker-compose down -v

# Remove old images
docker system prune -a
```

## Troubleshooting

### Web Service Won't Start

```bash
# Check logs
docker-compose logs web

# Common issues:
# - Port 8000 already in use
# - Database locked
# - Missing migrations

# Solution: Run migrations
docker-compose exec web python manage.py migrate
```

### Celery Tasks Not Executing

```bash
# Check if workers are running
docker-compose exec celery celery -A config inspect active

# Check Redis connection
docker-compose exec redis redis-cli ping

# Check task queue
docker-compose exec celery celery -A config inspect reserved

# Purge queue (⚠️ clears all pending tasks)
docker-compose exec celery celery -A config purge
```

### Database Locked Error

```bash
# SQLite doesn't handle high concurrency well
# Reduce Celery workers:
docker-compose up -d --scale celery=1

# Or migrate to PostgreSQL later
```

### Pattern Generation Timeout

```bash
# Check Celery worker logs
docker-compose logs celery | grep "generate_pattern"

# Increase timeout in settings
# WebUI/config/settings.py
CELERY_TASK_TIME_LIMIT = 300  # 5 minutes
```

## Production Considerations

### Security

```bash
# Use environment file for secrets
# Create .env file:
echo "DJANGO_SECRET_KEY=$(python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')" > .env
echo "DEBUG=false" >> .env

# Update docker-compose.yml to use .env
```

### Performance

```bash
# Use production WSGI server (Gunicorn)
# Update web service command:
command: gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 4

# Enable Redis persistence
# Add to redis service:
command: redis-server --appendonly yes
volumes:
  - redis-data:/data
```

### Backups

```bash
# Automate SQLite backups
# Add to crontab or Celery beat:
0 2 * * * cp /path/to/db.sqlite3 /backups/db-$(date +\%Y\%m\%d).sqlite3
```

## Architecture Notes

### Why SQLite?

- **Simple**: Single file, no separate DB container
- **Fast**: For < 10K products, SQLite is sufficient
- **Portable**: Easy to backup and restore
- **Limitations**: Not ideal for > 100 concurrent writes

### Why Celery?

- **Async Tasks**: Pattern generation takes 30-60s
- **Scheduling**: Built-in periodic task support
- **Scalability**: Easy to add more workers
- **Retry Logic**: Automatic task retry on failure

### Why Docker Compose?

- **Simple**: One command to start everything
- **Portable**: Works on any OS with Docker
- **Reproducible**: Same environment for all developers
- **Migration Path**: Easy to move to Kubernetes later

## Future Improvements

When scaling beyond MVP:

1. **PostgreSQL**: Replace SQLite for better concurrency
2. **Nginx**: Add reverse proxy for SSL and load balancing
3. **Redis Cluster**: For high availability
4. **Kubernetes**: For auto-scaling and orchestration
5. **Monitoring**: Add Prometheus + Grafana
6. **CDN**: For static assets and product images

---

**Quick Reference**

```bash
# Start
docker-compose up -d

# Stop
docker-compose down

# Logs
docker-compose logs -f celery

# Shell
docker-compose exec web python manage.py shell

# Celery monitor
open http://localhost:5555
```
