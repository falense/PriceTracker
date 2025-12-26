"""
Database models for PriceTracker WebUI - Multi-Store Support.

This version supports:
- Product-Store separation (products can be sold by multiple stores)
- User subscriptions to products (not specific store listings)
- Aggregated priority (highest priority from any subscriber)
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Max, Q
from datetime import timedelta
import uuid
import re


def normalize_name(name):
    """Normalize product name for matching."""
    if not name:
        return ''
    # Lowercase, remove special chars, normalize whitespace
    normalized = re.sub(r'[^\w\s]', '', name.lower())
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    return normalized


class Product(models.Model):
    """
    Normalized product entity - no URL, no user FK.
    Represents a unique product across all stores.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Product identification (normalized across stores)
    name = models.CharField(max_length=500, db_index=True)
    canonical_name = models.CharField(
        max_length=500,
        db_index=True,
        help_text='Normalized name for matching (lowercase, no special chars)'
    )

    # Product attributes (brand, model, etc.)
    brand = models.CharField(max_length=200, blank=True, null=True, db_index=True)
    model_number = models.CharField(max_length=200, blank=True, null=True, db_index=True)
    category = models.CharField(max_length=200, blank=True, null=True)

    # Universal product identifiers (when available)
    ean = models.CharField(max_length=13, blank=True, null=True, unique=True, db_index=True)
    upc = models.CharField(max_length=12, blank=True, null=True, unique=True, db_index=True)
    isbn = models.CharField(max_length=13, blank=True, null=True, unique=True, db_index=True)

    # Image (use best available across all listings)
    image_url = models.URLField(max_length=1000, null=True, blank=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Derived fields (computed from subscriptions)
    subscriber_count = models.IntegerField(default=0, help_text='Number of users subscribed')

    class Meta:
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['canonical_name']),
            models.Index(fields=['brand', 'model_number']),
            models.Index(fields=['ean']),
            models.Index(fields=['upc']),
            models.Index(fields=['subscriber_count']),
        ]
        verbose_name = 'Product'
        verbose_name_plural = 'Products'

    def __str__(self):
        return f"{self.name} ({self.brand or 'Unknown Brand'})"

    def save(self, *args, **kwargs):
        """Auto-generate canonical_name from name."""
        if self.name and not self.canonical_name:
            self.canonical_name = normalize_name(self.name)
        super().save(*args, **kwargs)

    @property
    def effective_priority(self):
        """
        Calculate effective priority from all user subscriptions.
        Returns the HIGHEST priority set by ANY subscribing user.
        """
        subscriptions = self.subscriptions.filter(active=True)
        if not subscriptions.exists():
            return 'low'

        # Priority order: normal > low
        max_priority = subscriptions.aggregate(
            max_priority=Max('priority')
        )['max_priority']

        # Convert int back to string
        priority_map = {2: 'normal', 1: 'low'}
        return priority_map.get(max_priority, 'low')

    @property
    def check_interval(self):
        """Get check interval based on effective priority."""
        intervals = {'normal': 3600, 'low': 86400}
        return intervals.get(self.effective_priority, 3600)

    @property
    def is_due_for_check(self):
        """
        Check if ANY listing for this product is due for checking.
        Based on effective priority from user subscriptions.
        """
        latest_check = self.listings.aggregate(
            latest=Max('last_checked')
        )['latest']

        if not latest_check:
            return True

        time_since_check = (timezone.now() - latest_check).total_seconds()
        return time_since_check >= self.check_interval

    @property
    def lowest_price_listing(self):
        """Get the listing with the lowest current price (prefers available items)."""
        # First try to get an available listing with price
        available_listing = self.listings.filter(
            available=True,
            current_price__isnull=False
        ).order_by('current_price').first()

        if available_listing:
            return available_listing

        # If no available listings, return any listing with a price
        return self.listings.filter(
            current_price__isnull=False
        ).order_by('current_price').first()

    @property
    def best_price_history(self):
        """Get historical lowest price across all stores."""
        from django.db.models import Min
        lowest = PriceHistory.objects.filter(
            listing__product=self
        ).aggregate(Min('price'))['price__min']
        return lowest


class Store(models.Model):
    """
    Merchant/Store entity.
    Represents a unique online store/retailer.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Store identification
    name = models.CharField(max_length=200, unique=True)
    domain = models.CharField(max_length=255, unique=True, db_index=True)

    # Store metadata
    country = models.CharField(max_length=2, blank=True, help_text='ISO country code')
    currency = models.CharField(max_length=3, default='USD')
    logo_url = models.URLField(max_length=1000, null=True, blank=True)

    # Store status
    active = models.BooleanField(default=True)
    verified = models.BooleanField(
        default=False,
        help_text='Store verified and trusted for scraping'
    )

    # Rate limiting
    rate_limit_seconds = models.IntegerField(
        default=2,
        help_text='Minimum seconds between requests to this store'
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['domain']),
            models.Index(fields=['active', 'verified']),
        ]
        verbose_name = 'Store'
        verbose_name_plural = 'Stores'

    def __str__(self):
        return f"{self.name} ({self.domain})"

    @property
    def has_pattern(self):
        """Check if extraction pattern exists for this store."""
        return hasattr(self, 'pattern') or Pattern.objects.filter(domain=self.domain).exists()


class ProductListing(models.Model):
    """
    Join table connecting Product + Store + URL.
    Represents a specific product being sold at a specific store.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Relationships
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='listings'
    )
    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name='listings'
    )

    # Listing-specific data
    url = models.URLField(max_length=1000, unique=True, db_index=True)
    store_product_id = models.CharField(
        max_length=200,
        blank=True,
        help_text='Store-specific product ID (e.g., ASIN for Amazon)'
    )

    # Current price state for this listing
    current_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    currency = models.CharField(max_length=3, default='USD')
    available = models.BooleanField(default=True)

    # Listing-specific metadata
    shipping_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    seller_name = models.CharField(max_length=200, blank=True)
    seller_rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        null=True,
        blank=True
    )

    # Tracking state
    active = models.BooleanField(default=True)
    last_checked = models.DateTimeField(null=True, blank=True)
    last_available = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Last time product was in stock'
    )

    # Pattern tracking
    pattern_version = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text='Deprecated: use extractor_version FK instead'
    )
    extractor_version = models.ForeignKey(
        'ExtractorVersion',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='listings',
        help_text='Git version used to extract this listing data'
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        unique_together = [['product', 'store', 'url']]
        indexes = [
            models.Index(fields=['product', 'store']),
            models.Index(fields=['store', 'active']),
            models.Index(fields=['url']),
            models.Index(fields=['last_checked']),
            models.Index(fields=['current_price']),
            models.Index(fields=['available']),
        ]
        verbose_name = 'Product Listing'
        verbose_name_plural = 'Product Listings'

    def __str__(self):
        return f"{self.product.name} at {self.store.name}"

    @property
    def total_price(self):
        """Calculate total price including shipping."""
        if not self.current_price:
            return None
        return self.current_price + (self.shipping_cost or 0)

    def update_price(self, price, available=True):
        """Update listing price and track availability."""
        old_price = self.current_price
        self.current_price = price
        self.available = available
        self.last_checked = timezone.now()

        if available:
            self.last_available = timezone.now()

        self.save(update_fields=[
            'current_price', 'available', 'last_checked',
            'last_available', 'updated_at'
        ])

        return old_price


class UserSubscription(models.Model):
    """
    User subscription to a product.
    Connects User + Product with user-specific preferences.
    """
    PRIORITY_CHOICES = [
        (2, 'Normal - Check every hour'),
        (1, 'Low - Check daily'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Relationships
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='subscriptions'
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='subscriptions'
    )

    # User preferences
    priority = models.IntegerField(
        choices=PRIORITY_CHOICES,
        default=2,
        db_index=True,
        help_text='User priority affects product check frequency'
    )

    # Alert settings
    target_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Alert when ANY store reaches this price'
    )
    notify_on_drop = models.BooleanField(default=True)
    notify_on_restock = models.BooleanField(default=False)
    notify_on_target = models.BooleanField(
        default=True,
        help_text='Notify when target price is reached'
    )

    # User engagement tracking
    view_count = models.IntegerField(default=0)
    last_viewed = models.DateTimeField(null=True, blank=True)

    # Subscription state
    active = models.BooleanField(default=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-last_viewed', '-created_at']
        unique_together = [['user', 'product']]
        indexes = [
            models.Index(fields=['user', 'active']),
            models.Index(fields=['product', 'active']),
            models.Index(fields=['priority', 'active']),
            models.Index(fields=['user', 'active', '-last_viewed']),
        ]
        verbose_name = 'User Subscription'
        verbose_name_plural = 'User Subscriptions'

    def __str__(self):
        priority_name = dict(self.PRIORITY_CHOICES)[self.priority]
        return f"{self.user.username} -> {self.product.name} ({priority_name})"

    def record_view(self):
        """Track that user viewed this subscription with retry logic for database locks."""
        from django.db import OperationalError, transaction
        import time

        max_retries = 3
        retry_delay = 0.1  # Start with 100ms

        for attempt in range(max_retries):
            try:
                # Use atomic transaction to prevent mid-update refresh
                with transaction.atomic():
                    # Refresh BEFORE incrementing to get latest value
                    # This prevents race condition where increment is lost
                    self.refresh_from_db()
                    self.view_count += 1
                    self.last_viewed = timezone.now()
                    self.save(update_fields=['view_count', 'last_viewed', 'updated_at'])
                return  # Success - exit retry loop
            except OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    # Retry on lock errors with exponential backoff
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    # Final attempt failed or different error - raise it
                    raise

    @property
    def best_listing(self):
        """Get the listing with the best price for this product."""
        return self.product.lowest_price_listing

    @property
    def is_target_reached(self):
        """Check if any listing has reached the target price."""
        if not self.target_price:
            return False

        best_listing = self.best_listing
        if not best_listing or not best_listing.current_price:
            return False

        return best_listing.current_price <= self.target_price


class PriceHistory(models.Model):
    """
    Historical price records for ProductListing.
    Time-series data per store listing.
    """
    id = models.BigAutoField(primary_key=True)

    # Relationship to listing (not product directly)
    listing = models.ForeignKey(
        ProductListing,
        on_delete=models.CASCADE,
        related_name='price_history'
    )

    # Price data
    price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    available = models.BooleanField(default=True)

    # Extraction metadata
    extracted_data = models.JSONField(default=dict, blank=True)
    confidence = models.FloatField(
        default=1.0,
        help_text='Extraction confidence (0.0-1.0)'
    )
    extraction_method = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text='Method used: css, xpath, jsonld, meta'
    )

    # Timestamp
    recorded_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-recorded_at']
        indexes = [
            models.Index(fields=['listing', '-recorded_at']),
            models.Index(fields=['listing', 'available', '-recorded_at']),
            models.Index(fields=['-recorded_at']),  # For time-range queries
        ]
        verbose_name = 'Price History'
        verbose_name_plural = 'Price Histories'

    def __str__(self):
        return (
            f"{self.listing.product.name} at {self.listing.store.name}: "
            f"{self.currency}{self.price} on {self.recorded_at.strftime('%Y-%m-%d %H:%M')}"
        )


class Notification(models.Model):
    """
    User notifications for price changes.
    Now references ProductListing for store-specific alerts.
    """
    NOTIFICATION_TYPES = [
        ('price_drop', 'Price Drop'),
        ('target_reached', 'Target Price Reached'),
        ('restock', 'Back in Stock'),
        ('price_spike', 'Price Increased'),
        ('new_listing', 'New Store Listing'),
    ]

    id = models.BigAutoField(primary_key=True)

    # Relationships
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    subscription = models.ForeignKey(
        UserSubscription,
        on_delete=models.CASCADE,
        related_name='notifications',
        help_text='User subscription that triggered this notification'
    )
    listing = models.ForeignKey(
        ProductListing,
        on_delete=models.CASCADE,
        related_name='notifications',
        help_text='Specific store listing for this notification'
    )

    # Notification details
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    message = models.TextField()

    # Price context
    old_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    new_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )

    # State
    read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'read', '-created_at']),
            models.Index(fields=['subscription', '-created_at']),
            models.Index(fields=['listing', '-created_at']),
        ]
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'

    def __str__(self):
        return (
            f"{self.get_notification_type_display()} for "
            f"{self.listing.product.name} at {self.listing.store.name}"
        )

    def mark_as_read(self):
        """Mark notification as read."""
        if not self.read:
            self.read = True
            self.read_at = timezone.now()
            self.save(update_fields=['read', 'read_at'])


class ExtractorVersion(models.Model):
    """
    Git version tracking for extractor modules.
    Tracks git commit hash and metadata for version control of extractors.
    """
    id = models.BigAutoField(primary_key=True)

    # Git tracking
    commit_hash = models.CharField(
        max_length=40,
        unique=True,
        db_index=True,
        help_text='Git commit SHA hash (40 characters)'
    )
    extractor_module = models.CharField(
        max_length=255,
        db_index=True,
        help_text='Python extractor module name (e.g., "generated_extractors.komplett_no")'
    )

    # Git metadata
    commit_message = models.TextField(
        blank=True,
        help_text='Git commit message'
    )
    commit_author = models.CharField(
        max_length=200,
        blank=True,
        help_text='Git commit author'
    )
    commit_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Git commit timestamp'
    )

    # Additional metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text='Additional git metadata (branch, tags, etc.)'
    )

    # Domain and store reference (moved from Pattern)
    domain = models.CharField(
        max_length=255,
        db_index=True,
        null=True,  # Temporarily nullable for migration
        blank=True,
        help_text='Domain this extractor handles (e.g., komplett.no)'
    )
    store = models.ForeignKey(
        'Store',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='extractor_versions',
        help_text='Store this extractor is for'
    )

    # Active version tracking
    is_active = models.BooleanField(
        default=False,
        db_index=True,
        help_text='Whether this version is currently deployed for this domain'
    )

    # Health metrics (moved from Pattern)
    success_rate = models.FloatField(
        default=0.0,
        help_text='Percentage of successful extractions for this version (0.0-1.0)'
    )
    total_attempts = models.IntegerField(
        default=0,
        help_text='Total extraction attempts with this version'
    )
    successful_attempts = models.IntegerField(
        default=0,
        help_text='Number of successful extraction attempts'
    )
    last_validated = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Last time this version was validated'
    )

    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text='When this version was registered in the system'
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['commit_hash']),
            models.Index(fields=['extractor_module', '-created_at']),
            models.Index(fields=['-created_at']),
            models.Index(fields=['domain', 'is_active']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['domain', 'is_active'],
                condition=models.Q(is_active=True),
                name='unique_active_version_per_domain'
            )
        ]
        verbose_name = 'Extractor Version'
        verbose_name_plural = 'Extractor Versions'

    def __str__(self):
        short_hash = self.commit_hash[:7] if self.commit_hash else 'unknown'
        module_display = self.extractor_module or 'unknown'
        if self.domain:
            return f"{self.domain} ({module_display} @ {short_hash})"
        return f"{module_display} @ {short_hash}"

    def record_attempt(self, success: bool):
        """
        Record extraction attempt and update success rate.

        Args:
            success: Whether the extraction was successful
        """
        self.total_attempts += 1
        if success:
            self.successful_attempts += 1

        self.success_rate = (
            self.successful_attempts / self.total_attempts
            if self.total_attempts > 0 else 0.0
        )

        self.save(update_fields=[
            'total_attempts',
            'successful_attempts',
            'success_rate',
        ])

    @property
    def is_healthy(self):
        """Check if this version has good success rate (>= 60%)."""
        return self.success_rate >= 0.6


class UserView(models.Model):
    """
    Track user product views for analytics.
    Now tracks subscription views instead of product views.
    """
    id = models.BigAutoField(primary_key=True)

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    subscription = models.ForeignKey(
        UserSubscription,
        on_delete=models.CASCADE,
        related_name='views'
    )
    viewed_at = models.DateTimeField(auto_now_add=True)
    duration_seconds = models.IntegerField(
        null=True,
        blank=True,
        help_text='Time spent on page'
    )

    class Meta:
        ordering = ['-viewed_at']
        indexes = [
            models.Index(fields=['user', '-viewed_at']),
            models.Index(fields=['subscription', '-viewed_at']),
        ]
        verbose_name = 'User View'
        verbose_name_plural = 'User Views'

    def __str__(self):
        return f"{self.user.username} viewed {self.subscription.product.name}"


class AdminFlag(models.Model):
    """
    Track issues requiring admin attention.
    Updated to reference Store instead of domain string.
    """
    FLAG_TYPES = [
        ('pattern_generation_failed', 'Pattern Generation Failed'),
        ('pattern_low_confidence', 'Pattern Low Confidence'),
        ('fetch_failing_repeatedly', 'Fetch Failing Repeatedly'),
        ('store_rate_limited', 'Store Rate Limited'),
        ('duplicate_products', 'Potential Duplicate Products'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('wont_fix', "Won't Fix"),
    ]

    id = models.BigAutoField(primary_key=True)

    flag_type = models.CharField(max_length=50, choices=FLAG_TYPES)
    store = models.ForeignKey(
        Store,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='flags'
    )
    domain = models.CharField(max_length=255, db_index=True)  # Keep for backward compat
    url = models.URLField(max_length=1000)
    error_message = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_flags'
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['domain', 'status']),
            models.Index(fields=['store', 'status']),
        ]
        verbose_name = 'Admin Flag'
        verbose_name_plural = 'Admin Flags'

    def __str__(self):
        return f"{self.get_flag_type_display()} - {self.domain} [{self.status}]"

    def resolve(self, user):
        """Mark flag as resolved."""
        self.status = 'resolved'
        self.resolved_at = timezone.now()
        self.resolved_by = user
        self.save(update_fields=['status', 'resolved_at', 'resolved_by', 'updated_at'])


class OperationLog(models.Model):
    """
    Unified operation logs from all services (Celery, PriceFetcher, ExtractorPatternAgent).
    Stores structured log entries for debugging and monitoring.
    """
    SERVICE_CHOICES = [
        ('celery', 'Celery Task'),
        ('fetcher', 'Price Fetcher'),
        ('extractor', 'Pattern Extractor'),
    ]

    LEVEL_CHOICES = [
        ('DEBUG', 'Debug'),
        ('INFO', 'Info'),
        ('WARNING', 'Warning'),
        ('ERROR', 'Error'),
        ('CRITICAL', 'Critical'),
    ]

    id = models.BigAutoField(primary_key=True)

    # Source tracking
    service = models.CharField(max_length=50, choices=SERVICE_CHOICES, db_index=True)
    task_id = models.CharField(
        max_length=100,
        db_index=True,
        null=True,
        blank=True,
        help_text='Celery task ID for correlation'
    )

    # Context (nullable to support logs not tied to specific products/listings)
    listing = models.ForeignKey(
        ProductListing,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='operation_logs'
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='operation_logs'
    )

    # Log entry
    level = models.CharField(max_length=10, choices=LEVEL_CHOICES, db_index=True)
    event = models.CharField(
        max_length=100,
        db_index=True,
        help_text='Structured event name (e.g., fetch_page_started, pattern_found)'
    )
    message = models.TextField(blank=True, help_text='Human-readable message')
    context = models.JSONField(
        default=dict,
        blank=True,
        help_text='Structured context data (all log fields as JSON)'
    )

    # Module info
    filename = models.CharField(
        max_length=100,
        blank=True,
        help_text='Source file (e.g., fetcher.py, storage.py)'
    )

    # Timing
    timestamp = models.DateTimeField(db_index=True)
    duration_ms = models.IntegerField(
        null=True,
        blank=True,
        help_text='Operation duration in milliseconds'
    )

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['service', '-timestamp']),
            models.Index(fields=['task_id', '-timestamp']),
            models.Index(fields=['level', '-timestamp']),
            models.Index(fields=['listing', '-timestamp']),
            models.Index(fields=['product', '-timestamp']),
            models.Index(fields=['event', '-timestamp']),
        ]
        verbose_name = 'Operation Log'
        verbose_name_plural = 'Operation Logs'

    def __str__(self):
        return f"[{self.level}] {self.service}: {self.event} at {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"


class UserFeedback(models.Model):
    """User feedback submissions."""

    STATUS_CHOICES = [
        ('new', 'New'),
        ('in_review', 'In Review'),
        ('implemented', 'Implemented'),
        ('dismissed', 'Dismissed'),
    ]

    id = models.BigAutoField(primary_key=True)

    # User and content
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='feedback_submissions', db_index=True)
    message = models.TextField(help_text='User feedback message')

    # Context capture
    page_url = models.CharField(max_length=500, help_text='URL path where feedback was submitted')
    page_title = models.CharField(max_length=200, blank=True, help_text='Page title for context')
    view_name = models.CharField(max_length=100, blank=True, help_text='Django view name if available')
    context_data = models.JSONField(default=dict, blank=True, help_text='Additional context: browser, screen size, etc.')

    # Admin workflow
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new', db_index=True)
    admin_notes = models.TextField(blank=True, help_text='Internal notes from admin review')
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_feedback')
    reviewed_at = models.DateTimeField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['-created_at']),
        ]
        verbose_name = 'User Feedback'
        verbose_name_plural = 'User Feedback'

    def __str__(self):
        return f"Feedback from {self.user.username} on {self.page_url}"


# ========== Signals ==========

from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver


