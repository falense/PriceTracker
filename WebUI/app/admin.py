"""
Django admin configuration for PriceTracker.
"""
from django.contrib import admin
from django.urls import path
from django.shortcuts import render
from django.utils.html import format_html
from django.contrib.admin.views.decorators import staff_member_required
from datetime import datetime
from .models import Product, PriceHistory, Pattern, Notification, FetchLog, UserView, AdminFlag


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
    from .admin_services import CeleryMonitorService

    stats = CeleryMonitorService.get_worker_stats()
    recent_tasks = CeleryMonitorService.get_recent_tasks(limit=50)

    context = {
        'stats': stats,
        'recent_tasks': recent_tasks,
        'now': datetime.now(),
    }
    return render(request, 'admin/partials/celery_stats.html', context)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'domain', 'current_price', 'priority', 'active', 'last_checked', 'created_at']
    list_filter = ['priority', 'active', 'domain', 'user', 'created_at']
    search_fields = ['name', 'url', 'domain', 'user__username']
    readonly_fields = ['id', 'created_at', 'updated_at', 'view_count', 'last_viewed']
    actions = ['refresh_prices', 'activate_products', 'deactivate_products']
    fieldsets = (
        ('Product Information', {
            'fields': ('id', 'user', 'url', 'domain', 'name', 'image_url')
        }),
        ('Price & Availability', {
            'fields': ('current_price', 'currency', 'available')
        }),
        ('Tracking Configuration', {
            'fields': ('priority', 'check_interval', 'active', 'last_checked')
        }),
        ('Alerts', {
            'fields': ('target_price', 'notify_on_drop', 'notify_on_restock')
        }),
        ('Analytics', {
            'fields': ('view_count', 'last_viewed')
        }),
        ('Metadata', {
            'fields': ('pattern_version', 'created_at', 'updated_at')
        }),
    )

    @admin.action(description='Refresh prices for selected products')
    def refresh_prices(self, request, queryset):
        """Trigger immediate price refresh for selected products."""
        from .tasks import fetch_product_price

        count = 0
        for product in queryset:
            try:
                task = fetch_product_price.delay(str(product.id))
                count += 1
            except Exception as e:
                self.message_user(
                    request,
                    f'Failed to queue refresh for {product.name}: {str(e)}',
                    level='error'
                )

        if count:
            self.message_user(
                request,
                f'Successfully queued {count} price refresh task(s)',
                level='success'
            )

    @admin.action(description='Activate selected products')
    def activate_products(self, request, queryset):
        """Bulk activate products."""
        updated = queryset.update(active=True)
        self.message_user(
            request,
            f'Activated {updated} product(s)',
            level='success'
        )

    @admin.action(description='Deactivate selected products')
    def deactivate_products(self, request, queryset):
        """Bulk deactivate products."""
        updated = queryset.update(active=False)
        self.message_user(
            request,
            f'Deactivated {updated} product(s)',
            level='success'
        )


@admin.register(PriceHistory)
class PriceHistoryAdmin(admin.ModelAdmin):
    list_display = ['product', 'price', 'currency', 'available', 'confidence', 'recorded_at']
    list_filter = ['available', 'recorded_at', 'currency']
    search_fields = ['product__name']
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
            'fields': ('domain',)
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
        # Handle None values
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

        # Format percentage separately before passing to format_html
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
            # Format JSON with indentation
            formatted_json = json.dumps(obj.pattern_json, indent=2, ensure_ascii=False)

            # Return formatted HTML with theme-aware styling
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
        from .tasks import generate_pattern

        regenerated = 0
        failed = []

        for pattern in queryset:
            # Get a sample product URL for this domain
            sample_product = Product.objects.filter(domain=pattern.domain).first()

            if not sample_product:
                failed.append(f"{pattern.domain} (no products found)")
                continue

            try:
                # Trigger pattern generation
                task = generate_pattern.delay(
                    url=sample_product.url,
                    domain=pattern.domain
                )

                regenerated += 1
                self.message_user(
                    request,
                    f'Queued pattern regeneration for {pattern.domain} (Task ID: {task.id})',
                    level='success'
                )
            except Exception as e:
                failed.append(f"{pattern.domain} ({str(e)})")

        # Summary message
        if regenerated:
            self.message_user(
                request,
                f'Successfully queued {regenerated} pattern regeneration task(s)',
                level='success'
            )

        if failed:
            self.message_user(
                request,
                f'Failed to queue: {", ".join(failed)}',
                level='error'
            )


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'product', 'notification_type', 'read', 'created_at']
    list_filter = ['notification_type', 'read', 'created_at']
    search_fields = ['user__username', 'product__name', 'message']
    readonly_fields = ['created_at', 'read_at']
    ordering = ['-created_at']


@admin.register(FetchLog)
class FetchLogAdmin(admin.ModelAdmin):
    list_display = ['product', 'success', 'extraction_method', 'duration_ms', 'fetched_at']
    list_filter = ['success', 'extraction_method', 'fetched_at']
    search_fields = ['product__name']
    readonly_fields = ['fetched_at']
    ordering = ['-fetched_at']

    def get_queryset(self, request):
        """Filter out logs with null fetched_at to prevent date_hierarchy errors."""
        qs = super().get_queryset(request)
        return qs.filter(fetched_at__isnull=False)


@admin.register(UserView)
class UserViewAdmin(admin.ModelAdmin):
    list_display = ['user', 'product', 'viewed_at', 'duration_seconds']
    list_filter = ['viewed_at']
    search_fields = ['user__username', 'product__name']
    readonly_fields = ['viewed_at']
    ordering = ['-viewed_at']


@admin.register(AdminFlag)
class AdminFlagAdmin(admin.ModelAdmin):
    list_display = ['flag_type', 'domain', 'status', 'created_at', 'resolved_by']
    list_filter = ['flag_type', 'status', 'created_at']
    search_fields = ['domain', 'url', 'error_message']
    readonly_fields = ['created_at', 'updated_at', 'resolved_at']
    fieldsets = (
        ('Flag Information', {
            'fields': ('flag_type', 'domain', 'url', 'error_message')
        }),
        ('Status', {
            'fields': ('status', 'resolved_by', 'resolved_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


# Note: Admin site customization is now in PriceTrackerAdminSite class above
