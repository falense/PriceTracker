# WebUI - Django + HTMX Interface

## Purpose

Web interface for users to add, view, and manage tracked products. Uses Django backend with HTMX for dynamic interactions without heavy JavaScript.

## Architecture

```
┌──────────────────────────────────────────────┐
│           Browser (User)                     │
└────────────────┬─────────────────────────────┘
                 │ HTTP/HTMX
                 ▼
┌──────────────────────────────────────────────┐
│         Django Web Server                    │
│  ┌────────────────────────────────┐          │
│  │  Views (HTMX endpoints)        │          │
│  │  - Dashboard                   │          │
│  │  - Add product                 │          │
│  │  - Product detail              │          │
│  │  - Price history chart         │          │
│  └────────────────────────────────┘          │
│  ┌────────────────────────────────┐          │
│  │  Models (Django ORM)           │          │
│  │  - Product                     │          │
│  │  - PriceHistory                │          │
│  │  - Pattern                     │          │
│  │  - UserPreference              │          │
│  └────────────────────────────────┘          │
│  ┌────────────────────────────────┐          │
│  │  Services                      │          │
│  │  - Trigger ExtractorAgent      │          │
│  │  - Query price data            │          │
│  │  - Track views/interactions    │          │
│  └────────────────────────────────┘          │
└────────────────┬─────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────┐
│         SQLite Database                      │
│  - products                                  │
│  - price_history                             │
│  - patterns                                  │
│  - user_views                                │
│  - notifications                             │
└──────────────────────────────────────────────┘
```

## Component Structure

```
WebUI/
├── ARCHITECTURE.md
├── manage.py                    # Django management
├── config/
│   ├── settings.py             # Django settings
│   ├── urls.py                 # Root URL config
│   └── wsgi.py
│
├── app/                        # Main Django app
│   ├── models.py              # Database models
│   ├── views.py               # View functions
│   ├── urls.py                # App URLs
│   ├── forms.py               # Django forms
│   ├── services.py            # Business logic
│   ├── admin.py               # Django admin
│   └── templatetags/          # Custom template tags
│       └── filters.py
│
├── templates/
│   ├── base.html              # Base layout
│   ├── dashboard.html         # Main dashboard
│   ├── product/
│   │   ├── list.html          # Product list
│   │   ├── detail.html        # Product detail
│   │   ├── add_form.html      # Add product form
│   │   └── partials/          # HTMX partials
│   │       ├── price_row.html
│   │       ├── product_card.html
│   │       └── chart.html
│   └── components/
│       ├── navbar.html
│       └── alert.html
│
├── static/
│   ├── css/
│   │   └── styles.css         # Custom styles
│   ├── js/
│   │   └── charts.js          # Chart.js integration
│   └── img/
│
└── requirements.txt
```

## Database Models (models.py)

```python
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import json

class Product(models.Model):
    """Tracked product."""

    PRIORITY_CHOICES = [
        ('high', 'High'),      # Check every 15 min
        ('normal', 'Normal'),  # Check every 1 hour
        ('low', 'Low'),        # Check every 6 hours
    ]

    id = models.CharField(primary_key=True, max_length=36)  # UUID
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='products')
    url = models.URLField(unique=True)
    domain = models.CharField(max_length=255, db_index=True)
    name = models.CharField(max_length=500)
    current_price = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    currency = models.CharField(max_length=3, default='USD')
    available = models.BooleanField(default=True)
    image_url = models.URLField(null=True, blank=True)

    # Tracking
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='normal')
    active = models.BooleanField(default=True)
    check_interval = models.IntegerField(default=3600)  # seconds
    last_checked = models.DateTimeField(null=True, blank=True)

    # User engagement
    view_count = models.IntegerField(default=0)
    last_viewed = models.DateTimeField(null=True, blank=True)

    # Alerts
    target_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    notify_on_drop = models.BooleanField(default=True)
    notify_on_restock = models.BooleanField(default=False)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    pattern_version = models.CharField(max_length=50, null=True)

    class Meta:
        ordering = ['-last_viewed', '-created_at']
        indexes = [
            models.Index(fields=['user', 'active']),
            models.Index(fields=['domain']),
            models.Index(fields=['last_checked']),
        ]

    def __str__(self):
        return f"{self.name} ({self.domain})"

    def record_view(self):
        """Track that user viewed this product."""
        self.view_count += 1
        self.last_viewed = timezone.now()
        self.save(update_fields=['view_count', 'last_viewed'])

    @property
    def price_change_24h(self):
        """Calculate 24h price change."""
        from datetime import timedelta
        yesterday = timezone.now() - timedelta(days=1)
        old_price = self.price_history.filter(
            recorded_at__lte=yesterday
        ).order_by('-recorded_at').first()

        if old_price and self.current_price:
            return self.current_price - old_price.price
        return None

    @property
    def lowest_price(self):
        """Get lowest recorded price."""
        lowest = self.price_history.order_by('price').first()
        return lowest.price if lowest else None

    @property
    def highest_price(self):
        """Get highest recorded price."""
        highest = self.price_history.order_by('-price').first()
        return highest.price if highest else None


class PriceHistory(models.Model):
    """Historical price records."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='price_history')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    available = models.BooleanField(default=True)
    extracted_data = models.JSONField(default=dict)  # Full extraction result
    confidence = models.FloatField(default=1.0)  # 0.0 - 1.0
    recorded_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-recorded_at']
        indexes = [
            models.Index(fields=['product', '-recorded_at']),
        ]
        verbose_name_plural = 'Price histories'

    def __str__(self):
        return f"{self.product.name}: ${self.price} at {self.recorded_at}"


class Pattern(models.Model):
    """Extraction patterns per domain."""

    domain = models.CharField(max_length=255, unique=True, db_index=True)
    pattern_json = models.JSONField()  # Full pattern structure
    success_rate = models.FloatField(default=0.0)  # % successful extractions
    total_attempts = models.IntegerField(default=0)
    successful_attempts = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_validated = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['domain']

    def __str__(self):
        return f"Pattern for {self.domain} ({self.success_rate:.1%})"

    def record_attempt(self, success: bool):
        """Record pattern usage."""
        self.total_attempts += 1
        if success:
            self.successful_attempts += 1
        self.success_rate = self.successful_attempts / self.total_attempts
        self.save()


class UserView(models.Model):
    """Track user product views for analytics."""

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    viewed_at = models.DateTimeField(auto_now_add=True)
    duration_seconds = models.IntegerField(null=True)  # Time spent on page

    class Meta:
        ordering = ['-viewed_at']
        indexes = [
            models.Index(fields=['user', '-viewed_at']),
            models.Index(fields=['product', '-viewed_at']),
        ]


class Notification(models.Model):
    """User notifications for price changes."""

    NOTIFICATION_TYPES = [
        ('price_drop', 'Price Drop'),
        ('target_reached', 'Target Price Reached'),
        ('restock', 'Back in Stock'),
        ('price_spike', 'Price Increased'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    message = models.TextField()

    old_price = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    new_price = models.DecimalField(max_digits=10, decimal_places=2, null=True)

    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'read', '-created_at']),
        ]

    def mark_as_read(self):
        """Mark notification as read."""
        if not self.read:
            self.read = True
            self.read_at = timezone.now()
            self.save()


class FetchLog(models.Model):
    """Log fetch attempts for debugging."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='fetch_logs')
    success = models.BooleanField()
    extraction_method = models.CharField(max_length=50, null=True)  # "css", "xpath", "jsonld"
    errors = models.JSONField(default=list)
    warnings = models.JSONField(default=list)
    duration_ms = models.IntegerField(null=True)
    fetched_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fetched_at']
        indexes = [
            models.Index(fields=['product', '-fetched_at']),
            models.Index(fields=['success', '-fetched_at']),
        ]
```

## Views (views.py)

```python
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.db.models import Q, Count, Avg
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from .models import Product, PriceHistory, Notification, Pattern
from .services import ProductService
from .forms import AddProductForm
import json

@login_required
def dashboard(request):
    """Main dashboard view."""
    products = Product.objects.filter(
        user=request.user,
        active=True
    ).select_related('price_history')[:20]

    notifications = Notification.objects.filter(
        user=request.user,
        read=False
    )[:5]

    stats = {
        'total_products': Product.objects.filter(user=request.user, active=True).count(),
        'price_drops_24h': _count_price_drops_24h(request.user),
        'total_saved': _calculate_total_saved(request.user),
        'active_alerts': products.filter(target_price__isnull=False).count(),
    }

    context = {
        'products': products,
        'notifications': notifications,
        'stats': stats,
    }
    return render(request, 'dashboard.html', context)


@login_required
def product_list(request):
    """List all products with filtering."""
    products = Product.objects.filter(user=request.user, active=True)

    # Filters
    domain = request.GET.get('domain')
    if domain:
        products = products.filter(domain=domain)

    search = request.GET.get('q')
    if search:
        products = products.filter(
            Q(name__icontains=search) | Q(url__icontains=search)
        )

    sort = request.GET.get('sort', '-last_viewed')
    products = products.order_by(sort)

    # HTMX: Return partial if requested
    if request.headers.get('HX-Request'):
        return render(request, 'product/partials/product_list.html', {'products': products})

    return render(request, 'product/list.html', {'products': products})


@login_required
def product_detail(request, product_id):
    """Product detail page with price history."""
    product = get_object_or_404(Product, id=product_id, user=request.user)

    # Record view
    product.record_view()

    # Get price history
    price_history = product.price_history.all()[:100]

    # Get recent fetch logs
    fetch_logs = product.fetch_logs.all()[:10]

    # Chart data for JavaScript
    chart_data = {
        'labels': [ph.recorded_at.strftime('%Y-%m-%d %H:%M') for ph in price_history],
        'prices': [float(ph.price) for ph in price_history],
    }

    context = {
        'product': product,
        'price_history': price_history,
        'fetch_logs': fetch_logs,
        'chart_data': json.dumps(chart_data),
    }

    return render(request, 'product/detail.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def add_product(request):
    """Add new product to track."""
    if request.method == 'POST':
        form = AddProductForm(request.POST)
        if form.is_valid():
            url = form.cleaned_data['url']
            priority = form.cleaned_data['priority']
            target_price = form.cleaned_data.get('target_price')

            # Use service to create product and trigger pattern generation
            service = ProductService()
            product = service.add_product(
                user=request.user,
                url=url,
                priority=priority,
                target_price=target_price
            )

            # HTMX: Return partial with new product
            if request.headers.get('HX-Request'):
                return render(request, 'product/partials/product_card.html', {'product': product})

            return redirect('product_detail', product_id=product.id)
    else:
        form = AddProductForm()

    return render(request, 'product/add_form.html', {'form': form})


@login_required
@require_http_methods(["POST"])
def update_product_settings(request, product_id):
    """Update product settings via HTMX."""
    product = get_object_or_404(Product, id=product_id, user=request.user)

    # Update fields from form
    product.priority = request.POST.get('priority', product.priority)
    product.target_price = request.POST.get('target_price') or None
    product.notify_on_drop = request.POST.get('notify_on_drop') == 'on'
    product.notify_on_restock = request.POST.get('notify_on_restock') == 'on'
    product.save()

    # HTMX: Return updated partial
    return render(request, 'product/partials/settings_form.html', {'product': product})


@login_required
@require_http_methods(["DELETE"])
def delete_product(request, product_id):
    """Delete (deactivate) product."""
    product = get_object_or_404(Product, id=product_id, user=request.user)
    product.active = False
    product.save()

    # HTMX: Return empty response with trigger to remove element
    response = HttpResponse("")
    response['HX-Trigger'] = 'productDeleted'
    return response


@login_required
def price_history_chart(request, product_id):
    """HTMX endpoint for price chart data."""
    product = get_object_or_404(Product, id=product_id, user=request.user)

    days = int(request.GET.get('days', 30))
    from datetime import timedelta
    since = timezone.now() - timedelta(days=days)

    price_history = product.price_history.filter(recorded_at__gte=since)

    context = {
        'product': product,
        'price_history': price_history,
    }

    return render(request, 'product/partials/chart.html', context)


@login_required
def notifications_list(request):
    """List notifications."""
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:50]

    # Mark as read
    if request.method == 'POST':
        Notification.objects.filter(user=request.user, read=False).update(read=True, read_at=timezone.now())

    if request.headers.get('HX-Request'):
        return render(request, 'partials/notification_list.html', {'notifications': notifications})

    return render(request, 'notifications.html', {'notifications': notifications})


@login_required
def patterns_status(request):
    """Admin view for pattern health."""
    if not request.user.is_staff:
        return redirect('dashboard')

    patterns = Pattern.objects.all().order_by('-success_rate')

    context = {
        'patterns': patterns,
    }

    return render(request, 'admin/patterns.html', context)


# Helper functions
def _count_price_drops_24h(user):
    """Count products with price drops in last 24h."""
    from datetime import timedelta
    yesterday = timezone.now() - timedelta(days=1)
    count = 0

    for product in Product.objects.filter(user=user, active=True):
        change = product.price_change_24h
        if change and change < 0:
            count += 1

    return count


def _calculate_total_saved(user):
    """Calculate total savings vs highest prices."""
    from decimal import Decimal
    total = Decimal('0.00')

    for product in Product.objects.filter(user=user, active=True):
        if product.current_price and product.highest_price:
            savings = product.highest_price - product.current_price
            if savings > 0:
                total += savings

    return total
```

## Services (services.py)

```python
from .models import Product, Pattern
from django.utils import timezone
import uuid
import subprocess
import json
from urllib.parse import urlparse

class ProductService:
    """Business logic for product management."""

    def add_product(self, user, url: str, priority: str = 'normal', target_price=None) -> Product:
        """
        Add new product and trigger pattern generation if needed.
        """
        # Parse domain
        domain = urlparse(url).netloc

        # Check if product already exists
        existing = Product.objects.filter(url=url).first()
        if existing:
            if existing.user != user:
                # Clone for this user
                product = self._clone_product(existing, user)
            else:
                existing.active = True
                existing.save()
                return existing
        else:
            # Create new product
            product = Product.objects.create(
                id=str(uuid.uuid4()),
                user=user,
                url=url,
                domain=domain,
                name=f"Product from {domain}",  # Temporary
                priority=priority,
                target_price=target_price,
            )

        # Check if pattern exists for domain
        pattern = Pattern.objects.filter(domain=domain).first()
        if not pattern:
            # Trigger ExtractorPatternAgent
            self._trigger_pattern_generation(url, domain)

        # Trigger immediate fetch
        self._trigger_fetch(product.id)

        return product

    def _trigger_pattern_generation(self, url: str, domain: str):
        """
        Trigger ExtractorPatternAgent to generate patterns.
        Uses Celery for async execution.
        """
        from .tasks import generate_pattern

        # Trigger async task
        task = generate_pattern.delay(url, domain)
        return task.id

    def _trigger_fetch(self, product_id: str):
        """Trigger immediate price fetch for new product."""
        from .tasks import fetch_product_price

        # Trigger async task
        task = fetch_product_price.delay(product_id)
        return task.id

    def _clone_product(self, source: Product, new_user) -> Product:
        """Clone product for different user."""
        return Product.objects.create(
            id=str(uuid.uuid4()),
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
        from .models import Notification

        if not product.notify_on_drop:
            return

        message = f"{product.name} dropped from ${old_price} to ${new_price}"

        Notification.objects.create(
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
        from .models import Notification

        if not product.target_price:
            return

        if product.current_price <= product.target_price:
            message = f"{product.name} reached your target price of ${product.target_price}!"

            Notification.objects.create(
                user=product.user,
                product=product,
                notification_type='target_reached',
                message=message,
                new_price=product.current_price,
            )
```

## Forms (forms.py)

```python
from django import forms
from .models import Product

class AddProductForm(forms.Form):
    """Form for adding new product."""

    url = forms.URLField(
        label='Product URL',
        widget=forms.URLInput(attrs={
            'class': 'form-input',
            'placeholder': 'https://amazon.com/...',
            'required': True
        })
    )

    priority = forms.ChoiceField(
        choices=Product.PRIORITY_CHOICES,
        initial='normal',
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    target_price = forms.DecimalField(
        label='Target Price (optional)',
        required=False,
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-input',
            'placeholder': '29.99',
            'step': '0.01'
        })
    )
```

## HTMX Integration Examples

### Template: dashboard.html

```html
{% extends 'base.html' %}

{% block content %}
<div class="container mx-auto px-4 py-8">
    <!-- Stats Cards -->
    <div class="grid grid-cols-4 gap-4 mb-8">
        <div class="stat-card">
            <h3>Total Products</h3>
            <p class="text-3xl">{{ stats.total_products }}</p>
        </div>
        <div class="stat-card">
            <h3>Price Drops (24h)</h3>
            <p class="text-3xl text-green-600">{{ stats.price_drops_24h }}</p>
        </div>
        <div class="stat-card">
            <h3>Total Saved</h3>
            <p class="text-3xl text-blue-600">${{ stats.total_saved }}</p>
        </div>
        <div class="stat-card">
            <h3>Active Alerts</h3>
            <p class="text-3xl">{{ stats.active_alerts }}</p>
        </div>
    </div>

    <!-- Add Product Form (HTMX) -->
    <div class="mb-8">
        <button
            hx-get="{% url 'add_product' %}"
            hx-target="#add-product-form"
            hx-swap="innerHTML"
            class="btn btn-primary">
            + Add Product
        </button>
        <div id="add-product-form"></div>
    </div>

    <!-- Product List (HTMX) -->
    <div id="product-list" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {% for product in products %}
            {% include 'product/partials/product_card.html' %}
        {% endfor %}
    </div>

    <!-- Notifications Sidebar -->
    <div
        hx-get="{% url 'notifications_list' %}"
        hx-trigger="load, every 30s"
        hx-swap="innerHTML"
        id="notifications">
    </div>
</div>
{% endblock %}
```

### Partial: product/partials/product_card.html

```html
<div class="product-card" id="product-{{ product.id }}">
    <img src="{{ product.image_url }}" alt="{{ product.name }}" class="product-image">

    <div class="product-info">
        <h3>{{ product.name }}</h3>
        <p class="text-sm text-gray-600">{{ product.domain }}</p>

        <div class="price-section">
            <span class="current-price">${{ product.current_price }}</span>

            {% if product.price_change_24h %}
                <span class="price-change {% if product.price_change_24h < 0 %}text-green-600{% else %}text-red-600{% endif %}">
                    {% if product.price_change_24h > 0 %}+{% endif %}${{ product.price_change_24h }}
                </span>
            {% endif %}
        </div>

        <div class="product-actions">
            <a href="{% url 'product_detail' product.id %}" class="btn btn-sm">View Details</a>

            <button
                hx-delete="{% url 'delete_product' product.id %}"
                hx-target="#product-{{ product.id }}"
                hx-swap="outerHTML"
                hx-confirm="Remove this product?"
                class="btn btn-sm btn-danger">
                Remove
            </button>
        </div>
    </div>
</div>
```

### Partial: product/partials/chart.html

```html
<div class="price-chart-container">
    <canvas id="price-chart-{{ product.id }}"></canvas>
</div>

<script>
const ctx = document.getElementById('price-chart-{{ product.id }}').getContext('2d');
const chart = new Chart(ctx, {
    type: 'line',
    data: {
        labels: [{% for ph in price_history %}'{{ ph.recorded_at|date:"M d, H:i" }}'{% if not forloop.last %},{% endif %}{% endfor %}],
        datasets: [{
            label: 'Price',
            data: [{% for ph in price_history %}{{ ph.price }}{% if not forloop.last %},{% endif %}{% endfor %}],
            borderColor: 'rgb(75, 192, 192)',
            tension: 0.1
        }]
    },
    options: {
        responsive: true,
        scales: {
            y: {
                beginAtZero: false
            }
        }
    }
});
</script>
```

## Configuration (settings.py)

```python
# Django settings
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# HTMX middleware
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# Static files
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']

# Templates with HTMX
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# Celery (optional, for async tasks)
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
```

## Dependencies (requirements.txt)

```txt
Django>=4.2.0
django-htmx>=1.17.0
Pillow>=10.0.0              # Image handling
django-extensions>=3.2.0     # Dev tools
celery>=5.3.0               # Async tasks
redis>=5.0.0                # Celery backend
```

## Integration with Other Components

```
User adds product (WebUI)
    ↓
ProductService.add_product()
    ↓
Check if pattern exists for domain
    ↓
NO → Trigger ExtractorPatternAgent (subprocess/Celery)
    ↓
ExtractorPatternAgent generates pattern → patterns.db
    ↓
Trigger immediate fetch (PriceFetcher)
    ↓
PriceFetcher stores price → prices.db
    ↓
WebUI displays result (HTMX update)
```

## Key Features

1. **Real-time Updates**: HTMX for dynamic content without page reloads
2. **User Tracking**: Records views, engagement for analytics
3. **Smart Notifications**: Price drops, target reached, restocks
4. **Price Charts**: Historical visualization with Chart.js
5. **Pattern Health**: Admin view for monitoring extraction success
6. **Quick Actions**: Add, update, delete products inline

## Next Steps

1. Implement Django models and migrations
2. Build core views and HTMX endpoints
3. Create responsive templates with Tailwind CSS
4. Add authentication (Django built-in)
5. Integrate with ExtractorPatternAgent and PriceFetcher
6. Add Celery for async tasks
7. Deploy with Gunicorn + Nginx
