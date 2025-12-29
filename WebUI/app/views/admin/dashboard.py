"""
Admin dashboard view for PriceTracker WebUI.

System overview, extractor health, and monitoring.
"""

import logging

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages

logger = logging.getLogger(__name__)


@login_required
def admin_dashboard(request):
    """Admin dashboard with extractor management and system monitoring."""
    if not request.user.is_staff:
        messages.error(request, "Access denied.")
        return redirect("dashboard")

    from ...models import ExtractorVersion

    # Get recent version activity
    recent_versions = ExtractorVersion.objects.all().order_by('-created_at')[:5]

    # PatternHistory was removed - use ExtractorVersion for change tracking
    recent_pattern_changes = []

    # Get extractor version health stats (active versions only)
    active_versions = ExtractorVersion.objects.filter(is_active=True)
    total = active_versions.count()
    healthy = active_versions.filter(success_rate__gte=0.8).count()
    warning = active_versions.filter(success_rate__gte=0.6, success_rate__lt=0.8).count()
    failing = active_versions.filter(success_rate__lt=0.6).count()
    pending = active_versions.filter(total_attempts=0).count()

    pattern_stats = {
        "total": total,
        "healthy": healthy,
        "warning": warning,
        "failing": failing,
        "pending": pending,
    }

    # Celery stats (if available)
    try:
        from ...admin_services import CeleryMonitorService
        celery_stats = CeleryMonitorService.get_worker_stats()
    except Exception:
        celery_stats = None

    # OperationLog health summary
    try:
        from ...operation_log_services import OperationLogAnalyticsService
        operation_health = OperationLogAnalyticsService.get_service_health_summary()
    except Exception as e:
        logger.warning(f"Error getting operation log health: {e}")
        operation_health = None

    context = {
        'recent_versions': recent_versions,
        'recent_pattern_changes': recent_pattern_changes,
        'pattern_stats': pattern_stats,
        'celery_stats': celery_stats,
        'operation_health': operation_health,
    }

    return render(request, "admin/dashboard.html", context)
