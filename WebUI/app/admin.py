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
    PriceHistory, Notification, UserView, AdminFlag, OperationLog,
    ExtractorVersion, UserFeedback, ProductRelation,
    ReferralCode, ReferralVisit, UserTierHistory
)


# Customize admin site
admin.site.site_header = 'Følgpris Admin'
admin.site.site_title = 'Følgpris Admin'
admin.site.index_title = 'Velkommen til Følgpris administrasjon'


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


# ========== Inline Classes ==========

class OperationLogInline(admin.TabularInline):
    """Display OperationLog entries inline on related admin pages."""
    model = OperationLog
    extra = 0
    can_delete = False
    max_num = 20
    fields = ['timestamp', 'level', 'service', 'event', 'message_short', 'task_id_short']
    readonly_fields = ['timestamp', 'level', 'service', 'event', 'message_short', 'task_id_short']
    ordering = ['-timestamp']
    
    def message_short(self, obj):
        """Truncate long messages for inline display."""
        if len(obj.message) > 80:
            return obj.message[:77] + '...'
        return obj.message
    message_short.short_description = 'Message'
    
    def task_id_short(self, obj):
        """Show shortened task ID."""
        if obj.task_id:
            return obj.task_id[:8] + '...' if len(obj.task_id) > 8 else obj.task_id
        return '-'
    task_id_short.short_description = 'Task'
    
    def has_add_permission(self, request, obj=None):
        return False


# ========== Admin Classes ==========

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'brand', 'subscriber_count', 'created_at']
    list_filter = ['brand', 'category', 'created_at']
    search_fields = ['name', 'canonical_name', 'brand', 'model_number', 'ean', 'upc', 'isbn']
    readonly_fields = ['id', 'canonical_name', 'subscriber_count', 'created_at', 'updated_at']
    actions = ['merge_products']
    inlines = [OperationLogInline]
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
        has_pattern = ExtractorVersion.objects.filter(domain=obj.domain, is_active=True).exists()
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
    inlines = [OperationLogInline]
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


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'subscription', 'listing', 'notification_type', 'read', 'created_at']
    list_filter = ['notification_type', 'read', 'created_at']
    search_fields = ['user__username', 'subscription__product__name', 'listing__store__name', 'message']
    readonly_fields = ['created_at', 'read_at']
    ordering = ['-created_at']


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


@admin.register(OperationLog)
class OperationLogAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'service', 'level', 'event', 'task_id_short', 'listing_info', 'filename']
    list_filter = ['service', 'level', 'event', 'timestamp']
    search_fields = ['event', 'message', 'task_id', 'filename', 'listing__product__name']
    readonly_fields = ['timestamp', 'service', 'task_id', 'listing', 'product', 'level', 'event', 'message', 'context', 'filename', 'duration_ms']
    date_hierarchy = 'timestamp'
    ordering = ['-timestamp']

    fieldsets = (
        ('Source', {
            'fields': ('service', 'task_id', 'filename')
        }),
        ('Context', {
            'fields': ('listing', 'product')
        }),
        ('Log Entry', {
            'fields': ('level', 'event', 'message', 'context')
        }),
        ('Timing', {
            'fields': ('timestamp', 'duration_ms')
        }),
    )

    def task_id_short(self, obj):
        """Show shortened task ID for list display."""
        if obj.task_id:
            return obj.task_id[:8] + '...' if len(obj.task_id) > 8 else obj.task_id
        return '-'
    task_id_short.short_description = 'Task ID'

    def listing_info(self, obj):
        """Show listing information if available."""
        if obj.listing:
            return f"{obj.listing.product.name} @ {obj.listing.store.name}"
        elif obj.product:
            return f"{obj.product.name}"
        return '-'
    listing_info.short_description = 'Context'

    def has_add_permission(self, request):
        """Prevent manual creation of log entries."""
        return False

    def has_change_permission(self, request, obj=None):
        """Prevent editing of log entries."""
        return False


@admin.register(ExtractorVersion)
class ExtractorVersionAdmin(admin.ModelAdmin):
    """Admin interface for ExtractorVersion - read-only like OperationLogAdmin."""

    list_display = [
        'domain',
        'module_short',
        'is_active',
        'commit_short',
        'success_rate_display',
        'total_attempts',
        'commit_author',
        'commit_date',
        'listing_count',
        'created_at'
    ]
    list_filter = ['is_active', 'extractor_module', 'domain', 'commit_date', 'created_at']
    search_fields = ['domain', 'commit_hash', 'extractor_module', 'commit_message', 'commit_author']
    readonly_fields = [
        'commit_hash',
        'extractor_module',
        'commit_message',
        'commit_author',
        'commit_date',
        'metadata',
        'domain',
        'store',
        'is_active',
        'success_rate',
        'total_attempts',
        'successful_attempts',
        'last_validated',
        'created_at',
        'formatted_metadata_display',
        'related_listings_display'
    ]
    date_hierarchy = 'created_at'
    ordering = ['-created_at']

    fieldsets = (
        ('Version Information', {
            'fields': ('extractor_module', 'commit_hash', 'created_at')
        }),
        ('Domain & Status', {
            'fields': ('domain', 'store', 'is_active')
        }),
        ('Health Metrics', {
            'fields': ('success_rate', 'total_attempts', 'successful_attempts', 'last_validated')
        }),
        ('Git Metadata', {
            'fields': ('commit_author', 'commit_date', 'commit_message')
        }),
        ('Additional Metadata', {
            'fields': ('formatted_metadata_display',),
            'classes': ('collapse',)
        }),
        ('Usage', {
            'fields': ('related_listings_display',),
            'description': 'Listings using this version'
        }),
    )

    def commit_short(self, obj):
        """Show shortened commit hash."""
        return obj.commit_hash[:8] if obj.commit_hash else '-'
    commit_short.short_description = 'Commit'

    def module_short(self, obj):
        """Show shortened module name."""
        # Extract just the domain part: "generated_extractors.komplett_no" -> "komplett_no"
        parts = obj.extractor_module.split('.')
        return parts[-1] if parts else obj.extractor_module
    module_short.short_description = 'Module'

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

    def listing_count(self, obj):
        """Count listings using this version."""
        count = obj.listings.count()
        if count > 0:
            url = f"/admin/app/productlisting/?extractor_version__id__exact={obj.id}"
            return format_html('<a href="{}">{} listings</a>', url, count)
        return '0 listings'
    listing_count.short_description = 'Listings'

    def formatted_metadata_display(self, obj):
        """Display metadata JSON formatted."""
        import json
        if not obj.metadata:
            return format_html('<em style="color: var(--body-quiet-color);">No metadata</em>')

        formatted_json = json.dumps(obj.metadata, indent=2)
        return format_html(
            '<pre style="background: var(--darkened-bg); padding: 10px; border-radius: 4px;">{}</pre>',
            formatted_json
        )
    formatted_metadata_display.short_description = 'Metadata'

    def related_listings_display(self, obj):
        """Show count of related listings."""
        count = obj.listings.count()
        if count > 0:
            url = f"/admin/app/productlisting/?extractor_version__id__exact={obj.id}"
            return format_html('<a href="{}">View {} listings</a>', url, count)
        return format_html('<em>No listings using this version</em>')
    related_listings_display.short_description = 'Related Listings'

    def has_add_permission(self, request):
        """Prevent manual creation - versions are created by VersionService."""
        return False

    def has_change_permission(self, request, obj=None):
        """Prevent editing - versions are immutable git snapshots."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Allow deletion only if not referenced by listings."""
        if obj:
            return obj.listings.count() == 0
        return True


@admin.register(UserFeedback)
class UserFeedbackAdmin(admin.ModelAdmin):
    """Admin interface for user feedback submissions."""

    list_display = ['id', 'user', 'page_url', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['user__username', 'message', 'page_url']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']

    fieldsets = (
        ('Feedback Details', {
            'fields': ('user', 'message', 'created_at')
        }),
        ('Context', {
            'fields': ('page_url', 'page_title', 'view_name', 'context_data')
        }),
        ('Admin Review', {
            'fields': ('status', 'admin_notes', 'reviewed_by', 'reviewed_at')
        }),
    )


@admin.register(ProductRelation)
class ProductRelationAdmin(admin.ModelAdmin):
    """Admin interface for product relation votes."""

    list_display = ['user', 'product_1', 'product_2', 'weight_display', 'updated_at']
    list_filter = ['weight', 'updated_at']
    search_fields = ['user__username', 'product_1__name', 'product_2__name']
    raw_id_fields = ['user', 'product_1', 'product_2']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'
    ordering = ['-updated_at']

    fieldsets = (
        ('Relation Information', {
            'fields': ('user', 'product_1', 'product_2', 'weight')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )

    def weight_display(self, obj):
        """Display vote with color coding."""
        weight_colors = {
            1: ('green', '👍 Same'),
            -1: ('red', '👎 Different'),
            0: ('gray', 'Dismissed'),
        }
        color, label = weight_colors.get(obj.weight, ('gray', 'Unknown'))
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, label
        )
    weight_display.short_description = 'Vote'


# ========== Referral System Admin ==========


@admin.register(ReferralCode)
class ReferralCodeAdmin(admin.ModelAdmin):
    """Admin interface for referral codes."""

    list_display = ['code', 'user', 'total_visits', 'unique_visits', 'conversions', 'rewards_earned', 'active', 'created_at']
    list_filter = ['active', 'created_at']
    search_fields = ['code', 'user__username', 'user__email']
    readonly_fields = ['code', 'created_at', 'total_visits', 'unique_visits', 'conversions', 'last_reward_granted_at']

    fieldsets = (
        ('Code Information', {
            'fields': ('code', 'user', 'active', 'created_at')
        }),
        ('Statistics', {
            'fields': ('total_visits', 'unique_visits', 'conversions', 'last_reward_granted_at')
        }),
    )

    def rewards_earned(self, obj):
        """Calculate rewards earned (every 3 unique visits)."""
        return obj.get_reward_count()
    rewards_earned.short_description = 'Rewards'

    def has_add_permission(self, request):
        """Prevent manual creation - codes are auto-generated."""
        return False


@admin.register(ReferralVisit)
class ReferralVisitAdmin(admin.ModelAdmin):
    """Admin interface for referral visits."""

    list_display = ['referral_code', 'visited_at', 'is_unique', 'visitor_user', 'converted_user', 'duplicate_reason_display']
    list_filter = ['is_unique', 'visited_at', 'duplicate_reason']
    search_fields = ['referral_code__code', 'visitor_user__username', 'user_agent', 'visitor_ip_hash']
    readonly_fields = ['visited_at', 'referral_code', 'visitor_cookie_id', 'visitor_ip_hash', 'visitor_user', 'is_unique', 'duplicate_reason', 'session_key', 'converted_user', 'converted_at']
    date_hierarchy = 'visited_at'
    ordering = ['-visited_at']

    fieldsets = (
        ('Visit Information', {
            'fields': ('referral_code', 'visited_at', 'is_unique', 'duplicate_reason')
        }),
        ('Visitor Identification', {
            'fields': ('visitor_user', 'visitor_cookie_id', 'visitor_ip_hash', 'visitor_fingerprint')
        }),
        ('Metadata', {
            'fields': ('user_agent', 'referer', 'landing_page', 'session_key')
        }),
        ('Conversion', {
            'fields': ('converted_user', 'converted_at')
        }),
    )

    def duplicate_reason_display(self, obj):
        """Show duplicate reason with color."""
        if obj.is_unique:
            return format_html('<span style="color: green;">✓ Unique</span>')
        else:
            reason_display = {
                'logged_in_duplicate': 'Same User',
                'cookie_duplicate': 'Same Cookie',
                'ip_duplicate': 'Same IP',
                'rate_limit_exceeded': 'Rate Limited',
            }.get(obj.duplicate_reason, obj.duplicate_reason)
            return format_html('<span style="color: orange;">⚠ {}</span>', reason_display)
    duplicate_reason_display.short_description = 'Status'

    def has_add_permission(self, request):
        """Prevent manual creation - visits are auto-tracked."""
        return False

    def has_change_permission(self, request, obj=None):
        """Prevent editing - visits are immutable."""
        return False


@admin.register(UserTierHistory)
class UserTierHistoryAdmin(admin.ModelAdmin):
    """Admin interface for tier change history."""

    list_display = ['user', 'tier_change_display', 'source_display', 'changed_at', 'changed_by']
    list_filter = ['source', 'old_tier', 'new_tier', 'changed_at']
    search_fields = ['user__username', 'notes', 'changed_by__username']
    readonly_fields = ['user', 'old_tier', 'new_tier', 'source', 'notes', 'changed_at', 'changed_by']
    date_hierarchy = 'changed_at'
    ordering = ['-changed_at']

    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Change Details', {
            'fields': ('old_tier', 'new_tier', 'source', 'notes')
        }),
        ('Metadata', {
            'fields': ('changed_at', 'changed_by')
        }),
    )

    def tier_change_display(self, obj):
        """Show tier change with arrow."""
        tier_colors = {
            'free': 'gray',
            'supporter': 'blue',
            'ultimate': 'gold'
        }
        old_color = tier_colors.get(obj.old_tier, 'gray')
        new_color = tier_colors.get(obj.new_tier, 'gray')

        return format_html(
            '<span style="color: {};">{}</span> → <span style="color: {};">{}</span>',
            old_color, obj.old_tier.title(),
            new_color, obj.new_tier.title()
        )
    tier_change_display.short_description = 'Tier Change'

    def source_display(self, obj):
        """Show source with icon."""
        source_icons = {
            'default': '🆕',
            'payment': '💳',
            'referral': '🔗',
            'admin': '👤',
            'promotion': '🎁',
            'expiration': '⏰',
        }
        icon = source_icons.get(obj.source, '❓')
        return format_html('{} {}', icon, obj.get_source_display())
    source_display.short_description = 'Source'

    def has_add_permission(self, request):
        """Prevent manual creation - history is auto-tracked."""
        return False

    def has_change_permission(self, request, obj=None):
        """Prevent editing - history is immutable."""
        return False


