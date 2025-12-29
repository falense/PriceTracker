"""
Views package for PriceTracker WebUI.

This package modularizes the views from the original monolithic views.py file.
All views are re-exported here to maintain backward compatibility with urls.py.
"""

# Authentication views
from .auth import login_view, register_view, logout_view

# Dashboard
from .dashboard import dashboard

# Product & Subscription management
from .products import (
    product_list,
    product_detail,
    add_product,
    delete_product,
    update_product_settings,
    vote_product_relation,
    get_similar_products_partial,
)
from .subscriptions import (
    subscription_detail,
    subscription_status,
    update_subscription,
    unsubscribe,
    refresh_price,
)

# Search & HTMX endpoints
from .search import (
    search_product,
    search_autocomplete,
    price_history_chart,
    product_status,
)

# Notifications
from .notifications import (
    notifications_list,
    mark_notifications_read,
)

# User settings
from .settings import (
    user_settings,
    change_password,
)

# Referral system
from .referrals import (
    referral_landing,
    referral_settings,
)

# Utilities
from .utilities import (
    proxy_image,
    api_regenerate_pattern,
    pricing_view,
    about_view,
    submit_feedback,
)

# Admin views
from .admin import (
    admin_dashboard,
    admin_logs,
    operation_log_analytics,
    operation_log_health,
    task_timeline,
    patterns_status,
    admin_flags_list,
    resolve_admin_flag,
    admin_users_list,
    admin_update_user_tier,
    admin_user_detail,
    admin_delete_user,
)

__all__ = [
    # Authentication
    'login_view',
    'register_view',
    'logout_view',
    # Dashboard
    'dashboard',
    # Products
    'product_list',
    'product_detail',
    'add_product',
    'delete_product',
    'update_product_settings',
    'product_status',
    'vote_product_relation',
    'get_similar_products_partial',
    # Subscriptions
    'subscription_detail',
    'subscription_status',
    'update_subscription',
    'unsubscribe',
    'refresh_price',
    # Search
    'search_product',
    'search_autocomplete',
    'price_history_chart',
    # Notifications
    'notifications_list',
    'mark_notifications_read',
    # Settings
    'user_settings',
    'change_password',
    # Referrals
    'referral_landing',
    'referral_settings',
    # Utilities
    'proxy_image',
    'api_regenerate_pattern',
    'pricing_view',
    'about_view',
    'submit_feedback',
    # Admin
    'admin_dashboard',
    'admin_logs',
    'operation_log_analytics',
    'operation_log_health',
    'task_timeline',
    'patterns_status',
    'admin_flags_list',
    'resolve_admin_flag',
    'admin_users_list',
    'admin_update_user_tier',
    'admin_user_detail',
    'admin_delete_user',
]
