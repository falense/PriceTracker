"""
URL configuration for PriceTracker WebUI.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from app.admin import celery_monitor_view, celery_monitor_refresh

urlpatterns = [
    path('admin/celery-monitor/', celery_monitor_view, name='celery_monitor'),
    path('admin/celery-monitor/refresh/', celery_monitor_refresh, name='celery_monitor_refresh'),
    path('admin/', admin.site.urls),
    path('', include('app.urls')),
]

# Serve static files in development
if settings.DEBUG:
    urlpatterns += staticfiles_urlpatterns()
