"""
Django admin configuration for PriceTracker.
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import Product, PriceHistory, Pattern, Notification, FetchLog, UserView, AdminFlag


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'domain', 'current_price', 'priority', 'active', 'last_checked', 'created_at']
    list_filter = ['priority', 'active', 'domain', 'created_at']
    search_fields = ['name', 'url', 'domain']
    readonly_fields = ['id', 'created_at', 'updated_at', 'view_count', 'last_viewed']
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


@admin.register(PriceHistory)
class PriceHistoryAdmin(admin.ModelAdmin):
    list_display = ['product', 'price', 'currency', 'available', 'confidence', 'recorded_at']
    list_filter = ['available', 'recorded_at', 'currency']
    search_fields = ['product__name']
    readonly_fields = ['recorded_at']
    date_hierarchy = 'recorded_at'


@admin.register(Pattern)
class PatternAdmin(admin.ModelAdmin):
    list_display = ['domain', 'success_rate_display', 'total_attempts', 'last_validated', 'created_at']
    list_filter = ['created_at', 'updated_at']
    search_fields = ['domain']
    readonly_fields = ['created_at', 'updated_at']

    def success_rate_display(self, obj):
        """Display success rate with color coding."""
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

        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1%}</span> ({})',
            color, obj.success_rate, status
        )
    success_rate_display.short_description = 'Success Rate'


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'product', 'notification_type', 'read', 'created_at']
    list_filter = ['notification_type', 'read', 'created_at']
    search_fields = ['user__username', 'product__name', 'message']
    readonly_fields = ['created_at', 'read_at']
    date_hierarchy = 'created_at'


@admin.register(FetchLog)
class FetchLogAdmin(admin.ModelAdmin):
    list_display = ['product', 'success', 'extraction_method', 'duration_ms', 'fetched_at']
    list_filter = ['success', 'extraction_method', 'fetched_at']
    search_fields = ['product__name']
    readonly_fields = ['fetched_at']
    date_hierarchy = 'fetched_at'


@admin.register(UserView)
class UserViewAdmin(admin.ModelAdmin):
    list_display = ['user', 'product', 'viewed_at', 'duration_seconds']
    list_filter = ['viewed_at']
    search_fields = ['user__username', 'product__name']
    readonly_fields = ['viewed_at']
    date_hierarchy = 'viewed_at'


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


# Customize admin site header
admin.site.site_header = 'PriceTracker Admin'
admin.site.site_title = 'PriceTracker Admin'
admin.site.index_title = 'Welcome to PriceTracker Administration'
