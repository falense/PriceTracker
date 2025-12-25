"""
OperationLog Analytics and Reporting Services.

Provides business logic for querying, analyzing, and reporting on OperationLog data.
Includes statistics, timeline analysis, and failure reason reporting.
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from django.db.models import Count, Avg, Q, Max, Min, F
from django.utils import timezone

from .models import OperationLog, ProductListing, Product, Store

logger = logging.getLogger(__name__)


class OperationLogService:
    """Service for basic OperationLog queries and operations."""

    @staticmethod
    def get_logs(
        service: Optional[str] = None,
        level: Optional[str] = None,
        event: Optional[str] = None,
        task_id: Optional[str] = None,
        listing_id: Optional[str] = None,
        product_id: Optional[str] = None,
        time_since: Optional[datetime] = None,
        time_until: Optional[datetime] = None,
        limit: Optional[int] = 100,
    ) -> List[OperationLog]:
        """
        Get filtered OperationLog entries.

        Args:
            service: Filter by service (celery, fetcher, extractor)
            level: Filter by log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            event: Filter by event name
            task_id: Filter by task ID
            listing_id: Filter by listing UUID
            product_id: Filter by product UUID
            time_since: Filter logs after this timestamp
            time_until: Filter logs before this timestamp
            limit: Maximum number of logs to return

        Returns:
            List of OperationLog instances
        """
        query = OperationLog.objects.all()

        # Apply filters
        if service:
            query = query.filter(service=service)
        if level:
            query = query.filter(level=level)
        if event:
            query = query.filter(event=event)
        if task_id:
            query = query.filter(task_id=task_id)
        if listing_id:
            query = query.filter(listing_id=listing_id)
        if product_id:
            query = query.filter(product_id=product_id)
        if time_since:
            query = query.filter(timestamp__gte=time_since)
        if time_until:
            query = query.filter(timestamp__lte=time_until)

        # Order by timestamp (newest first) and apply limit
        query = query.select_related('listing__product', 'listing__store', 'product').order_by('-timestamp')

        if limit:
            query = query[:limit]

        return list(query)

    @staticmethod
    def get_task_timeline(task_id: str) -> List[Dict[str, Any]]:
        """
        Get chronological timeline of events for a specific task.

        Args:
            task_id: Celery task ID

        Returns:
            List of log entries with timing information
        """
        logs = OperationLog.objects.filter(
            task_id=task_id
        ).order_by('timestamp')

        if not logs.exists():
            return []

        timeline = []
        first_timestamp = logs.first().timestamp

        for log in logs:
            elapsed_ms = int((log.timestamp - first_timestamp).total_seconds() * 1000)

            timeline.append({
                'timestamp': log.timestamp,
                'elapsed_ms': elapsed_ms,
                'service': log.service,
                'level': log.level,
                'event': log.event,
                'message': log.message,
                'duration_ms': log.duration_ms,
                'context': log.context,
            })

        return timeline

    @staticmethod
    def get_events_by_service(service: str, time_since: Optional[datetime] = None) -> List[str]:
        """
        Get list of unique events for a service.

        Args:
            service: Service name
            time_since: Optional time filter

        Returns:
            List of unique event names
        """
        query = OperationLog.objects.filter(service=service)

        if time_since:
            query = query.filter(timestamp__gte=time_since)

        events = query.values_list('event', flat=True).distinct().order_by('event')
        return list(events)


class OperationLogAnalyticsService:
    """Service for OperationLog analytics and reporting."""

    @staticmethod
    def get_statistics(
        service: Optional[str] = None,
        time_since: Optional[datetime] = None,
        time_until: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get comprehensive statistics for OperationLog entries.

        Args:
            service: Filter by service (None = all services)
            time_since: Start time for analysis
            time_until: End time for analysis

        Returns:
            Dictionary with statistics
        """
        query = OperationLog.objects.all()

        # Apply filters
        if service:
            query = query.filter(service=service)
        if time_since:
            query = query.filter(timestamp__gte=time_since)
        if time_until:
            query = query.filter(timestamp__lte=time_until)

        # Get overall counts
        total_logs = query.count()

        # Count by level
        level_counts = query.values('level').annotate(
            count=Count('id')
        ).order_by('-count')

        # Count by service
        service_counts = query.values('service').annotate(
            count=Count('id')
        ).order_by('-count')

        # Count by event
        event_counts = query.values('event').annotate(
            count=Count('id')
        ).order_by('-count')[:20]  # Top 20 events

        # Calculate success/error rates
        error_count = query.filter(level__in=['ERROR', 'CRITICAL']).count()
        warning_count = query.filter(level='WARNING').count()
        success_count = query.filter(level__in=['INFO', 'DEBUG']).count()

        success_rate = (success_count / total_logs * 100) if total_logs > 0 else 0
        error_rate = (error_count / total_logs * 100) if total_logs > 0 else 0

        # Average duration (for logs that have duration_ms)
        duration_stats = query.exclude(duration_ms__isnull=True).aggregate(
            avg_duration=Avg('duration_ms'),
            max_duration=Max('duration_ms'),
            min_duration=Min('duration_ms'),
        )

        # Time range
        time_range = query.aggregate(
            first_log=Min('timestamp'),
            last_log=Max('timestamp'),
        )

        return {
            'total_logs': total_logs,
            'success_count': success_count,
            'error_count': error_count,
            'warning_count': warning_count,
            'success_rate': round(success_rate, 2),
            'error_rate': round(error_rate, 2),
            'level_distribution': list(level_counts),
            'service_distribution': list(service_counts),
            'top_events': list(event_counts),
            'duration_stats': {
                'avg_ms': round(duration_stats['avg_duration'], 2) if duration_stats['avg_duration'] else None,
                'max_ms': duration_stats['max_duration'],
                'min_ms': duration_stats['min_duration'],
            },
            'time_range': time_range,
        }

    @staticmethod
    def get_failure_analysis(
        service: Optional[str] = None,
        time_since: Optional[datetime] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """
        Analyze failures and errors from OperationLog.

        Args:
            service: Filter by service
            time_since: Start time for analysis
            limit: Number of top failures to return

        Returns:
            Dictionary with failure analysis
        """
        query = OperationLog.objects.filter(level__in=['ERROR', 'CRITICAL'])

        if service:
            query = query.filter(service=service)
        if time_since:
            query = query.filter(timestamp__gte=time_since)

        total_failures = query.count()

        # Most common error events
        top_error_events = query.values('event', 'service').annotate(
            count=Count('id')
        ).order_by('-count')[:limit]

        # Most common error messages (group by message prefix)
        error_messages = []
        for log in query.values('message', 'event', 'service').annotate(
            count=Count('id')
        ).order_by('-count')[:limit]:
            error_messages.append(log)

        # Failed listings (listings with errors)
        failed_listings = query.exclude(
            listing__isnull=True
        ).values(
            'listing__id',
            'listing__url',
            'listing__product__name',
            'listing__store__name'
        ).annotate(
            error_count=Count('id'),
            last_error=Max('timestamp')
        ).order_by('-error_count')[:limit]

        # Failed products (products with errors)
        failed_products = query.exclude(
            product__isnull=True
        ).values(
            'product__id',
            'product__name'
        ).annotate(
            error_count=Count('id'),
            last_error=Max('timestamp')
        ).order_by('-error_count')[:limit]

        # Errors by time (hourly buckets for the last 24 hours)
        if time_since and time_since > timezone.now() - timedelta(days=1):
            # Group by hour
            from django.db.models.functions import TruncHour
            error_timeline = query.annotate(
                hour=TruncHour('timestamp')
            ).values('hour').annotate(
                count=Count('id')
            ).order_by('hour')
        else:
            error_timeline = []

        return {
            'total_failures': total_failures,
            'top_error_events': list(top_error_events),
            'common_error_messages': error_messages,
            'failed_listings': list(failed_listings),
            'failed_products': list(failed_products),
            'error_timeline': list(error_timeline),
        }

    @staticmethod
    def get_timeline_analysis(
        time_since: Optional[datetime] = None,
        time_until: Optional[datetime] = None,
        bucket_size: str = 'hour',
    ) -> Dict[str, Any]:
        """
        Analyze OperationLog timeline with time-based aggregations.

        Args:
            time_since: Start time for analysis
            time_until: End time for analysis
            bucket_size: Time bucket size ('hour', 'day', 'week')

        Returns:
            Dictionary with timeline analytics
        """
        from django.db.models.functions import TruncHour, TruncDay, TruncWeek

        query = OperationLog.objects.all()

        if time_since:
            query = query.filter(timestamp__gte=time_since)
        if time_until:
            query = query.filter(timestamp__lte=time_until)

        # Choose truncation function based on bucket size
        trunc_func = {
            'hour': TruncHour,
            'day': TruncDay,
            'week': TruncWeek,
        }.get(bucket_size, TruncHour)

        # Aggregate by time buckets
        timeline = query.annotate(
            time_bucket=trunc_func('timestamp')
        ).values('time_bucket').annotate(
            total_logs=Count('id'),
            error_count=Count('id', filter=Q(level__in=['ERROR', 'CRITICAL'])),
            warning_count=Count('id', filter=Q(level='WARNING')),
            success_count=Count('id', filter=Q(level__in=['INFO', 'DEBUG'])),
            avg_duration=Avg('duration_ms', filter=Q(duration_ms__isnull=False)),
        ).order_by('time_bucket')

        # Service activity over time
        service_timeline = query.annotate(
            time_bucket=trunc_func('timestamp')
        ).values('time_bucket', 'service').annotate(
            count=Count('id')
        ).order_by('time_bucket', 'service')

        return {
            'bucket_size': bucket_size,
            'timeline': list(timeline),
            'service_timeline': list(service_timeline),
        }

    @staticmethod
    def get_performance_metrics(
        service: Optional[str] = None,
        event: Optional[str] = None,
        time_since: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get performance metrics from OperationLog duration data.

        Args:
            service: Filter by service
            event: Filter by event
            time_since: Start time for analysis

        Returns:
            Dictionary with performance metrics
        """
        query = OperationLog.objects.exclude(duration_ms__isnull=True)

        if service:
            query = query.filter(service=service)
        if event:
            query = query.filter(event=event)
        if time_since:
            query = query.filter(timestamp__gte=time_since)

        # Overall performance stats
        overall_stats = query.aggregate(
            total_operations=Count('id'),
            avg_duration=Avg('duration_ms'),
            max_duration=Max('duration_ms'),
            min_duration=Min('duration_ms'),
        )

        # Performance by event
        event_performance = query.values('event', 'service').annotate(
            count=Count('id'),
            avg_duration=Avg('duration_ms'),
            max_duration=Max('duration_ms'),
            min_duration=Min('duration_ms'),
        ).order_by('-avg_duration')[:20]

        # Slow operations (operations taking longer than 95th percentile)
        if overall_stats['total_operations'] > 0:
            # Calculate 95th percentile (approximation via ordering)
            percentile_95_index = int(overall_stats['total_operations'] * 0.95)
            slow_threshold_log = query.order_by('-duration_ms')[percentile_95_index:percentile_95_index+1].first()
            slow_threshold = slow_threshold_log.duration_ms if slow_threshold_log else None

            if slow_threshold:
                slow_operations = query.filter(
                    duration_ms__gte=slow_threshold
                ).values(
                    'event', 'service', 'duration_ms', 'timestamp'
                ).order_by('-duration_ms')[:20]
            else:
                slow_operations = []
        else:
            slow_threshold = None
            slow_operations = []

        return {
            'overall': overall_stats,
            'event_performance': list(event_performance),
            'slow_threshold_ms': slow_threshold,
            'slow_operations': list(slow_operations),
        }

    @staticmethod
    def get_service_health_summary() -> Dict[str, Any]:
        """
        Get overall health summary for all services.

        Returns:
            Dictionary with service health metrics
        """
        # Get logs from last 24 hours
        time_since = timezone.now() - timedelta(hours=24)

        services = ['celery', 'fetcher', 'extractor']
        health_summary = {}

        for service in services:
            stats = OperationLogAnalyticsService.get_statistics(
                service=service,
                time_since=time_since
            )

            # Calculate health score (simple heuristic)
            # 100% - error_rate gives a basic health score
            health_score = 100 - stats['error_rate']

            health_summary[service] = {
                'total_logs': stats['total_logs'],
                'error_count': stats['error_count'],
                'error_rate': stats['error_rate'],
                'success_rate': stats['success_rate'],
                'health_score': round(health_score, 2),
                'avg_duration_ms': stats['duration_stats']['avg_ms'],
                'status': 'healthy' if health_score >= 90 else 'degraded' if health_score >= 70 else 'unhealthy',
            }

        return {
            'timestamp': timezone.now(),
            'period_hours': 24,
            'services': health_summary,
        }
