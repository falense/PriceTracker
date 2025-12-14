"""
Database models for PriceTracker WebUI.
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
import uuid


class Product(models.Model):
    """Tracked product model."""

    PRIORITY_CHOICES = [
        ('high', 'High - Check every 15 minutes'),
        ('normal', 'Normal - Check every hour'),
        ('low', 'Low - Check daily'),
    ]

    CHECK_INTERVALS = {
        'high': 900,      # 15 minutes
        'normal': 3600,   # 1 hour
        'low': 86400,     # 24 hours
    }

    # Primary fields
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='products')
    url = models.URLField(max_length=1000, unique=True)
    domain = models.CharField(max_length=255, db_index=True)
    name = models.CharField(max_length=500)

    # Price information
    current_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, default='USD')
    available = models.BooleanField(default=True)
    image_url = models.URLField(max_length=1000, null=True, blank=True)

    # Tracking configuration
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='normal')
    check_interval = models.IntegerField(default=3600, help_text='Check interval in seconds')
    active = models.BooleanField(default=True)
    last_checked = models.DateTimeField(null=True, blank=True)

    # User engagement
    view_count = models.IntegerField(default=0)
    last_viewed = models.DateTimeField(null=True, blank=True)

    # Alerts
    target_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Alert when price drops to or below this value'
    )
    notify_on_drop = models.BooleanField(default=True)
    notify_on_restock = models.BooleanField(default=False)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    pattern_version = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        ordering = ['-last_viewed', '-created_at']
        indexes = [
            models.Index(fields=['user', 'active']),
            models.Index(fields=['domain']),
            models.Index(fields=['last_checked']),
            models.Index(fields=['priority', 'active']),
        ]
        verbose_name = 'Product'
        verbose_name_plural = 'Products'

    def __str__(self):
        return f"{self.name} ({self.domain})"

    def save(self, *args, **kwargs):
        """Set check_interval based on priority."""
        if self.priority:
            self.check_interval = self.CHECK_INTERVALS.get(self.priority, 3600)
        super().save(*args, **kwargs)

    def record_view(self):
        """Track that user viewed this product."""
        self.view_count += 1
        self.last_viewed = timezone.now()
        self.save(update_fields=['view_count', 'last_viewed'])

    @property
    def price_change_24h(self):
        """Calculate 24h price change."""
        if not self.current_price:
            return None

        yesterday = timezone.now() - timedelta(days=1)
        old_price_record = self.price_history.filter(
            recorded_at__lte=yesterday
        ).order_by('-recorded_at').first()

        if old_price_record:
            return float(self.current_price - old_price_record.price)
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

    @property
    def is_due_for_check(self):
        """Check if product is due for price checking."""
        if not self.last_checked:
            return True
        time_since_check = (timezone.now() - self.last_checked).total_seconds()
        return time_since_check >= self.check_interval


class PriceHistory(models.Model):
    """Historical price records."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='price_history')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    available = models.BooleanField(default=True)
    extracted_data = models.JSONField(default=dict, blank=True)
    confidence = models.FloatField(default=1.0, help_text='Extraction confidence (0.0-1.0)')
    recorded_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-recorded_at']
        indexes = [
            models.Index(fields=['product', '-recorded_at']),
        ]
        verbose_name = 'Price History'
        verbose_name_plural = 'Price Histories'

    def __str__(self):
        return f"{self.product.name}: ${self.price} at {self.recorded_at.strftime('%Y-%m-%d %H:%M')}"


class Pattern(models.Model):
    """Extraction patterns per domain."""

    domain = models.CharField(max_length=255, unique=True, db_index=True)
    pattern_json = models.JSONField(help_text='Full pattern structure from ExtractorPatternAgent')

    # Success tracking
    success_rate = models.FloatField(default=0.0, help_text='Percentage of successful extractions')
    total_attempts = models.IntegerField(default=0)
    successful_attempts = models.IntegerField(default=0)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_validated = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['domain']
        verbose_name = 'Pattern'
        verbose_name_plural = 'Patterns'

    def __str__(self):
        return f"Pattern for {self.domain} ({self.success_rate:.1%} success)"

    def record_attempt(self, success: bool):
        """Record pattern usage and update success rate."""
        self.total_attempts += 1
        if success:
            self.successful_attempts += 1
        self.success_rate = self.successful_attempts / self.total_attempts if self.total_attempts > 0 else 0
        self.save(update_fields=['total_attempts', 'successful_attempts', 'success_rate'])

    @property
    def is_healthy(self):
        """Check if pattern has good success rate."""
        if self.total_attempts < 10:
            return True  # Not enough data yet
        return self.success_rate >= 0.6


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

    old_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    new_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'read', '-created_at']),
        ]
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'

    def __str__(self):
        return f"{self.get_notification_type_display()} for {self.product.name}"

    def mark_as_read(self):
        """Mark notification as read."""
        if not self.read:
            self.read = True
            self.read_at = timezone.now()
            self.save(update_fields=['read', 'read_at'])


class FetchLog(models.Model):
    """Log fetch attempts for debugging."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='fetch_logs')
    success = models.BooleanField()
    extraction_method = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text='Method used: css, xpath, jsonld, meta'
    )
    errors = models.JSONField(default=list, blank=True)
    warnings = models.JSONField(default=list, blank=True)
    duration_ms = models.IntegerField(null=True, blank=True, help_text='Fetch duration in milliseconds')
    fetched_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fetched_at']
        indexes = [
            models.Index(fields=['product', '-fetched_at']),
            models.Index(fields=['success', '-fetched_at']),
        ]
        verbose_name = 'Fetch Log'
        verbose_name_plural = 'Fetch Logs'

    def __str__(self):
        status = 'Success' if self.success else 'Failed'
        return f"{status}: {self.product.name} at {self.fetched_at.strftime('%Y-%m-%d %H:%M')}"


class UserView(models.Model):
    """Track user product views for analytics."""

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    viewed_at = models.DateTimeField(auto_now_add=True)
    duration_seconds = models.IntegerField(null=True, blank=True, help_text='Time spent on page')

    class Meta:
        ordering = ['-viewed_at']
        indexes = [
            models.Index(fields=['user', '-viewed_at']),
            models.Index(fields=['product', '-viewed_at']),
        ]
        verbose_name = 'User View'
        verbose_name_plural = 'User Views'

    def __str__(self):
        return f"{self.user.username} viewed {self.product.name}"


class AdminFlag(models.Model):
    """Track issues requiring admin attention."""

    FLAG_TYPES = [
        ('pattern_generation_failed', 'Pattern Generation Failed'),
        ('pattern_low_confidence', 'Pattern Low Confidence'),
        ('fetch_failing_repeatedly', 'Fetch Failing Repeatedly'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('wont_fix', "Won't Fix"),
    ]

    flag_type = models.CharField(max_length=50, choices=FLAG_TYPES)
    domain = models.CharField(max_length=255, db_index=True)
    url = models.URLField(max_length=1000)
    error_message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

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
