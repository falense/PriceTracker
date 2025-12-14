# WebUI Implementation Status & Agent Starting Point

## Current State: 70% Complete

### ✅ What's Working

1. **Database Models** (app/models.py:1-333)
   - All 7 core models implemented and tested
   - Product, PriceHistory, Pattern, Notification, FetchLog, UserView, AdminFlag
   - Proper relationships, indexes, and constraints
   - Django migrations created (migrations/0001_initial.py)

2. **Django Admin** (app/admin.py:1-141)
   - Full admin interface for all models
   - Custom admin actions and filters
   - Good for debugging and manual operations

3. **URL Routing** (app/urls.py:1-58)
   - URL patterns defined
   - View names mapped correctly

4. **View Functions Skeleton** (app/views.py:1-384)
   - View functions exist with proper signatures
   - HTMX patterns in place
   - Missing: Service layer integration

5. **Celery Configuration** (config/celery.py:1-45)
   - Celery app configured
   - Beat schedule defined
   - Redis connection configured

### 🔴 Critical Missing Pieces

1. **Celery Tasks Implementation** (BLOCKING ISSUE)
   - File `app/tasks.py` doesn't exist
   - Views reference `tasks.generate_pattern` and `tasks.fetch_product_price` that don't exist
   - Service layer (app/services.py) would break if executed

2. **Templates Directory**
   - Need to verify templates/ has all required files:
     - base.html
     - dashboard.html
     - product/list.html, detail.html, add_form.html
     - product/partials/ (HTMX fragments)
     - components/ (navbar, alerts, etc.)

3. **Static Assets**
   - CSS/JS for HTMX interactions
   - Chart.js integration
   - Dark/light mode toggle

4. **Service Layer Integration**
   - ProductService.add_product() calls non-existent tasks
   - NotificationService needs testing

### ⚠️ Known Issues

1. **Authentication**: Views use `@login_required` but auth is postponed
   - Decision needed: Remove decorators for MVP or implement basic auth?

2. **Database Path**: Hardcoded assumptions about db.sqlite3 location
   - Should use environment variable `DATABASE_PATH`

3. **Error Handling**: No error handling in views for failed async tasks

## Priority Tasks for Implementation Agent

### P0 - Blocking (Must Complete First)

#### Task 1: Create Celery Tasks (app/tasks.py)

**Location**: `WebUI/app/tasks.py`

**Required Tasks**:

```python
from celery import shared_task
import subprocess
import json
from pathlib import Path
from django.conf import settings
from .models import Pattern, Product

@shared_task(bind=True, max_retries=3)
def generate_pattern(self, url: str, domain: str):
    """
    Generate extraction pattern using ExtractorPatternAgent.

    Args:
        url: Product URL to analyze
        domain: Domain name (e.g., 'amazon.com')

    Returns:
        dict: Pattern data or error info
    """
    try:
        # Path to ExtractorPatternAgent CLI
        extractor_cli = Path(settings.BASE_DIR).parent / "ExtractorPatternAgent" / "extractor-cli.py"

        # Run pattern generation
        result = subprocess.run(
            ["uv", "run", str(extractor_cli), "generate", url, "--domain", domain],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        if result.returncode != 0:
            raise Exception(f"Pattern generation failed: {result.stderr}")

        # Parse output (assuming JSON output)
        pattern_data = json.loads(result.stdout)

        # Save to database using Django ORM
        pattern, created = Pattern.objects.update_or_create(
            domain=domain,
            defaults={
                'pattern_json': pattern_data,
                'last_validated': timezone.now()
            }
        )

        return {
            'success': True,
            'domain': domain,
            'pattern_id': pattern.id,
            'created': created
        }

    except Exception as e:
        # Retry with exponential backoff
        self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=3)
def fetch_product_price(self, product_id: str):
    """
    Fetch current price for a product using PriceFetcher.

    Args:
        product_id: UUID of product to fetch

    Returns:
        dict: Fetch result with price data
    """
    try:
        from .models import Product, PriceHistory

        # Get product
        product = Product.objects.get(id=product_id)

        # Path to PriceFetcher
        fetcher_script = Path(settings.BASE_DIR).parent / "PriceFetcher" / "scripts" / "run_fetch.py"

        # Run fetch for single product
        result = subprocess.run(
            [
                "python", str(fetcher_script),
                "--product-id", product_id,
                "--db-path", str(settings.DATABASES['default']['NAME'])
            ],
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode != 0:
            raise Exception(f"Price fetch failed: {result.stderr}")

        # Parse result
        fetch_data = json.loads(result.stdout)

        # Update product
        product.current_price = fetch_data.get('price')
        product.available = fetch_data.get('available', True)
        product.last_checked = timezone.now()
        product.save()

        return {
            'success': True,
            'product_id': product_id,
            'price': str(product.current_price),
            'available': product.available
        }

    except Product.DoesNotExist:
        return {'success': False, 'error': f'Product {product_id} not found'}
    except Exception as e:
        self.retry(exc=e, countdown=30 * (2 ** self.request.retries))


@shared_task
def fetch_prices(priority: str = 'all'):
    """
    Periodic task to fetch prices for all due products.
    Called by Celery Beat every 15 min / 1 hour / 6 hours.

    Args:
        priority: 'high', 'normal', 'low', or 'all'
    """
    from django.utils import timezone
    from .models import Product

    # Get products due for checking
    now = timezone.now()
    products = Product.objects.filter(active=True)

    if priority != 'all':
        products = products.filter(priority=priority)

    # Filter by check interval
    due_products = [
        p for p in products
        if p.is_due_for_check
    ]

    # Dispatch individual fetch tasks
    results = []
    for product in due_products:
        task = fetch_product_price.delay(str(product.id))
        results.append({
            'product_id': str(product.id),
            'task_id': task.id
        })

    return {
        'scheduled': len(results),
        'priority': priority,
        'tasks': results
    }


@shared_task
def check_pattern_health():
    """
    Daily task to check pattern health and trigger regeneration if needed.
    Called by Celery Beat at 2 AM daily.
    """
    from .models import Pattern, AdminFlag

    patterns = Pattern.objects.all()
    issues = []

    for pattern in patterns:
        if not pattern.is_healthy:
            # Create admin flag
            AdminFlag.objects.create(
                flag_type='pattern_low_confidence',
                domain=pattern.domain,
                url=f"https://{pattern.domain}",
                error_message=f"Success rate: {pattern.success_rate:.1%}, Total attempts: {pattern.total_attempts}",
                status='pending'
            )
            issues.append(pattern.domain)

    return {
        'checked': patterns.count(),
        'issues_found': len(issues),
        'flagged_domains': issues
    }
```

**Testing Checklist**:
- [ ] Import works: `from app.tasks import generate_pattern`
- [ ] Task appears in Celery: `celery -A config inspect registered`
- [ ] Can call: `generate_pattern.delay("https://example.com/product", "example.com")`
- [ ] Task executes without errors
- [ ] Pattern saved to database
- [ ] Task retries on failure

#### Task 2: Fix Service Layer (app/services.py)

**Current Issue**: File might not exist or imports are broken

**Required**: Create or fix `app/services.py` with proper task imports:

```python
from .models import Product, Pattern, Notification
from .tasks import generate_pattern, fetch_product_price
from django.utils import timezone
from urllib.parse import urlparse
import uuid


class ProductService:
    """Business logic for product management."""

    @staticmethod
    def add_product(user, url: str, priority: str = 'normal', target_price=None) -> Product:
        """
        Add new product and trigger pattern generation if needed.

        Returns:
            Product: Created or existing product
        """
        # Parse domain
        domain = urlparse(url).netloc.replace('www.', '')

        # Check if product already exists
        existing = Product.objects.filter(url=url).first()
        if existing:
            if existing.user == user:
                # Reactivate if was deactivated
                if not existing.active:
                    existing.active = True
                    existing.save()
                return existing
            else:
                # Clone for this user
                return ProductService._clone_product(existing, user)

        # Create new product
        product = Product.objects.create(
            id=uuid.uuid4(),
            user=user,
            url=url,
            domain=domain,
            name=f"Product from {domain}",  # Temporary, updated after first fetch
            priority=priority,
            target_price=target_price,
        )

        # Check if pattern exists for domain
        pattern = Pattern.objects.filter(domain=domain).first()
        if not pattern:
            # Trigger pattern generation (async)
            task = generate_pattern.delay(url, domain)
            print(f"Pattern generation task started: {task.id}")

        # Trigger immediate fetch (async)
        task = fetch_product_price.delay(str(product.id))
        print(f"Price fetch task started: {task.id}")

        return product

    @staticmethod
    def _clone_product(source: Product, new_user) -> Product:
        """Clone product for different user."""
        return Product.objects.create(
            id=uuid.uuid4(),
            user=new_user,
            url=source.url,
            domain=source.domain,
            name=source.name,
            priority='normal',
            pattern_version=source.pattern_version,
        )


class NotificationService:
    """Create and manage notifications."""

    @staticmethod
    def create_price_drop_notification(product: Product, old_price, new_price):
        """Create price drop notification."""
        if not product.notify_on_drop:
            return None

        if new_price >= old_price:
            return None  # Not a drop

        message = f"{product.name} dropped from ${old_price} to ${new_price}"

        return Notification.objects.create(
            user=product.user,
            product=product,
            notification_type='price_drop',
            message=message,
            old_price=old_price,
            new_price=new_price,
        )

    @staticmethod
    def create_target_reached_notification(product: Product):
        """Notify when target price is reached."""
        if not product.target_price:
            return None

        if not product.current_price:
            return None

        if product.current_price <= product.target_price:
            message = f"{product.name} reached your target price of ${product.target_price}!"

            return Notification.objects.create(
                user=product.user,
                product=product,
                notification_type='target_reached',
                message=message,
                new_price=product.current_price,
            )

        return None
```

#### Task 3: Create Dockerfile

**Location**: `WebUI/Dockerfile`

```dockerfile
FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy application code
COPY . .

# Collect static files (will be overridden by volume in dev)
RUN python manage.py collectstatic --noinput || true

# Run migrations on startup (for development)
# In production, run as separate init container
CMD ["sh", "-c", "python manage.py migrate && gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 4"]
```

### P1 - High Priority

#### Task 4: Verify Templates Exist

**Action**: Check if these files exist and are functional:

```bash
# Required template files
templates/
├── base.html                     # Base layout with HTMX
├── dashboard.html                # Main page
├── product/
│   ├── list.html                # Product list view
│   ├── detail.html              # Product detail with chart
│   ├── add_form.html            # Add product form
│   └── partials/
│       ├── product_card.html    # HTMX partial
│       ├── product_list.html    # HTMX partial
│       ├── chart.html           # Chart.js integration
│       └── settings_form.html   # Settings partial
├── notifications.html           # Notifications page
├── admin/
│   └── patterns.html            # Pattern health dashboard
└── components/
    ├── navbar.html              # Navigation
    └── alert.html               # Alert component
```

**If Missing**: Create minimal templates starting with base.html:

```html
<!-- templates/base.html -->
<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}PriceTracker{% endblock %}</title>

    <!-- HTMX -->
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>

    <!-- Tailwind CSS -->
    <script src="https://cdn.tailwindcss.com"></script>

    <!-- Chart.js -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

    {% block extra_head %}{% endblock %}
</head>
<body class="bg-gray-50 dark:bg-gray-900">
    <!-- Navigation -->
    {% include 'components/navbar.html' %}

    <!-- Main Content -->
    <main class="container mx-auto px-4 py-8">
        {% block content %}{% endblock %}
    </main>

    <!-- Theme Toggle Script -->
    <script>
        // Load theme from localStorage
        const theme = localStorage.getItem('theme') || 'light';
        document.documentElement.setAttribute('data-theme', theme);

        // Toggle function
        function toggleTheme() {
            const current = document.documentElement.getAttribute('data-theme');
            const next = current === 'light' ? 'dark' : 'light';
            document.documentElement.setAttribute('data-theme', next);
            localStorage.setItem('theme', next);
        }
    </script>

    {% block extra_scripts %}{% endblock %}
</body>
</html>
```

#### Task 5: Add Environment Configuration

**Location**: `WebUI/.env.example`

```bash
# Django
DEBUG=true
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DATABASE_PATH=/app/db.sqlite3

# Redis (Celery)
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# External Components
EXTRACTOR_PATH=/extractor
FETCHER_PATH=/fetcher

# Logging
LOG_LEVEL=INFO
```

Update `config/settings.py` to use environment variables:

```python
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Environment variables
DEBUG = os.getenv('DEBUG', 'false').lower() == 'true'
SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost').split(',')

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.getenv('DATABASE_PATH', BASE_DIR.parent / 'db.sqlite3'),
    }
}

# Celery
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
```

### P2 - Medium Priority

#### Task 6: Add Health Check Endpoint

**Location**: Add to `app/views.py`

```python
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

@require_http_methods(["GET"])
def health_check(request):
    """Health check endpoint for monitoring."""
    from django.db import connection
    from django_celery_results.models import TaskResult

    checks = {
        'status': 'healthy',
        'database': False,
        'celery': False,
    }

    # Check database
    try:
        connection.ensure_connection()
        checks['database'] = True
    except Exception as e:
        checks['status'] = 'unhealthy'
        checks['database_error'] = str(e)

    # Check Celery (if redis is reachable and recent tasks exist)
    try:
        recent_tasks = TaskResult.objects.count()
        checks['celery'] = True
        checks['recent_tasks'] = recent_tasks
    except Exception:
        checks['celery'] = False

    status_code = 200 if checks['status'] == 'healthy' else 503
    return JsonResponse(checks, status=status_code)
```

Add to `app/urls.py`:
```python
urlpatterns = [
    path('health/', views.health_check, name='health_check'),
    # ... existing patterns
]
```

#### Task 7: Integration Test Script

**Location**: `WebUI/test_integration.py`

```python
#!/usr/bin/env python
"""
Integration test: Add product → Generate pattern → Fetch price
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User
from app.models import Product, Pattern, PriceHistory
from app.services import ProductService

def test_end_to_end():
    print("=== Integration Test: End-to-End Flow ===\n")

    # 1. Create test user
    print("1. Creating test user...")
    user, created = User.objects.get_or_create(
        username='testuser',
        defaults={'email': 'test@example.com'}
    )
    print(f"   User: {user.username} (created: {created})")

    # 2. Add product
    print("\n2. Adding product...")
    test_url = "https://www.example.com/product/test-item"
    product = ProductService.add_product(
        user=user,
        url=test_url,
        priority='high',
        target_price=29.99
    )
    print(f"   Product ID: {product.id}")
    print(f"   Domain: {product.domain}")

    # 3. Check if pattern generation was triggered
    print("\n3. Checking pattern status...")
    pattern = Pattern.objects.filter(domain=product.domain).first()
    if pattern:
        print(f"   ✓ Pattern exists for {product.domain}")
        print(f"   Success rate: {pattern.success_rate:.1%}")
    else:
        print(f"   ⚠ Pattern not found (check Celery task)")

    # 4. Check if price was fetched
    print("\n4. Checking price history...")
    price_history = PriceHistory.objects.filter(product=product)
    if price_history.exists():
        latest = price_history.first()
        print(f"   ✓ Price found: ${latest.price}")
        print(f"   Confidence: {latest.confidence}")
    else:
        print(f"   ⚠ No price history (check Celery task)")

    print("\n=== Test Complete ===")

if __name__ == '__main__':
    test_end_to_end()
```

## Testing Checklist

### Unit Tests
- [ ] Models: Test all model methods and properties
- [ ] Services: Test ProductService and NotificationService
- [ ] Tasks: Test Celery tasks with mocked subprocess calls

### Integration Tests
- [ ] Add product flow (with mocked external calls)
- [ ] Price fetch updates product correctly
- [ ] Notifications created on price changes
- [ ] Pattern health check works

### Manual Tests
- [ ] Django admin works for all models
- [ ] Can add product via web UI
- [ ] Celery tasks visible in Flower
- [ ] Health check endpoint responds

## Common Issues & Solutions

### Issue 1: Celery tasks not found
```bash
# Symptom: ImportError: cannot import name 'generate_pattern'
# Solution: Ensure tasks.py exists and is imported in __init__.py

# app/__init__.py
from .celery import app as celery_app
__all__ = ('celery_app',)
```

### Issue 2: Database path incorrect in Docker
```bash
# Symptom: django.db.utils.OperationalError: unable to open database file
# Solution: Check volume mount and DATABASE_PATH env var

# In docker-compose.yml
volumes:
  - ./db.sqlite3:/app/db.sqlite3  # Ensure this path exists
```

### Issue 3: Celery worker not processing tasks
```bash
# Debug commands:
celery -A config inspect active       # See running tasks
celery -A config inspect registered   # See available tasks
celery -A config inspect stats        # Worker stats

# Check Celery logs
docker-compose logs -f celery
```

## Next Agent Handoff

Once you complete P0 and P1 tasks:
1. Document any deviations from this plan
2. Update `IMPLEMENTATION_STATUS.md` with current state
3. Create test results summary
4. Note any new issues discovered
5. Recommend next priority tasks

## References

- Main architecture: `../ARCHITECTURE.md`
- Django models: `app/models.py`
- Celery config: `config/celery.py`
- Deployment: `../DEPLOYMENT.md`
