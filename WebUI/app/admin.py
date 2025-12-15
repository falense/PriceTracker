"""
Django admin configuration for PriceTracker - Multi-Store Support.
"""
from django.contrib import admin
from django.urls import path
from django.shortcuts import render
from django.utils.html import format_html
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from datetime import datetime
from .models import (
    Product, Store, ProductListing, UserSubscription,
    PriceHistory, Pattern, Notification, FetchLog, UserView, AdminFlag
)


# Customize admin site
admin.site.site_header = 'PriceTracker Admin'
admin.site.site_title = 'PriceTracker Admin'
admin.site.index_title = 'Welcome to PriceTracker Administration'


# Custom admin views for Celery monitoring
@staff_member_required
def celery_monitor_view(request):
    """Main Celery monitoring page."""
    from django.contrib.admin import site
    context = {
        **site.each_context(request),
        'title': 'Celery Queue Monitor',
    }
    return render(request, 'admin/celery_monitor.html', context)


@staff_member_required
def celery_monitor_refresh(request):
    """HTMX endpoint for auto-refresh."""
    try:
        from .admin_services import CeleryMonitorService

        stats = CeleryMonitorService.get_worker_stats()
        recent_tasks = CeleryMonitorService.get_recent_tasks(limit=50)

        context = {
            'stats': stats,
            'recent_tasks': recent_tasks,
            'now': datetime.now(),
        }
        return render(request, 'admin/partials/celery_stats.html', context)
    except ImportError:
        # admin_services doesn't exist yet
        return render(request, 'admin/partials/celery_stats.html', {'stats': {}, 'recent_tasks': []})


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'brand', 'subscriber_count', 'created_at']
    list_filter = ['brand', 'category', 'created_at']
    search_fields = ['name', 'canonical_name', 'brand', 'model_number', 'ean', 'upc', 'isbn']
    readonly_fields = ['id', 'canonical_name', 'subscriber_count', 'created_at', 'updated_at']
    actions = ['merge_products']
    fieldsets = (
        ('Product Information', {
            'fields': ('id', 'name', 'canonical_name', 'brand', 'model_number', 'category', 'image_url')
        }),
        ('Product Identifiers', {
            'fields': ('ean', 'upc', 'isbn'),
            'classes': ('collapse',)
        }),
        ('Subscriptions', {
            'fields': ('subscriber_count',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at')
        }),
    )

    @admin.action(description="Merge selected products into first one")
    def merge_products(self, request, queryset):
        """Admin action to merge duplicate products."""
        products = list(queryset)
        if len(products) < 2:
            self.message_user(request, "Select at least 2 products to merge", level=messages.ERROR)
            return

        primary = products[0]

        for duplicate in products[1:]:
            # Move listings
            duplicate.listings.update(product=primary)

            # Merge subscriptions (avoid duplicates)
            for sub in duplicate.subscriptions.all():
                existing = UserSubscription.objects.filter(
                    user=sub.user, product=primary
                ).first()
                if existing:
                    # Keep highest priority
                    if sub.priority > existing.priority:
                        existing.priority = sub.priority
                        existing.save()
                    sub.delete()
                else:
                    sub.product = primary
                    sub.save()

            # Delete duplicate
            duplicate.delete()

        # Update subscriber count
        primary.subscriber_count = primary.subscriptions.filter(active=True).count()
        primary.save()

        self.message_user(
            request,
            f"Merged {len(products)-1} products into {primary.name}",
            level=messages.SUCCESS
        )


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ['name', 'domain', 'active', 'verified', 'has_pattern_display']
    list_filter = ['active', 'verified', 'country']
    search_fields = ['name', 'domain']
    readonly_fields = ['id', 'created_at', 'updated_at']
    fieldsets = (
        ('Store Information', {
            'fields': ('id', 'name', 'domain', 'country', 'currency', 'logo_url')
        }),
        ('Status', {
            'fields': ('active', 'verified')
        }),
        ('Configuration', {
            'fields': ('rate_limit_seconds',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at')
        }),
    )

    def has_pattern_display(self, obj):
        """Check if extraction pattern exists for this store."""
        has_pattern = Pattern.objects.filter(domain=obj.domain).exists()
        if has_pattern:
            return format_html('<span style="color: green;">✓</span>')
        return format_html('<span style="color: red;">✗</span>')
    has_pattern_display.short_description = 'Has Pattern'


@admin.register(ProductListing)
class ProductListingAdmin(admin.ModelAdmin):
    list_display = ['product', 'store', 'current_price', 'available', 'last_checked']
    list_filter = ['store', 'available', 'active']
    search_fields = ['product__name', 'url', 'store__name', 'store_product_id']
    readonly_fields = ['id', 'created_at', 'updated_at', 'total_price']
    actions = ['refresh_prices']
    fieldsets = (
        ('Listing Information', {
            'fields': ('id', 'product', 'store', 'url', 'store_product_id')
        }),
        ('Price & Availability', {
            'fields': ('current_price', 'currency', 'available', 'shipping_cost', 'total_price')
        }),
        ('Seller Information', {
            'fields': ('seller_name', 'seller_rating')
        }),
        ('Tracking', {
            'fields': ('active', 'last_checked', 'last_available', 'pattern_version')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at')
        }),
    )

    @admin.action(description='Refresh prices for selected listings')
    def refresh_prices(self, request, queryset):
        """Trigger immediate price refresh for selected listings."""
        try:
            from app.tasks import fetch_listing_price

            count = 0
            for listing in queryset:
                try:
                    task = fetch_listing_price.delay(str(listing.id))
                    count += 1
                except Exception as e:
                    self.message_user(
                        request,
                        f'Failed to queue refresh for {listing}: {str(e)}',
                        level=messages.ERROR
                    )

            if count:
                self.message_user(
                    request,
                    f'Successfully queued {count} price refresh task(s)',
                    level=messages.SUCCESS
                )
        except ImportError:
            self.message_user(
                request,
                'Task module not available yet',
                level=messages.WARNING
            )


@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = ['user', 'product', 'priority_display', 'target_price', 'active', 'created_at']
    list_filter = ['priority', 'active', 'notify_on_drop', 'notify_on_target', 'notify_on_restock']
    search_fields = ['user__username', 'product__name']
    readonly_fields = ['id', 'view_count', 'created_at', 'updated_at']
    actions = ['activate_subscriptions', 'deactivate_subscriptions']
    fieldsets = (
        ('Subscription Information', {
            'fields': ('id', 'user', 'product', 'active')
        }),
        ('Preferences', {
            'fields': ('priority', 'target_price')
        }),
        ('Notifications', {
            'fields': ('notify_on_drop', 'notify_on_restock', 'notify_on_target')
        }),
        ('Analytics', {
            'fields': ('view_count', 'last_viewed')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at')
        }),
    )

    def priority_display(self, obj):
        """Display priority with color coding."""
        priority_colors = {
            3: ('red', 'High'),
            2: ('orange', 'Normal'),
            1: ('gray', 'Low'),
        }
        color, label = priority_colors.get(obj.priority, ('gray', 'Unknown'))
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, label
        )
    priority_display.short_description = 'Priority'

    @admin.action(description='Activate selected subscriptions')
    def activate_subscriptions(self, request, queryset):
        """Bulk activate subscriptions."""
        updated = queryset.update(active=True)
        self.message_user(
            request,
            f'Activated {updated} subscription(s)',
            level=messages.SUCCESS
        )

    @admin.action(description='Deactivate selected subscriptions')
    def deactivate_subscriptions(self, request, queryset):
        """Bulk deactivate subscriptions."""
        updated = queryset.update(active=False)
        self.message_user(
            request,
            f'Deactivated {updated} subscription(s)',
            level=messages.SUCCESS
        )


@admin.register(PriceHistory)
class PriceHistoryAdmin(admin.ModelAdmin):
    list_display = ['listing', 'price', 'available', 'confidence', 'recorded_at']
    list_filter = ['available', 'extraction_method', 'recorded_at']
    search_fields = ['listing__product__name', 'listing__store__name']
    readonly_fields = ['recorded_at']
    ordering = ['-recorded_at']


@admin.register(Pattern)
class PatternAdmin(admin.ModelAdmin):
    list_display = ['domain', 'success_rate_display', 'total_attempts', 'last_validated', 'created_at']
    list_filter = ['created_at', 'updated_at']
    search_fields = ['domain']
    readonly_fields = ['created_at', 'updated_at', 'formatted_pattern_display', 'success_rate', 'total_attempts', 'successful_attempts']
    exclude = ['pattern_json']  # Hide raw JSON field, show formatted version instead
    actions = ['regenerate_pattern']
    fieldsets = (
        ('Domain Information', {
            'fields': ('domain', 'store')
        }),
        ('Pattern Details', {
            'fields': ('formatted_pattern_display',),
            'description': 'Extraction pattern configuration for this domain. Use the "Regenerate pattern" action to update.'
        }),
        ('Success Metrics', {
            'fields': ('success_rate', 'total_attempts', 'successful_attempts', 'last_validated')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def success_rate_display(self, obj):
        """Display success rate with color coding."""
        if obj.success_rate is None or obj.total_attempts is None:
            return format_html('<span style="color: gray;">N/A</span>')

        if obj.total_attempts < 10:
            color = 'gray'
            status = 'Not enough data'
        elif obj.success_rate >= 0.8:
            color = 'green'
            status = 'Healthy'
        elif obj.success_rate >= 0.6:
            color = 'orange'
            status = 'Warning'
        else:
            color = 'red'
            status = 'Critical'

        percentage = f'{obj.success_rate:.1%}'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span> ({})',
            color, percentage, status
        )
    success_rate_display.short_description = 'Success Rate'

    def formatted_pattern_display(self, obj):
        """Display pattern JSON in a formatted, readable way."""
        import json

        if not obj.pattern_json:
            return format_html('<em style="color: var(--body-quiet-color, #999);">No pattern data</em>')

        try:
            formatted_json = json.dumps(obj.pattern_json, indent=2, ensure_ascii=False)

            return format_html(
                '''
                <div style="background: var(--darkened-bg); border: 1px solid var(--border-color, #ddd); border-radius: 4px; padding: 15px; margin: 10px 0;">
                    <div style="margin-bottom: 10px; color: var(--body-fg);">
                        <strong>Pattern Structure:</strong>
                        <button onclick="navigator.clipboard.writeText(this.nextElementSibling.textContent); this.textContent='✓ Copied!'; setTimeout(() => this.textContent='Copy JSON', 2000);"
                                style="float: right; padding: 5px 10px; background: var(--link-fg, #447e9b); color: #fff; border: none; border-radius: 3px; cursor: pointer; font-size: 12px; transition: opacity 0.2s;"
                                onmouseover="this.style.opacity='0.8'" onmouseout="this.style.opacity='1'">
                            Copy JSON
                        </button>
                    </div>
                    <pre style="background: var(--body-bg); border: 1px solid var(--border-color, #ddd); border-radius: 3px; padding: 12px; overflow-x: auto; margin: 0; font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', 'Consolas', monospace; font-size: 13px; line-height: 1.6; color: var(--body-fg); max-height: 600px; white-space: pre-wrap; word-wrap: break-word;">{}</pre>
                </div>
                ''',
                formatted_json
            )
        except Exception as e:
            return format_html(
                '<div style="color: #c30; padding: 10px; background: rgba(204, 51, 0, 0.1); border: 1px solid #c30; border-left: 3px solid #c30; border-radius: 4px;">'
                '⚠ Error displaying pattern: {}'
                '</div>',
                str(e)
            )
    formatted_pattern_display.short_description = 'Pattern Configuration'

    @admin.action(description='Regenerate pattern for selected domains')
    def regenerate_pattern(self, request, queryset):
        """Trigger pattern regeneration for selected domains."""
        try:
            from app.tasks import generate_pattern

            regenerated = 0
            failed = []

            for pattern in queryset:
                # Get a sample listing for this domain
                sample_listing = ProductListing.objects.filter(
                    store__domain=pattern.domain
                ).first()

                if not sample_listing:
                    failed.append(f"{pattern.domain} (no listings found)")
                    continue

                try:
                    task = generate_pattern.delay(
                        url=sample_listing.url,
                        domain=pattern.domain,
                        listing_id=str(sample_listing.id)
                    )

                    regenerated += 1
                    self.message_user(
                        request,
                        f'Queued pattern regeneration for {pattern.domain} (Task ID: {task.id})',
                        level=messages.SUCCESS
                    )
                except Exception as e:
                    failed.append(f"{pattern.domain} ({str(e)})")

            if regenerated:
                self.message_user(
                    request,
                    f'Successfully queued {regenerated} pattern regeneration task(s)',
                    level=messages.SUCCESS
                )

            if failed:
                self.message_user(
                    request,
                    f'Failed to queue: {", ".join(failed)}',
                    level=messages.ERROR
                )
        except ImportError:
            self.message_user(
                request,
                'Task module not available yet',
                level=messages.WARNING
            )


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'subscription', 'listing', 'notification_type', 'read', 'created_at']
    list_filter = ['notification_type', 'read', 'created_at']
    search_fields = ['user__username', 'subscription__product__name', 'listing__store__name', 'message']
    readonly_fields = ['created_at', 'read_at']
    ordering = ['-created_at']


@admin.register(FetchLog)
class FetchLogAdmin(admin.ModelAdmin):
    list_display = ['listing', 'success', 'extraction_method', 'duration_ms', 'fetched_at']
    list_filter = ['success', 'extraction_method', 'fetched_at']
    search_fields = ['listing__product__name', 'listing__store__name']
    readonly_fields = ['fetched_at']
    ordering = ['-fetched_at']

    def get_queryset(self, request):
        """Filter out logs with null fetched_at to prevent date_hierarchy errors."""
        qs = super().get_queryset(request)
        return qs.filter(fetched_at__isnull=False)


@admin.register(UserView)
class UserViewAdmin(admin.ModelAdmin):
    list_display = ['user', 'subscription', 'viewed_at', 'duration_seconds']
    list_filter = ['viewed_at']
    search_fields = ['user__username', 'subscription__product__name']
    readonly_fields = ['viewed_at']
    ordering = ['-viewed_at']


@admin.register(AdminFlag)
class AdminFlagAdmin(admin.ModelAdmin):
    list_display = ['flag_type', 'domain', 'store', 'status', 'created_at', 'resolved_by']
    list_filter = ['flag_type', 'status', 'created_at']
    search_fields = ['domain', 'url', 'error_message', 'store__name']
    readonly_fields = ['created_at', 'updated_at', 'resolved_at']
    fieldsets = (
        ('Flag Information', {
            'fields': ('flag_type', 'domain', 'store', 'url', 'error_message')
        }),
        ('Status', {
            'fields': ('status', 'resolved_by', 'resolved_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
