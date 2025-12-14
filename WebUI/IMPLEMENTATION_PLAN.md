# WebUI Implementation Plan

## Executive Summary

This document outlines a comprehensive, phased implementation plan for the WebUI component of the PriceTracker system. The WebUI is a Django + HTMX web application that provides users with a search-first interface for tracking product prices across e-commerce websites.

**Current Status**: Architecture complete, implementation pending
- ✅ Comprehensive documentation (ARCHITECTURE.md, UI_DESIGN_FINAL.md)
- ✅ Celery tasks implemented (tasks.py)
- ✅ Docker orchestration configured
- ✅ ExtractorPatternAgent fully implemented
- ⚠️ PriceFetcher architecture documented, code not implemented
- ❌ Django application not implemented (models, views, templates)

**Recommended Approach**: Incremental implementation with integrated price fetching service
- Phase 1: Core Django infrastructure and database models
- Phase 2: Pattern generation integration with ExtractorPatternAgent
- Phase 3: Price fetching service (integrated within WebUI initially)
- Phase 4: Basic views and templates (server-side rendering)
- Phase 5: HTMX interactivity and real-time updates
- Phase 6: Notifications and admin features
- Phase 7: Testing, optimization, and deployment

**Estimated Scope**: 7 phases, iterative development, MVP in phases 1-4

---

## 1. Current State Analysis

### What Exists

**Documentation** (Complete):
- `/WebUI/ARCHITECTURE.md` - 933 lines, comprehensive technical architecture
- `/WebUI/UI_DESIGN_FINAL.md` - Complete UI/UX specifications
- `/WebUI/UI_DESIGN_v2.md` - Search-first design approach
- `/WebUI/UI_DESIGN.md` - Initial dashboard-centric design

**Code** (Partial):
- `/WebUI/tasks.py` - 212 lines, Celery tasks for async operations
  - `generate_pattern()` - Triggers ExtractorPatternAgent
  - `fetch_product_price()` - Triggers PriceFetcher
  - `fetch_prices_by_priority()` - Periodic price checks
  - `check_pattern_health()` - Pattern monitoring
  - `cleanup_old_logs()` - Maintenance tasks

**Infrastructure**:
- `/docker-compose.yml` (project root) - Complete orchestration for:
  - Redis (message broker)
  - Web (Django on port 8000)
  - Celery worker
  - Celery beat (scheduler)
  - Flower (monitoring on port 5555)

**Dependencies**:
- ExtractorPatternAgent: ✅ Fully implemented (475 lines)
- PriceFetcher: ❌ Not implemented (architecture only)

### What's Missing

**Critical (MVP Blockers)**:
1. Django project structure (`config/`, `manage.py`)
2. Django app implementation (`app/`)
3. Database models (Product, PriceHistory, Pattern, etc.)
4. Views and URL routing
5. HTML templates
6. Static assets (CSS, JavaScript)
7. Price fetching logic (PriceFetcher component)
8. Database migrations

**Important (Post-MVP)**:
1. User authentication and authorization
2. Comprehensive test suite
3. Admin interface customization
4. Frontend optimization (CSS, JS minification)
5. Production deployment configuration
6. Monitoring and logging setup

---

## 2. Implementation Approach Analysis

### Option A: Full Architecture Implementation

**Approach**: Implement all components as documented
- Build WebUI Django app
- Build PriceFetcher as separate component
- Integrate both via Celery and shared database

**Pros**:
- Follows documented architecture perfectly
- Clear separation of concerns
- Components can scale independently
- Matches long-term vision

**Cons**:
- Larger initial scope (need to implement PriceFetcher)
- More complex inter-component communication
- Longer time to working MVP
- More moving parts to test and debug

**Estimated Effort**: High (7-10 implementation phases)

---

### Option B: WebUI-First with Integrated Price Fetching ⭐ RECOMMENDED

**Approach**: Implement WebUI with price fetching as internal service
- Build WebUI Django app
- Implement price fetching logic directly in WebUI services
- Use ExtractorPatternAgent for pattern generation (fully implemented)
- Later extract price fetching to separate component if needed

**Pros**:
- ✅ Faster path to working MVP
- ✅ Simpler deployment and debugging
- ✅ All logic in one codebase initially
- ✅ Can refactor to separate component later (patterns already stored in DB)
- ✅ Less complex inter-component communication
- ✅ Easier to iterate on features

**Cons**:
- ❌ Deviates slightly from documented architecture
- ❌ May need refactoring if scaling requires separate fetcher
- ❌ Monolithic initially (can be addressed later)

**Estimated Effort**: Medium (7 phases, faster iterations)

**Migration Path**:
1. Start with integrated service
2. Extract to separate component when scaling needs arise
3. Patterns already in shared database, minimal code changes needed

---

### Option C: Minimal Prototype First

**Approach**: Build bare minimum to demonstrate concept
- Basic Django app with hardcoded patterns
- No pattern generation initially
- Manual product addition only
- Single-user, no auth

**Pros**:
- Fastest to initial working state
- Good for proof-of-concept
- Easy to demonstrate core functionality

**Cons**:
- ⚠️ Requires significant rework for production
- ⚠️ Doesn't leverage existing ExtractorPatternAgent
- ⚠️ Not a viable MVP
- ⚠️ Technical debt from day one

**Estimated Effort**: Low (3-4 phases), High rework later

---

### Recommendation: Option B (Integrated Price Fetching)

**Rationale**:
1. **Faster MVP**: Get to working product quickly without implementing entire PriceFetcher component
2. **Pragmatic**: Leverages fully-implemented ExtractorPatternAgent, defers complex PriceFetcher
3. **Flexible**: Can refactor to separate component later when needed
4. **Lower Risk**: Fewer moving parts means easier debugging and testing
5. **Iterative**: Can ship features incrementally and gather feedback

**Trade-off Acceptance**:
- Slight deviation from documented architecture is acceptable for MVP
- Price fetching logic will initially live in `app/services/price_fetcher_service.py`
- Database schema remains the same (enables future separation)
- Can extract to separate component if scaling requires it

---

## 3. Detailed Implementation Plan

### Phase 1: Core Django Infrastructure & Database Models

**Goal**: Set up Django project with complete data models and migrations

**Tasks**:

1.1. **Create Django Project Structure**
```bash
cd WebUI/
django-admin startproject config .
python manage.py startapp app
```

**Files to create**:
- `manage.py` - Django management script
- `config/__init__.py` - Package marker
- `config/settings.py` - Django settings
- `config/urls.py` - Root URL configuration
- `config/wsgi.py` - WSGI application
- `config/celery.py` - Celery configuration
- `app/__init__.py` - App package marker

1.2. **Configure Django Settings** (`config/settings.py`)
- Database: SQLite3 at `/app/db.sqlite3` (shared with other components)
- Installed apps: `django.contrib.auth`, `app`, `django_htmx`
- Middleware: Standard Django + CSRF protection
- Templates: Configure template directories
- Static files: Configure static file serving
- Celery: Redis broker URL from environment

1.3. **Implement Database Models** (`app/models.py`)

Models to implement (from ARCHITECTURE.md):
- `Product` - Core product tracking model
  - Fields: id (UUID), user (FK), url, domain, name, current_price, currency, etc.
  - Priority choices: high (15min), normal (1h), low (24h)
  - Properties: `price_change_24h`, `lowest_price`, `highest_price`
  - Method: `record_view()`

- `PriceHistory` - Historical price records
  - Fields: product (FK), price, currency, available, extracted_data (JSON), confidence
  - Ordering: newest first

- `Pattern` - Extraction patterns per domain
  - Fields: domain (unique), pattern_json (JSON), success_rate, total_attempts
  - Method: `record_attempt(success: bool)`

- `Notification` - User notifications
  - Fields: user (FK), product (FK), notification_type, message, old/new prices
  - Types: price_drop, target_reached, restock, price_spike
  - Method: `mark_as_read()`

- `FetchLog` - Debugging logs for fetch attempts
  - Fields: product (FK), success, extraction_method, errors (JSON), duration_ms

- `UserView` - Analytics tracking
  - Fields: user (FK), product (FK), viewed_at, duration_seconds

- `AdminFlag` - Admin attention flags
  - Fields: flag_type, domain, url, error_message, status
  - Types: pattern_generation_failed, pattern_low_confidence, fetch_failing_repeatedly
  - Status: pending, in_progress, resolved, wont_fix

1.4. **Create and Run Migrations**
```bash
python manage.py makemigrations
python manage.py migrate
```

1.5. **Create Superuser for Admin**
```bash
python manage.py createsuperuser
```

1.6. **Configure Celery** (`config/celery.py`)
- Initialize Celery app with Redis broker
- Configure task routes and schedules
- Set up beat schedule for periodic tasks

**Acceptance Criteria**:
- ✅ Django project structure created
- ✅ All 7 models implemented with correct fields
- ✅ Database migrations created and applied
- ✅ Admin can create superuser
- ✅ Celery configuration complete
- ✅ `python manage.py check` passes with no errors

**Estimated Effort**: 1-2 days

---

### Phase 2: Pattern Generation Integration

**Goal**: Integrate with ExtractorPatternAgent for automatic pattern generation

**Tasks**:

2.1. **Create Pattern Service** (`app/services/pattern_service.py`)

```python
class PatternService:
    """
    Service for managing extraction patterns.
    Integrates with ExtractorPatternAgent.
    """

    def get_or_generate_pattern(self, domain: str, sample_url: str) -> Pattern:
        """Get existing pattern or generate new one."""
        # Check database for existing pattern
        # If not found, trigger generation via Celery
        # Return pattern or raise exception

    def validate_pattern(self, pattern: Pattern, url: str) -> dict:
        """Validate pattern still works."""
        # Call ExtractorPatternAgent validation

    def regenerate_pattern(self, domain: str, url: str) -> Pattern:
        """Force regeneration of pattern."""
        # Trigger ExtractorPatternAgent
```

2.2. **Update Celery Tasks** (`tasks.py`)

Modify `generate_pattern` task to:
- Use ExtractorPatternAgent CLI interface
- Parse JSON output and save to Pattern model
- Handle errors and create AdminFlag on failure
- Return pattern ID on success

**Integration Options**:

**Option 2.2A: CLI Subprocess** (Simplest)
```python
result = subprocess.run([
    'uv', 'run',
    '/extractor/extractor-cli.py',
    'generate', url,
    '--output', '/tmp/pattern.json',
    '--no-save'  # Don't save to agent's DB
], timeout=120, capture_output=True)
```

**Option 2.2B: Direct Python API** (More efficient) ⭐ RECOMMENDED
```python
import sys
sys.path.insert(0, '/extractor')
from src.agent import ExtractorPatternAgent

async with ExtractorPatternAgent() as agent:
    patterns = await agent.generate_patterns(url, save_to_db=False)
    # Save to WebUI database
```

2.3. **Create Management Command for Pattern Testing**
```bash
python manage.py generate_pattern amazon.com https://amazon.com/dp/B0X123
```

2.4. **Add Admin Interface for Patterns**
- Register Pattern model in `app/admin.py`
- Custom admin actions: validate, regenerate, export
- Display success rate and last validated date

**Acceptance Criteria**:
- ✅ PatternService implemented with all methods
- ✅ generate_pattern task successfully calls ExtractorPatternAgent
- ✅ Patterns saved to database with correct structure
- ✅ Failed generation creates AdminFlag
- ✅ Management command works for testing
- ✅ Admin interface shows patterns with stats

**Estimated Effort**: 2-3 days

---

### Phase 3: Price Fetching Service (Integrated)

**Goal**: Implement price fetching logic within WebUI services

**Tasks**:

3.1. **Create Price Fetcher Service** (`app/services/price_fetcher_service.py`)

```python
class PriceFetcherService:
    """
    Price fetching service using stored patterns.
    Applies patterns to fetch and extract product data.
    """

    async def fetch_product_price(self, product: Product) -> dict:
        """Fetch current price for a product."""
        # 1. Load pattern from database
        # 2. Fetch HTML using httpx
        # 3. Apply pattern (CSS, XPath, JSON-LD)
        # 4. Validate extraction
        # 5. Return extracted data

    async def apply_pattern(self, html: str, pattern: dict) -> dict:
        """Apply extraction pattern to HTML."""
        # Try primary selector
        # Try fallback selectors
        # Return extracted data with confidence

    def validate_extraction(self, data: dict, product: Product) -> dict:
        """Validate extracted data quality."""
        # Check price is numeric and positive
        # Check price change is reasonable (< 50%)
        # Return validation result
```

3.2. **Implement Pattern Application Logic**

Create extractors for each pattern type:
- `JSONLDExtractor` - Extract from structured data
- `MetaTagExtractor` - Extract from Open Graph tags
- `CSSSelectorExtractor` - Apply CSS selectors with BeautifulSoup
- `XPathExtractor` - Apply XPath expressions with lxml

3.3. **Update Celery Task** (`tasks.py`)

Modify `fetch_product_price` task to:
- Load product from database
- Call PriceFetcherService
- Save price to PriceHistory
- Update product current_price
- Create notifications if needed
- Log to FetchLog

3.4. **Create Storage Service** (`app/services/storage_service.py`)

```python
class StorageService:
    """Handle database operations for price data."""

    def save_price_history(self, product, extraction, validation):
        """Save price history record."""

    def log_fetch_attempt(self, product, success, errors, duration_ms):
        """Log fetch attempt for debugging."""

    def update_product_price(self, product, new_price):
        """Update product current price."""
```

3.5. **Add HTTP Client with Rate Limiting**
- Use `httpx.AsyncClient` for HTTP requests
- Implement rate limiting per domain (1 request per 2 seconds)
- Set realistic User-Agent headers
- Handle timeouts and retries

**Acceptance Criteria**:
- ✅ PriceFetcherService implemented with all methods
- ✅ All four extractor types working (JSON-LD, meta, CSS, XPath)
- ✅ fetch_product_price task successfully fetches and stores prices
- ✅ Validation logic prevents bad data
- ✅ Rate limiting works correctly
- ✅ Errors logged to FetchLog
- ✅ Can fetch prices for products with existing patterns

**Estimated Effort**: 3-4 days

---

### Phase 4: Basic Views and Templates (Server-Side)

**Goal**: Implement core views with server-side rendering (no HTMX yet)

**Tasks**:

4.1. **Create URL Configuration** (`app/urls.py`)

```python
urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('products/', views.product_list, name='product_list'),
    path('products/<str:product_id>/', views.product_detail, name='product_detail'),
    path('products/add/', views.add_product, name='add_product'),
    path('notifications/', views.notifications_list, name='notifications_list'),
    # Admin URLs (requires staff permission)
    path('admin/patterns/', views.patterns_status, name='patterns_status'),
]
```

4.2. **Implement Core Views** (`app/views.py`)

From ARCHITECTURE.md, implement:
- `dashboard()` - Main dashboard with stats and recent products
- `product_list()` - List products with search and filtering
- `product_detail()` - Product detail with price history
- `add_product()` - Form to add new product
- `notifications_list()` - User notifications
- `patterns_status()` - Admin pattern health dashboard

4.3. **Create Base Template** (`templates/base.html`)

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}PriceTracker{% endblock %}</title>

    <!-- Tailwind CSS CDN (for now) -->
    <script src="https://cdn.tailwindcss.com"></script>

    <!-- HTMX (for Phase 5) -->
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>

    {% block extra_head %}{% endblock %}
</head>
<body class="bg-gray-50">
    <!-- Navigation -->
    <nav class="bg-white shadow">
        <div class="container mx-auto px-4 py-3 flex justify-between items-center">
            <a href="{% url 'dashboard' %}" class="text-2xl font-bold text-blue-600">
                PriceTracker
            </a>
            <div class="flex items-center gap-4">
                <a href="{% url 'notifications_list' %}" class="relative">
                    🔔
                    {% if unread_count > 0 %}
                    <span class="badge">{{ unread_count }}</span>
                    {% endif %}
                </a>
                <span>{{ user.username }}</span>
            </div>
        </div>
    </nav>

    <!-- Content -->
    <main class="container mx-auto px-4 py-8">
        {% block content %}{% endblock %}
    </main>
</body>
</html>
```

4.4. **Create Dashboard Template** (`templates/dashboard.html`)

From UI_DESIGN_FINAL.md:
- Search box (prominent, centered)
- Quick stats cards (total products, drops 24h, saved, alerts)
- Recent price drops list
- Product list (grid layout)

4.5. **Create Product Templates**
- `templates/product/list.html` - Product list
- `templates/product/detail.html` - Product detail with price chart
- `templates/product/add_form.html` - Add product form

4.6. **Implement Forms** (`app/forms.py`)
- `AddProductForm` - URL, priority, target_price fields
- Form validation for URL format
- Priority choices (high, normal, low)

4.7. **Create ProductService** (`app/services/product_service.py`)

```python
class ProductService:
    """Business logic for product management."""

    def add_product(self, user, url, priority='normal', target_price=None):
        """Add new product and trigger pattern/price fetch."""
        # Parse domain from URL
        # Check if product already exists
        # Create product record
        # Trigger pattern generation if needed
        # Trigger immediate price fetch

    def delete_product(self, product):
        """Soft delete (deactivate) product."""

    def update_product_settings(self, product, **kwargs):
        """Update product settings."""
```

**Acceptance Criteria**:
- ✅ All URLs configured and accessible
- ✅ Dashboard renders with stats and product list
- ✅ Can add product via form (basic submission)
- ✅ Product detail page shows price history (table view)
- ✅ Product list has search and filter functionality
- ✅ Notifications page shows user notifications
- ✅ Admin patterns page shows pattern health
- ✅ All templates use consistent base layout
- ✅ Basic CSS styling with Tailwind

**Estimated Effort**: 3-4 days

---

### Phase 5: HTMX Interactivity and Real-Time Updates

**Goal**: Add dynamic interactions without full page reloads using HTMX

**Tasks**:

5.1. **Update Views for HTMX**

Add HTMX detection to views:
```python
if request.headers.get('HX-Request'):
    # Return partial template
    return render(request, 'product/partials/product_card.html', context)
# Return full page
return render(request, 'product/list.html', context)
```

5.2. **Create HTMX Partials**
- `templates/product/partials/product_card.html` - Individual product card
- `templates/product/partials/product_list.html` - Product list (for filtering)
- `templates/product/partials/chart.html` - Price chart
- `templates/product/partials/settings_form.html` - Product settings form
- `templates/search/autocomplete.html` - Autocomplete results

5.3. **Implement Search Autocomplete**

```html
<input type="text"
       name="q"
       placeholder="Search products or paste URL..."
       hx-get="{% url 'search_autocomplete' %}"
       hx-trigger="keyup changed delay:300ms"
       hx-target="#autocomplete-results"
       minlength="3">
```

Create view:
```python
@login_required
def search_autocomplete(request):
    query = request.GET.get('q', '').strip()
    if len(query) < 3:
        return HttpResponse('')

    # Search user's products
    products = Product.objects.filter(
        user=request.user,
        active=True,
        name__icontains=query
    ).order_by('-last_viewed')[:5]

    return render(request, 'search/autocomplete.html', {'products': products})
```

5.4. **Add Product with HTMX**

Update add product form:
```html
<form hx-post="{% url 'add_product' %}"
      hx-target="#product-list"
      hx-swap="afterbegin">
    <!-- Form fields -->
</form>
```

Add loading states and progress tracking:
```html
<div id="add-status"
     hx-get="{% url 'product_status' product.id %}"
     hx-trigger="every 2s"
     hx-swap="innerHTML">
    ⏳ Adding product...
</div>
```

5.5. **Implement Product Actions with HTMX**
- Delete product (hx-delete with confirmation)
- Update settings (hx-post with inline form)
- Refresh price (hx-post to trigger immediate fetch)

5.6. **Add Notification Polling**

```html
<div id="notifications"
     hx-get="{% url 'notifications_list' %}"
     hx-trigger="load, every 30s"
     hx-swap="innerHTML">
</div>
```

5.7. **Implement Price Chart Updates**

```html
<div class="chart-controls">
    <button hx-get="{% url 'price_chart' product.id %}?days=7"
            hx-target="#chart-container">7D</button>
    <button hx-get="{% url 'price_chart' product.id %}?days=30"
            hx-target="#chart-container">30D</button>
    <button hx-get="{% url 'price_chart' product.id %}?days=90"
            hx-target="#chart-container">90D</button>
</div>
<div id="chart-container">
    <!-- Chart rendered here -->
</div>
```

**Acceptance Criteria**:
- ✅ Search autocomplete works with 300ms debounce
- ✅ Add product form submits via HTMX
- ✅ Loading states shown during pattern generation
- ✅ Product actions (delete, update) work without page reload
- ✅ Notifications update every 30 seconds
- ✅ Price chart updates dynamically with time range buttons
- ✅ All HTMX interactions feel smooth and responsive

**Estimated Effort**: 2-3 days

---

### Phase 6: Notifications and Admin Features

**Goal**: Complete notification system and admin tools for pattern management

**Tasks**:

6.1. **Implement NotificationService** (`app/services/notification_service.py`)

```python
class NotificationService:
    """Create and manage notifications."""

    @staticmethod
    def create_price_drop_notification(product, old_price, new_price):
        """Create price drop notification."""

    @staticmethod
    def create_target_reached_notification(product):
        """Notify when target price is reached."""

    @staticmethod
    def create_restock_notification(product):
        """Notify when product back in stock."""

    @staticmethod
    def create_price_spike_notification(product, old_price, new_price):
        """Notify when price increases significantly."""
```

6.2. **Integrate Notifications into Price Fetch**

Update `fetch_product_price` task:
```python
# After saving price
if product.current_price and new_price < product.current_price:
    NotificationService.create_price_drop_notification(
        product, product.current_price, new_price
    )

if product.target_price and new_price <= product.target_price:
    NotificationService.create_target_reached_notification(product)
```

6.3. **Create Admin Pattern Dashboard**

Template: `templates/admin/patterns.html`
- Table of all patterns with success rates
- Color coding: green (>80%), yellow (60-80%), red (<60%)
- Actions: validate, regenerate, export
- Filter: show only failing patterns

6.4. **Implement AdminFlag Management**

Create views:
- `admin_flags_list()` - List all pending flags
- `resolve_admin_flag()` - Mark flag as resolved
- `regenerate_flagged_pattern()` - Trigger pattern regeneration

Template: `templates/admin/flags.html`
- Group by flag_type
- Show error messages
- Bulk actions (resolve, regenerate)

6.5. **Add Email Notifications (Optional)**

Configure Django email backend:
```python
# settings.py
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.getenv('EMAIL_HOST')
EMAIL_PORT = 587
EMAIL_USE_TLS = True
```

Create email templates:
- `emails/price_drop.html`
- `emails/target_reached.html`

6.6. **Add User Preferences**

Model fields for email preferences:
- `notify_via_email`
- `email_frequency` (instant, daily_digest, weekly_digest)

**Acceptance Criteria**:
- ✅ Notifications created automatically on price changes
- ✅ Target price alerts work correctly
- ✅ Restock notifications work
- ✅ Admin can view pattern health dashboard
- ✅ AdminFlags created for failing patterns
- ✅ Admin can regenerate patterns from dashboard
- ✅ Email notifications sent (if configured)
- ✅ Users can control notification preferences

**Estimated Effort**: 2-3 days

---

### Phase 7: Testing, Optimization, and Deployment

**Goal**: Ensure system is production-ready with tests, optimizations, and deployment

**Tasks**:

7.1. **Create Unit Tests**

`tests/test_models.py`:
- Test Product model properties (price_change_24h, etc.)
- Test Pattern.record_attempt()
- Test Notification.mark_as_read()

`tests/test_services.py`:
- Test PatternService.get_or_generate_pattern()
- Test PriceFetcherService.fetch_product_price()
- Test NotificationService.create_price_drop_notification()

`tests/test_views.py`:
- Test dashboard loads correctly
- Test add product flow
- Test HTMX endpoints return partials

7.2. **Create Integration Tests**

`tests/test_integration.py`:
- Test full flow: add product → generate pattern → fetch price
- Test notification creation on price drop
- Test pattern reuse for same domain

7.3. **Add Celery Task Tests**

`tests/test_tasks.py`:
- Mock ExtractorPatternAgent calls
- Test generate_pattern task
- Test fetch_product_price task
- Test periodic tasks

7.4. **Performance Optimization**

- Add database indexes (already defined in models)
- Optimize queries with select_related() and prefetch_related()
- Add caching for dashboard stats
- Optimize price history queries (limit to recent data)

```python
# Example optimization
products = Product.objects.filter(
    user=request.user
).select_related(
    'user'
).prefetch_related(
    'price_history'
)[:20]
```

7.5. **Add Logging and Monitoring**

Configure Django logging:
```python
LOGGING = {
    'version': 1,
    'handlers': {
        'file': {
            'class': 'logging.FileHandler',
            'filename': 'logs/django.log',
        },
    },
    'loggers': {
        'django': {'handlers': ['file'], 'level': 'INFO'},
        'app': {'handlers': ['file'], 'level': 'DEBUG'},
    },
}
```

7.6. **Create Production Configuration**

`config/settings_prod.py`:
- DEBUG = False
- ALLOWED_HOSTS from environment
- PostgreSQL database (optional, can keep SQLite for MVP)
- Static file serving via WhiteNoise
- Security settings (CSRF, XSS protection)

7.7. **Docker Configuration Updates**

Update `docker-compose.yml`:
- Add health checks for web service
- Configure proper volume mounts
- Set environment variables
- Add restart policies

7.8. **Create Deployment Documentation**

`DEPLOYMENT_GUIDE.md`:
- Prerequisites (Docker, Docker Compose)
- Environment variables
- Initial setup commands
- Running migrations
- Creating superuser
- Accessing admin
- Monitoring logs

7.9. **Load Testing** (Optional)

Test with realistic load:
- 100 products per user
- 1000 users
- Price checks every hour
- Pattern generation for 50 domains

**Acceptance Criteria**:
- ✅ Unit test coverage >70%
- ✅ Integration tests pass
- ✅ Celery tasks tested with mocks
- ✅ Database queries optimized (< 10 queries per page)
- ✅ Logging configured for production
- ✅ Production settings configured
- ✅ Docker containers start successfully
- ✅ Deployment documentation complete
- ✅ Can deploy to production environment

**Estimated Effort**: 3-4 days

---

## 4. Integration Strategy

### 4.1. ExtractorPatternAgent Integration

**Approach**: Direct Python API (recommended)

**Implementation**:

```python
# app/services/pattern_service.py
import sys
from pathlib import Path

# Add ExtractorPatternAgent to Python path
sys.path.insert(0, '/extractor')

from src.agent import ExtractorPatternAgent

class PatternService:
    async def generate_pattern(self, url: str, domain: str) -> dict:
        """Generate pattern using ExtractorPatternAgent."""
        async with ExtractorPatternAgent() as agent:
            patterns = await agent.generate_patterns(url, save_to_db=False)
            return patterns
```

**Alternative**: CLI subprocess (simpler, less efficient)

```python
result = subprocess.run([
    'uv', 'run', '/extractor/extractor-cli.py',
    'generate', url,
    '--output', '/tmp/pattern.json',
    '--no-save'
], timeout=120, capture_output=True, text=True)
```

**Recommendation**: Use Direct Python API for better error handling and performance

---

### 4.2. Price Fetcher Integration

**Phase 3 Approach**: Integrated service within WebUI

```python
# app/services/price_fetcher_service.py
class PriceFetcherService:
    async def fetch_product_price(self, product: Product) -> dict:
        # Integrated logic
```

**Future Approach**: Separate component (if scaling requires)

When/if needed:
1. Extract `price_fetcher_service.py` to separate repo
2. Create CLI interface similar to ExtractorPatternAgent
3. Update Celery tasks to call subprocess
4. No database changes needed (patterns already shared)

---

### 4.3. Database Access Strategy

**Shared SQLite Database**:
- Location: `/app/db.sqlite3`
- Mounted in all Docker containers
- Django manages schema via migrations
- All components read/write directly

**Access Pattern**:
```yaml
# docker-compose.yml
volumes:
  - ./db.sqlite3:/app/db.sqlite3  # Shared volume
```

**Tables**:
- WebUI: Read/Write all tables (primary owner)
- ExtractorPatternAgent: Read/Write `app_pattern` table only
- PriceFetcher: Read `app_product` & `app_pattern`, Write `app_pricehistory` & `app_fetchlog`

---

### 4.4. Celery Task Queue

**Configuration**:

```python
# config/celery.py
from celery import Celery

app = Celery('pricetracker')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Beat schedule
app.conf.beat_schedule = {
    'fetch-high-priority': {
        'task': 'app.tasks.fetch_prices_by_priority',
        'schedule': 900.0,  # 15 minutes
        'args': ('high',)
    },
    'fetch-normal-priority': {
        'task': 'app.tasks.fetch_prices_by_priority',
        'schedule': 3600.0,  # 1 hour
        'args': ('normal',)
    },
    'fetch-low-priority': {
        'task': 'app.tasks.fetch_prices_by_priority',
        'schedule': 86400.0,  # 24 hours
        'args': ('low',)
    },
    'check-pattern-health': {
        'task': 'app.tasks.check_pattern_health',
        'schedule': 86400.0,  # Daily
    },
    'cleanup-old-logs': {
        'task': 'app.tasks.cleanup_old_logs',
        'schedule': 604800.0,  # Weekly
    },
}
```

---

## 5. Technical Decisions

### 5.1. Database

**Decision**: SQLite (MVP), PostgreSQL (production scaling)

**Rationale**:
- SQLite sufficient for < 10K products
- Single-file, simple deployment
- Zero configuration
- Shared easily via Docker volume
- Easy migration path to PostgreSQL

**Migration Strategy**:
```bash
# When needed
python manage.py dumpdata > backup.json
# Update settings.py to PostgreSQL
python manage.py migrate
python manage.py loaddata backup.json
```

---

### 5.2. Frontend Framework

**Decision**: HTMX + Tailwind CSS (no heavy JavaScript framework)

**Rationale**:
- HTMX provides dynamic interactions without React/Vue complexity
- Server-side rendering simpler to develop and debug
- Tailwind CSS for rapid UI development
- Progressive enhancement approach
- Reduces frontend build complexity

**Trade-off**:
- Less suitable for highly interactive UIs
- Acceptable for MVP (forms, lists, dashboards)

---

### 5.3. Authentication

**Decision**: Django built-in authentication (Phase 1), OAuth later (optional)

**Rationale**:
- Django auth is production-ready out of the box
- Username/password sufficient for MVP
- Can add social auth later via django-allauth

---

### 5.4. Static Assets

**Decision**: Tailwind CSS CDN (development), compiled CSS (production)

**Development**:
```html
<script src="https://cdn.tailwindcss.com"></script>
```

**Production**:
```bash
npm install tailwindcss
npx tailwindcss build -o static/css/styles.css
```

---

### 5.5. Testing Strategy

**Decision**: Pytest + pytest-django + factory_boy

**Rationale**:
- Pytest more flexible than Django's TestCase
- factory_boy for test data generation
- pytest-django for Django integration

```python
# tests/factories.py
import factory
from app.models import Product

class ProductFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Product

    id = factory.Faker('uuid4')
    url = factory.Faker('url')
    domain = 'amazon.com'
    name = factory.Faker('sentence')
```

---

## 6. Risks and Mitigations

### Risk 1: ExtractorPatternAgent Takes Too Long (120s timeout)

**Impact**: Users wait long time for pattern generation

**Mitigation**:
- Show clear loading states with progress
- Run pattern generation in background (Celery)
- Poll for status updates every 2 seconds
- Cache patterns aggressively (90% reuse rate expected)
- Provide estimated time (45 seconds average)

---

### Risk 2: Pattern Generation Fails

**Impact**: Product cannot be tracked

**Mitigation**:
- Create AdminFlag for manual review
- Mark product as inactive (don't block user)
- Admin can manually create pattern
- Show user helpful error message
- Retry mechanism (3 attempts)

---

### Risk 3: Price Fetching Fails (Website Changes)

**Impact**: Stale prices, unhappy users

**Mitigation**:
- Log all failures to FetchLog
- Track pattern success rate
- Trigger AdminFlag when success rate drops below 60%
- Daily health check task
- Admin dashboard for pattern monitoring

---

### Risk 4: Rate Limiting by Target Websites

**Impact**: Blocked by e-commerce sites

**Mitigation**:
- Implement rate limiting (1 request per 2 seconds per domain)
- Rotate User-Agent headers
- Respect robots.txt
- Use polite crawling practices
- Add delays between requests

---

### Risk 5: SQLite Concurrency Issues

**Impact**: Database locks, slow writes

**Mitigation**:
- SQLite sufficient for < 10K products
- Write-Ahead Logging (WAL) mode enabled
- Migration path to PostgreSQL documented
- Monitor database size and query performance

```python
# settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
        'OPTIONS': {
            'timeout': 20,
            'journal_mode': 'WAL',  # Better concurrency
        }
    }
}
```

---

### Risk 6: Celery Worker Overload

**Impact**: Tasks delayed, slow system

**Mitigation**:
- Monitor queue length via Flower
- Increase worker count if needed (docker-compose scale)
- Prioritize user-initiated tasks over periodic tasks
- Set task timeouts and retries

---

## 7. Success Criteria

### Phase 1 Success:
- ✅ Django project runs without errors
- ✅ All models created and migrated
- ✅ Admin can create superuser
- ✅ Celery worker connects to Redis

### Phase 2 Success:
- ✅ Can generate patterns via CLI
- ✅ Patterns saved to database
- ✅ Failed generation creates AdminFlag
- ✅ Admin can view patterns

### Phase 3 Success:
- ✅ Can fetch price for product with existing pattern
- ✅ Price saved to PriceHistory
- ✅ Product current_price updated
- ✅ Failures logged to FetchLog

### Phase 4 Success:
- ✅ Dashboard accessible and renders
- ✅ Can add product via form
- ✅ Product detail page shows history
- ✅ All basic pages functional

### Phase 5 Success:
- ✅ Search autocomplete works
- ✅ Add product with HTMX (no page reload)
- ✅ Delete product with HTMX
- ✅ Notifications update automatically
- ✅ Price charts update dynamically

### Phase 6 Success:
- ✅ Notifications created on price drops
- ✅ Target price alerts work
- ✅ Admin pattern dashboard functional
- ✅ AdminFlags created and manageable

### Phase 7 Success:
- ✅ Test coverage >70%
- ✅ All integration tests pass
- ✅ Production deployment successful
- ✅ System stable under normal load

---

## 8. Post-MVP Roadmap

### Near-Term (1-3 months):
1. User authentication via social login (Google, GitHub)
2. Email notifications for price drops
3. Mobile responsive improvements
4. Price prediction using historical data
5. Export price history (CSV, JSON)

### Mid-Term (3-6 months):
1. Extract PriceFetcher to separate component (if scaling needed)
2. PostgreSQL migration for better concurrency
3. Multi-region deployment
4. Advanced analytics dashboard
5. Bulk product import (CSV upload)

### Long-Term (6-12 months):
1. Public API for third-party integrations
2. Browser extension for one-click tracking
3. Price comparison across multiple stores
4. Price history predictions using ML
5. Community-contributed patterns

---

## 9. Timeline Estimate

**Phase-by-Phase**:
- Phase 1: 1-2 days (Django infrastructure & models)
- Phase 2: 2-3 days (Pattern generation integration)
- Phase 3: 3-4 days (Price fetching service)
- Phase 4: 3-4 days (Views and templates)
- Phase 5: 2-3 days (HTMX interactivity)
- Phase 6: 2-3 days (Notifications & admin)
- Phase 7: 3-4 days (Testing & deployment)

**Total**: 16-23 days (~3-4 weeks for full implementation)

**MVP Timeline**: Phases 1-4 (~10-13 days, ~2 weeks for basic functional system)

---

## Summary

This implementation plan provides a comprehensive, phased approach to building the WebUI component of the PriceTracker system. By following the recommended approach (Option B: Integrated Price Fetching), we can deliver an MVP quickly while maintaining the flexibility to scale and refactor later.

**Key Principles**:
1. **Incremental Development**: Each phase builds on the previous
2. **Early Testing**: Test as we build, not after
3. **Pragmatic Trade-offs**: Integrated price fetching for faster MVP
4. **Clear Success Criteria**: Each phase has measurable outcomes
5. **Risk Mitigation**: Identified risks with clear mitigation strategies

**Next Steps**: Review this plan, gather feedback, and proceed with Phase 1 implementation upon approval.
