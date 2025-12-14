# WebUI - User Interface Design (Final)

## Design Decisions

1. ✅ **Default check frequency**: Once per day (24 hours)
2. ✅ **Search autocomplete**: Live suggestions while typing
3. ✅ **Keep it simple**: No "Recently Viewed" section
4. ✅ **Pattern sharing**: Patterns stored per domain, shared across users
5. ✅ **Failed patterns**: Flag for admin review, don't block user

## Main Page: Search Interface (`/`)

### Initial State (Clean & Simple)

```
┌────────────────────────────────────────────────────────────┐
│  [Logo] PriceTracker                      [Notifications]  │
├────────────────────────────────────────────────────────────┤
│                                                             │
│                                                             │
│                    Track Any Product                       │
│                                                             │
│  ┌────────────────────────────────────────────────────┐    │
│  │  🔍  Search products or paste URL...              │🔎 │
│  └────────────────────────────────────────────────────┘    │
│                                                             │
│  Examples:                                                 │
│  • "iPhone 16 Pro"                                         │
│  • "Sony headphones"                                       │
│  • https://amazon.com/product/B0X123                       │
│                                                             │
│  ─────────────────────────────────────────────────────    │
│                                                             │
│  Quick Stats                                               │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐         │
│  │   42    │ │    5    │ │ $127.50 │ │    3    │         │
│  │Tracking │ │Drops 24h│ │  Saved  │ │ At Target│        │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘         │
│                                                             │
│  Recent Price Drops                                        │
│  🔽 Product A dropped to $29.99 (was $34.99) - 5 min ago  │
│  🔽 Product B dropped to $149.99 (was $159.99) - 1h ago   │
│  🔽 Product C dropped to $8.99 (was $12.99) - 2h ago      │
│                                                             │
└────────────────────────────────────────────────────────────┘
```

### Search with Autocomplete

**User types**: "iph" (3+ characters)

```
┌────────────────────────────────────────────────────────────┐
│  [Logo] PriceTracker                      [Notifications]  │
├────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌────────────────────────────────────────────────────┐    │
│  │  🔍  iph|                                         │🔎 │
│  └────────────────────────────────────────────────────┘    │
│  ┌────────────────────────────────────────────────────┐    │
│  │  📦 Your Products                                  │    │
│  │  ─────────────────────────────────────────────    │    │
│  │  • iPhone 16 Pro 256GB                             │    │
│  │  • iPhone 15 Case                                  │    │
│  │  • iPhone Charger Cable                            │    │
│  └────────────────────────────────────────────────────┘    │
│                                                             │
│  [Stats and Recent Drops hidden while searching]           │
│                                                             │
└────────────────────────────────────────────────────────────┘
```

**HTMX Implementation**:
```html
<input type="text"
       name="q"
       placeholder="Search products or paste URL..."
       hx-get="/search/autocomplete"
       hx-trigger="keyup changed delay:300ms, search"
       hx-target="#autocomplete-results"
       hx-indicator="#search-spinner"
       minlength="3">

<div id="autocomplete-results">
  <!-- Suggestions appear here -->
</div>
```

**Backend**:
```python
@login_required
def search_autocomplete(request):
    query = request.GET.get('q', '').strip()

    if len(query) < 3:
        return HttpResponse('')  # Don't search on short queries

    # Check if it's a URL
    if query.startswith('http://') or query.startswith('https://'):
        # Don't show autocomplete for URLs
        return HttpResponse('')

    # Search user's products
    products = Product.objects.filter(
        user=request.user,
        active=True,
        name__icontains=query
    ).order_by('-last_viewed')[:5]

    return render(request, 'search/autocomplete.html', {
        'products': products,
        'query': query
    })
```

### Add Product: Setup Form (Daily Default)

**User pastes**: "https://ebay.com/itm/12345" (not tracked)

```
┌────────────────────────────────────────────────────────────┐
│  [Logo] PriceTracker                      [Notifications]  │
├────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌────────────────────────────────────────────────────┐    │
│  │  🔍  https://ebay.com/itm/12345                   │🔎 │
│  └────────────────────────────────────────────────────┘    │
│                                                             │
│  ⓘ  You're not tracking this product yet                  │
│  ─────────────────────────────────────────────────────    │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  🔗 Found Product from eBay                          │   │
│  │                                                       │   │
│  │  ┌─────────────────────────────────────────────┐    │   │
│  │  │  Quick Setup                                 │    │   │
│  │  │                                               │    │   │
│  │  │  Check frequency:                            │    │   │
│  │  │  ● Daily (24h)                               │    │   │
│  │  │  ○ Hourly (1h)                               │    │   │
│  │  │  ○ Every 15 minutes (high priority)          │    │   │
│  │  │                                               │    │   │
│  │  │  Target Price (optional):                    │    │   │
│  │  │  ┌──────────────┐                            │    │   │
│  │  │  │ $            │                            │    │   │
│  │  │  └──────────────┘                            │    │   │
│  │  │                                               │    │   │
│  │  │  Notify me when:                             │    │   │
│  │  │  ☑ Price drops                               │    │   │
│  │  │  ☐ Target price reached                      │    │   │
│  │  │  ☐ Back in stock                             │    │   │
│  │  └─────────────────────────────────────────────┘    │   │
│  │                                                       │   │
│  │  [✓ Start Tracking]  [Cancel]                       │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└────────────────────────────────────────────────────────────┘
```

### Loading State: Pattern Generation

**After clicking "Start Tracking"**:

```
┌────────────────────────────────────────────────────────────┐
│  ⏳ Adding product to your tracker...                      │
│  ─────────────────────────────────────────────────────    │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  🎯 Setting up price tracking                        │   │
│  │                                                       │   │
│  │  Step 1: Checking if we know this store...          │   │
│  │  ✅ Pattern found for ebay.com (reusing)             │   │
│  │                                                       │   │
│  │  Step 2: Fetching product information...            │   │
│  │  ⏳ In progress                                       │   │
│  │                                                       │   │
│  │  Step 3: Getting first price...                     │   │
│  │  ⏸  Waiting                                          │   │
│  │                                                       │   │
│  │  This usually takes 5-15 seconds                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└────────────────────────────────────────────────────────────┘
```

**If pattern exists** (most common case):
```
Step 1: Checking if we know this store...
✅ Pattern found for amazon.com (reusing)

Step 2: Fetching product information...
⏳ In progress

Step 3: Getting first price...
⏸ Waiting
```

**If pattern does NOT exist** (first time for this store):
```
Step 1: Checking if we know this store...
⚠️ First time tracking amazon.com products

Step 2: Generating extraction pattern...
⏳ Analyzing page structure (this may take 30-60 seconds)

Step 3: Fetching product information...
⏸ Waiting

Step 4: Getting first price...
⏸ Waiting
```

**If pattern generation FAILS**:
```
Step 1: Checking if we know this store...
⚠️ First time tracking obscure-store.com products

Step 2: Generating extraction pattern...
❌ Failed to generate pattern

⚠️  We couldn't automatically extract prices from this page

What happens next:
• Product added to your tracker (inactive)
• Flagged for admin review
• You'll be notified when pattern is ready (1-2 days)

[Understand] [Cancel Add]
```

### Backend: Add Product Logic

```python
# views.py
@login_required
@require_http_methods(["POST"])
def add_product(request):
    url = request.POST.get('url')
    priority = request.POST.get('priority', 'daily')  # daily, hourly, high
    target_price = request.POST.get('target_price')

    # Map priority to check_interval (seconds)
    intervals = {
        'daily': 86400,   # 24 hours
        'hourly': 3600,   # 1 hour
        'high': 900,      # 15 minutes
    }
    check_interval = intervals.get(priority, 86400)

    # Use service to add product
    service = ProductService()
    result = service.add_product(
        user=request.user,
        url=url,
        check_interval=check_interval,
        target_price=target_price,
        notify_on_drop=request.POST.get('notify_on_drop') == 'on',
        notify_on_target=request.POST.get('notify_on_target') == 'on',
        notify_on_restock=request.POST.get('notify_on_restock') == 'on',
    )

    if result['status'] == 'pattern_generation_failed':
        # Show failed state, but product is added (inactive)
        return render(request, 'search/add_failed_pattern.html', {
            'product': result['product'],
            'error': result['error']
        })

    # Return polling template
    return render(request, 'search/add_loading.html', {
        'product_id': result['product_id'],
        'has_pattern': result['has_pattern']
    })


# services.py
class ProductService:
    def add_product(self, user, url, check_interval, target_price=None, **kwargs):
        """Add new product and trigger pattern generation if needed."""
        domain = urlparse(url).netloc

        # Check if product already exists for this user
        existing = Product.objects.filter(url=url, user=user).first()
        if existing:
            existing.active = True
            existing.save()
            return {'status': 'already_exists', 'product_id': existing.id}

        # Create product record
        product = Product.objects.create(
            id=str(uuid.uuid4()),
            user=user,
            url=url,
            domain=domain,
            name=f"Product from {domain}",  # Temporary
            check_interval=check_interval,
            target_price=target_price,
            notify_on_drop=kwargs.get('notify_on_drop', True),
            notify_on_target=kwargs.get('notify_on_target', False),
            notify_on_restock=kwargs.get('notify_on_restock', False),
        )

        # Check if pattern exists for domain
        pattern = Pattern.objects.filter(domain=domain).first()

        if not pattern:
            # Need to generate pattern
            success = self._trigger_pattern_generation(url, domain, product.id)

            if not success:
                # Pattern generation failed
                product.active = False  # Don't check this product yet
                product.save()

                # Create admin flag
                AdminFlag.objects.create(
                    flag_type='pattern_generation_failed',
                    product=product,
                    url=url,
                    domain=domain,
                    error_message='Failed to generate extraction pattern',
                    status='pending'
                )

                return {
                    'status': 'pattern_generation_failed',
                    'product': product,
                    'product_id': product.id,
                    'error': 'Could not generate pattern automatically'
                }

        # Trigger immediate fetch
        self._trigger_fetch(product.id)

        return {
            'status': 'adding',
            'product_id': product.id,
            'has_pattern': pattern is not None
        }

    def _trigger_pattern_generation(self, url, domain, product_id):
        """Trigger ExtractorPatternAgent."""
        try:
            # Option 1: Subprocess
            result = subprocess.run([
                'python',
                '../ExtractorPatternAgent/scripts/generate_pattern.py',
                '--url', url,
                '--domain', domain,
                '--product-id', product_id
            ], timeout=120, capture_output=True)

            return result.returncode == 0
        except subprocess.TimeoutExpired:
            return False
        except Exception as e:
            logger.error(f"Pattern generation failed: {e}")
            return False
```

### Admin Flag Model

```python
# models.py
class AdminFlag(models.Model):
    """Issues that need admin attention."""

    FLAG_TYPES = [
        ('pattern_generation_failed', 'Pattern Generation Failed'),
        ('pattern_low_confidence', 'Pattern Low Confidence'),
        ('fetch_failing_repeatedly', 'Fetch Failing Repeatedly'),
        ('user_reported_issue', 'User Reported Issue'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('wont_fix', "Won't Fix"),
    ]

    flag_type = models.CharField(max_length=50, choices=FLAG_TYPES)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, null=True, blank=True)
    url = models.URLField()
    domain = models.CharField(max_length=255)
    error_message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_flags')

    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['domain', 'status']),
        ]

    def __str__(self):
        return f"{self.get_flag_type_display()} - {self.domain} ({self.status})"
```

## Admin Interface

### Admin Dashboard (`/admin/flags`)

**Purpose**: Review and fix issues flagged by the system

```
┌────────────────────────────────────────────────────────────┐
│  Admin Dashboard                               [Logout]    │
├────────────────────────────────────────────────────────────┤
│  Flagged Items (12 pending)                                │
│                                                             │
│  Filters:                                                  │
│  [All] [Pattern Failed] [Low Confidence] [Fetch Failing]  │
│  Status: [Pending] [In Progress] [Resolved]               │
├────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  ❌ Pattern Generation Failed          2 hours ago  │   │
│  │  Domain: rarestore.com                               │   │
│  │  URL: https://rarestore.com/product/12345           │   │
│  │  Error: Could not find price selector               │   │
│  │                                                       │   │
│  │  Affected Users: 1                                   │   │
│  │  • user@example.com (added to tracker, inactive)    │   │
│  │                                                       │   │
│  │  [View Page] [Generate Pattern Manually]            │   │
│  │  [Mark Won't Fix] [Assign to Me]                    │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  ⚠️ Pattern Low Confidence                1 day ago │   │
│  │  Domain: amazon.com                                  │   │
│  │  Success Rate: 45% (9/20 fetches)                   │   │
│  │                                                       │   │
│  │  Affected Products: 15                              │   │
│  │                                                       │   │
│  │  [View Pattern] [Regenerate Pattern]                │   │
│  │  [View Failed Fetches]                              │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└────────────────────────────────────────────────────────────┘
```

### Admin: Manual Pattern Generation

```
┌────────────────────────────────────────────────────────────┐
│  Manual Pattern Generation                                 │
├────────────────────────────────────────────────────────────┤
│  Domain: rarestore.com                                     │
│  URL: https://rarestore.com/product/12345                  │
│                                                             │
│  ┌──────────────────────────────────────────────────┐      │
│  │  Page Preview                                    │      │
│  │  [Screenshot of page]                            │      │
│  │                                                   │      │
│  │  Detected Elements:                              │      │
│  │  • Potential price: "$29.99" (class: price-tag)  │      │
│  │  • Potential title: "Product Name" (id: title)   │      │
│  └──────────────────────────────────────────────────┘      │
│                                                             │
│  Pattern Configuration                                     │
│  ┌──────────────────────────────────────────────────┐      │
│  │  Price Selector:                                 │      │
│  │  ┌────────────────────────────────────────────┐  │      │
│  │  │ .price-tag                                 │  │      │
│  │  └────────────────────────────────────────────┘  │      │
│  │  Type: ● CSS  ○ XPath  ○ JSON-LD               │      │
│  │                                                   │      │
│  │  [Test Selector] → Result: $29.99 ✓             │      │
│  └──────────────────────────────────────────────────┘      │
│                                                             │
│  [Save Pattern] [Trigger Agent Retry] [Cancel]            │
└────────────────────────────────────────────────────────────┘
```

## Updated Models

```python
# Update Product model
class Product(models.Model):
    # ... existing fields ...

    # Check intervals mapped to priorities
    CHECK_INTERVAL_CHOICES = [
        (86400, 'Daily (24 hours)'),
        (3600, 'Hourly'),
        (900, 'Every 15 minutes'),
    ]

    check_interval = models.IntegerField(
        default=86400,  # Daily default
        choices=CHECK_INTERVAL_CHOICES
    )

    @property
    def priority_display(self):
        """Human-readable priority."""
        if self.check_interval == 900:
            return "High Priority"
        elif self.check_interval == 3600:
            return "Normal Priority"
        else:
            return "Low Priority"
```

## Simplified UX Flow

### New User Journey (60 seconds total)

```
1. User opens app
   → Clean search box, examples shown

2. User pastes Amazon URL
   → "Not tracking yet" + setup form appears

3. User sees "Daily (24h)" is selected by default
   → Leaves it, clicks "Start Tracking" (5 seconds)

4. Loading screen appears
   → "Pattern found for amazon.com (reusing)" ✓
   → "Fetching product information..." ⏳
   → "Getting first price..." ⏳
   (10-15 seconds)

5. Success!
   → Product card appears with:
     • Product name (fetched)
     • Current price
     • "Just added" timestamp

6. User clicks "View Details"
   → Sees full page
   → "Price history will appear after first day"
```

### Pattern Reuse Flow (90% of cases)

```
User adds product from Amazon
    ↓
Check Pattern table for "amazon.com"
    ↓
✓ Found (created by previous user)
    ↓
Skip pattern generation entirely
    ↓
Just fetch price using existing pattern (5-10 seconds)
    ↓
Done!
```

### Pattern Generation Flow (10% of cases, new store)

```
User adds product from "new-store.com"
    ↓
Check Pattern table for "new-store.com"
    ↓
✗ Not found
    ↓
Trigger ExtractorPatternAgent
    ↓
Wait 30-60 seconds (show progress)
    ↓
SUCCESS → Store pattern → Fetch price → Done!
    OR
FAILED → Flag for admin → Product added (inactive) → User notified later
```

## Configuration Values

```yaml
# config/settings.yaml
check_intervals:
  daily: 86400      # 24 hours (default)
  hourly: 3600      # 1 hour
  high: 900         # 15 minutes

pattern_generation:
  timeout: 120      # 2 minutes max
  retry_on_fail: false
  flag_for_admin: true

autocomplete:
  min_chars: 3
  max_results: 5
  delay_ms: 300

admin:
  flag_retention_days: 90
  auto_close_resolved: 30  # days
```

## Autocomplete Template

```html
<!-- templates/search/autocomplete.html -->
<div class="autocomplete-dropdown">
  {% if products %}
    <div class="autocomplete-section">
      <div class="autocomplete-header">📦 Your Products</div>
      {% for product in products %}
        <a href="{% url 'product_detail' product.id %}"
           class="autocomplete-item">
          <img src="{{ product.image_url }}" class="autocomplete-thumb">
          <div class="autocomplete-info">
            <div class="autocomplete-name">{{ product.name }}</div>
            <div class="autocomplete-price">${{ product.current_price }}</div>
          </div>
        </a>
      {% endfor %}
    </div>
  {% else %}
    <div class="autocomplete-empty">
      No matching products. Paste a URL to add a new one.
    </div>
  {% endif %}
</div>
```

## Key Improvements

1. ✅ **Daily default** - Most users don't need hourly checks
2. ✅ **Pattern reuse** - 90% of adds will be instant (pattern exists)
3. ✅ **Autocomplete** - Find products faster as you type
4. ✅ **Admin review** - Failed patterns don't block users
5. ✅ **Simplified UI** - Removed "Recently Viewed", cleaner layout
6. ✅ **Clear communication** - Loading states show pattern reuse vs. generation

Would you like me to:
1. **Build the Django views** implementing this flow?
2. **Create the HTML/HTMX templates** for search and add?
3. **Implement the ProductService** with pattern reuse logic?
4. **Build the admin dashboard** for reviewing flags?