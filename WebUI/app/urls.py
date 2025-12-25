"""
URL configuration for PriceTracker app.
"""

from django.urls import path
from . import views
from . import addon_api

urlpatterns = [
    # Main pages
    path("", views.dashboard, name="dashboard"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("register/", views.register_view, name="register"),
    # Product management
    path("products/", views.product_list, name="product_list"),
    path("products/add/", views.add_product, name="add_product"),
    path("products/<uuid:product_id>/", views.product_detail, name="product_detail"),
    path(
        "products/<uuid:product_id>/delete/",
        views.delete_product,
        name="delete_product",
    ),
    path(
        "products/<uuid:product_id>/settings/",
        views.update_product_settings,
        name="update_product_settings",
    ),
    # Subscription management (new multi-store model)
    path(
        "subscriptions/<uuid:subscription_id>/",
        views.subscription_detail,
        name="subscription_detail",
    ),
    path(
        "subscriptions/<uuid:subscription_id>/status/",
        views.subscription_status,
        name="subscription_status",
    ),
    path(
        "subscriptions/<uuid:subscription_id>/update/",
        views.update_subscription,
        name="update_subscription",
    ),
    path(
        "subscriptions/<uuid:subscription_id>/unsubscribe/",
        views.unsubscribe,
        name="unsubscribe",
    ),
    path(
        "subscriptions/<uuid:subscription_id>/refresh/",
        views.refresh_price,
        name="refresh_price",
    ),
    # HTMX endpoints
    path("search/", views.search_product, name="search_product"),
    path("search/autocomplete/", views.search_autocomplete, name="search_autocomplete"),
    path(
        "products/<uuid:product_id>/chart/",
        views.price_history_chart,
        name="price_history_chart",
    ),
    path(
        "products/<uuid:product_id>/status/",
        views.product_status,
        name="product_status",
    ),
    # Notifications
    path("notifications/", views.notifications_list, name="notifications_list"),
    path(
        "notifications/mark-read/",
        views.mark_notifications_read,
        name="mark_notifications_read",
    ),
    # Admin pages (staff only)
    path("admin-dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("admin-dashboard/logs/", views.admin_logs, name="admin_logs"),
    path("admin-dashboard/version-analytics/", views.version_analytics, name="version_analytics"),
    path("admin-dashboard/operation-analytics/", views.operation_log_analytics, name="operation_log_analytics"),
    path("admin-dashboard/operation-health/", views.operation_log_health, name="operation_log_health"),
    path("admin-dashboard/task/<str:task_id>/", views.task_timeline, name="task_timeline"),
    # Pattern API endpoints
    path(
        "api/patterns/regenerate/",
        views.api_regenerate_pattern,
        name="api_regenerate_pattern",
    ),
    # Firefox Addon API
    path(
        "api/addon/check-tracking/",
        addon_api.addon_check_tracking,
        name="addon_check_tracking",
    ),
    path(
        "api/addon/track-product/",
        addon_api.addon_track_product,
        name="addon_track_product",
    ),
    path(
        "api/addon/untrack-product/",
        addon_api.addon_untrack_product,
        name="addon_untrack_product",
    ),
    path(
        "api/addon/csrf-token/",
        addon_api.addon_csrf_token,
        name="addon_csrf_token",
    ),
    # Admin Flags
    path("admin-dashboard/flags/", views.admin_flags_list, name="admin_flags_list"),
    path(
        "admin-dashboard/flags/<int:flag_id>/resolve/",
        views.resolve_admin_flag,
        name="resolve_admin_flag",
    ),
    # Extractor health and version history
    path(
        "admin-dashboard/patterns/", views.patterns_status, name="patterns_status"
    ),
    # Settings
    path("settings/", views.user_settings, name="user_settings"),
    path("settings/change-password/", views.change_password, name="change_password"),
    # Utilities
    path("proxy-image/", views.proxy_image, name="proxy_image"),
]
