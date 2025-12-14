"""
Celery configuration for PriceTracker WebUI.
"""
import os
from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('pricetracker')

# Load config from Django settings with CELERY namespace
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in all installed apps
app.autodiscover_tasks()

# Celery Beat Schedule for periodic tasks
app.conf.beat_schedule = {
    'fetch-high-priority-products': {
        'task': 'app.tasks.fetch_prices_by_priority',
        'schedule': 900.0,  # Every 15 minutes
        'args': ('high',)
    },
    'fetch-normal-priority-products': {
        'task': 'app.tasks.fetch_prices_by_priority',
        'schedule': 3600.0,  # Every hour
        'args': ('normal',)
    },
    'fetch-low-priority-products': {
        'task': 'app.tasks.fetch_prices_by_priority',
        'schedule': 86400.0,  # Every 24 hours
        'args': ('low',)
    },
    'check-pattern-health': {
        'task': 'app.tasks.check_pattern_health',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
    },
    'cleanup-old-logs': {
        'task': 'app.tasks.cleanup_old_logs',
        'schedule': crontab(day_of_week=0, hour=3, minute=0),  # Weekly on Sunday at 3 AM
    },
}

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
