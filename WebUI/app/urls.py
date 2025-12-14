"""
URL configuration for PriceTracker app.
"""
from django.urls import path
from . import views

urlpatterns = [
    # Main pages
    path('', views.dashboard, name='dashboard'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),

    # Product management
    path('products/', views.product_list, name='product_list'),
    path('products/add/', views.add_product, name='add_product'),
    path('products/<uuid:product_id>/', views.product_detail, name='product_detail'),
    path('products/<uuid:product_id>/delete/', views.delete_product, name='delete_product'),
    path('products/<uuid:product_id>/settings/', views.update_product_settings, name='update_product_settings'),
    path('products/<uuid:product_id>/refresh/', views.refresh_price, name='refresh_price'),

    # HTMX endpoints
    path('search/', views.search_product, name='search_product'),
    path('search/autocomplete/', views.search_autocomplete, name='search_autocomplete'),
    path('products/<uuid:product_id>/chart/', views.price_history_chart, name='price_history_chart'),
    path('products/<uuid:product_id>/status/', views.product_status, name='product_status'),

    # Notifications
    path('notifications/', views.notifications_list, name='notifications_list'),
    path('notifications/mark-read/', views.mark_notifications_read, name='mark_notifications_read'),

    # Admin pages (staff only)
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-dashboard/patterns/', views.patterns_status, name='patterns_status'),
    path('admin-dashboard/flags/', views.admin_flags_list, name='admin_flags_list'),
    path('admin-dashboard/flags/<int:flag_id>/resolve/', views.resolve_admin_flag, name='resolve_admin_flag'),

    # Settings
    path('settings/', views.user_settings, name='user_settings'),
]
