"""
Admin log views for PriceTracker WebUI.

Handles operation log analytics, task timelines, and health monitoring.
"""

import logging
from datetime import timedelta

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Avg, Q
from django.utils import timezone

from ...models import OperationLog

logger = logging.getLogger(__name__)


@login_required
def admin_logs(request):
    """Admin logs view - display logs sorted by task type."""
    if not request.user.is_staff:
        messages.error(request, "Access denied.")
        return redirect("dashboard")

    # Get filter parameters
    task_type = request.GET.get(
        "task", "all"
    )  # all, fetch (price fetches), pattern, celery
    status_filter = request.GET.get("status", "all")  # all, success, failed
    time_range = request.GET.get("range", "24h")  # 1h, 24h, 7d, 30d, all

    # Calculate time filter
    now = timezone.now()
    time_filters = {
        "1h": now - timedelta(hours=1),
        "24h": now - timedelta(hours=24),
        "7d": now - timedelta(days=7),
        "30d": now - timedelta(days=30),
        "all": None,
    }
    time_since = time_filters.get(time_range)

    # ========== PRICE FETCHES (from OperationLog) ==========
    fetch_logs_query = OperationLog.objects.filter(
        service='fetcher'
    ).select_related(
        "listing__product", "listing__store"
    ).order_by("-timestamp")

    if time_since:
        fetch_logs_query = fetch_logs_query.filter(timestamp__gte=time_since)

    if status_filter == "success":
        # Success = INFO level, no ERROR/CRITICAL
        fetch_logs_query = fetch_logs_query.filter(level__in=['INFO', 'DEBUG'])
    elif status_filter == "failed":
        # Failed = ERROR or CRITICAL level
        fetch_logs_query = fetch_logs_query.filter(level__in=['ERROR', 'CRITICAL'])

    # Get fetch log statistics
    fetch_stats = fetch_logs_query.aggregate(
        total=Count("id"),
        success_count=Count("id", filter=Q(level__in=['INFO', 'DEBUG'])),
        failed_count=Count("id", filter=Q(level__in=['ERROR', 'CRITICAL'])),
        avg_duration=Avg("duration_ms"),
    )

    # Calculate success rate
    if fetch_stats["total"] > 0:
        fetch_stats["success_rate"] = (
            fetch_stats["success_count"] / fetch_stats["total"]
        ) * 100
    else:
        fetch_stats["success_rate"] = 0

    # Get recent fetch logs (limit to 100 for performance)
    recent_fetch_logs = fetch_logs_query[:100] if task_type in ["all", "fetch"] else []

    # ========== PATTERN HISTORY ==========
    # PatternHistory model was removed - use ExtractorVersion for tracking

    # Get pattern history statistics
    pattern_stats = {
        "total": 0,
        "auto_generated": 0,
        "manual_edit": 0,
        "rollback": 0,
    }

    # Get recent pattern changes (now empty, since PatternHistory was removed)
    recent_pattern_changes = []

    # ========== ADMIN FLAGS ==========
    from ...models import AdminFlag

    admin_flags_query = AdminFlag.objects.select_related(
        "store", "resolved_by"
    ).order_by("-created_at")

    if time_since:
        admin_flags_query = admin_flags_query.filter(created_at__gte=time_since)

    if status_filter == "success":
        admin_flags_query = admin_flags_query.filter(status="resolved")
    elif status_filter == "failed":
        admin_flags_query = admin_flags_query.filter(status="pending")

    # Get admin flag statistics
    flag_stats = {
        "total": admin_flags_query.count(),
        "pending": admin_flags_query.filter(status="pending").count(),
        "in_progress": admin_flags_query.filter(status="in_progress").count(),
        "resolved": admin_flags_query.filter(status="resolved").count(),
    }

    # Get recent admin flags
    recent_admin_flags = admin_flags_query[:50] if task_type in ["all", "admin"] else []

    # ========== CELERY TASKS (if available) ==========
    celery_tasks = []
    celery_stats = {"total": 0, "success": 0, "failed": 0, "pending": 0}

    try:
        from django_celery_results.models import TaskResult

        celery_query = TaskResult.objects.order_by("-date_done")

        if time_since:
            celery_query = celery_query.filter(date_done__gte=time_since)

        if status_filter == "success":
            celery_query = celery_query.filter(status="SUCCESS")
        elif status_filter == "failed":
            celery_query = celery_query.filter(status="FAILURE")

        celery_stats = {
            "total": celery_query.count(),
            "success": celery_query.filter(status="SUCCESS").count(),
            "failed": celery_query.filter(status="FAILURE").count(),
            "pending": celery_query.filter(status="PENDING").count(),
        }

        celery_tasks = celery_query[:50] if task_type in ["all", "celery"] else []

    except ImportError:
        # django_celery_results not installed
        pass

    # ========== AGGREGATE STATS ==========
    total_logs = (
        fetch_stats["total"]
        + pattern_stats["total"]
        + flag_stats["total"]
        + celery_stats["total"]
    )

    context = {
        "task_type": task_type,
        "status_filter": status_filter,
        "time_range": time_range,
        "total_logs": total_logs,
        # Price fetches
        "fetch_logs": recent_fetch_logs,
        "fetch_stats": fetch_stats,
        # Pattern changes
        "pattern_changes": recent_pattern_changes,
        "pattern_stats": pattern_stats,
        # Admin flags
        "admin_flags": recent_admin_flags,
        "flag_stats": flag_stats,
        # Celery tasks
        "celery_tasks": celery_tasks,
        "celery_stats": celery_stats,
    }

    return render(request, "admin/logs.html", context)


@login_required
def operation_log_analytics(request):
    """Operation log analytics dashboard with comprehensive statistics."""
    if not request.user.is_staff:
        messages.error(request, "Access denied.")
        return redirect("dashboard")

    from ...operation_log_services import OperationLogAnalyticsService

    # Get filter parameters
    service = request.GET.get('service', None)
    time_range = request.GET.get('range', '24h')

    # Calculate time filter
    now = timezone.now()
    time_filters = {
        '1h': now - timedelta(hours=1),
        '24h': now - timedelta(hours=24),
        '7d': now - timedelta(days=7),
        '30d': now - timedelta(days=30),
        'all': None,
    }
    time_since = time_filters.get(time_range)

    # Get comprehensive statistics
    statistics = OperationLogAnalyticsService.get_statistics(
        service=service,
        time_since=time_since
    )

    # Get failure analysis
    failure_analysis = OperationLogAnalyticsService.get_failure_analysis(
        service=service,
        time_since=time_since,
        limit=20
    )

    # Get performance metrics
    performance_metrics = OperationLogAnalyticsService.get_performance_metrics(
        service=service,
        time_since=time_since
    )

    # Get timeline analysis (hourly for 24h, daily for longer)
    bucket_size = 'hour' if time_range in ['1h', '24h'] else 'day'
    timeline_analysis = OperationLogAnalyticsService.get_timeline_analysis(
        time_since=time_since,
        bucket_size=bucket_size
    )

    context = {
        'service': service,
        'time_range': time_range,
        'statistics': statistics,
        'failure_analysis': failure_analysis,
        'performance_metrics': performance_metrics,
        'timeline_analysis': timeline_analysis,
    }

    return render(request, "admin/operation_analytics.html", context)


@login_required
def task_timeline(request, task_id):
    """View detailed timeline for a specific task."""
    if not request.user.is_staff:
        messages.error(request, "Access denied.")
        return redirect("dashboard")

    from ...operation_log_services import OperationLogService

    # Get timeline for this task
    timeline = OperationLogService.get_task_timeline(task_id)

    if not timeline:
        messages.warning(request, f"No logs found for task {task_id}")
        return redirect("admin_logs")

    context = {
        'task_id': task_id,
        'timeline': timeline,
        'total_events': len(timeline),
        'total_duration_ms': timeline[-1]['elapsed_ms'] if timeline else 0,
    }

    return render(request, "admin/task_timeline.html", context)


@login_required
def operation_log_health(request):
    """Service health summary dashboard."""
    if not request.user.is_staff:
        messages.error(request, "Access denied.")
        return redirect("dashboard")

    from ...operation_log_services import OperationLogAnalyticsService

    # Get service health summary
    health_summary = OperationLogAnalyticsService.get_service_health_summary()

    context = {
        'health_summary': health_summary,
    }

    return render(request, "admin/operation_health.html", context)
