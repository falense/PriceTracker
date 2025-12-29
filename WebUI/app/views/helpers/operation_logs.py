"""
Operation log helpers for admin debugging views.

Consolidates duplicated operation log grouping and processing logic
that appears in subscription_detail and subscription_status views.
"""

import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


def build_operation_log_context(product, time_since, service_filter='all', limit=200):
    """
    Build operation log context for admin debugging views.

    Consolidates identical logic from:
    - subscription_detail (is_being_added case, 1h window)
    - subscription_detail (main view, 24h window)
    - subscription_status (HTMX polling case, 1h window)

    Args:
        product: Product model instance to fetch logs for
        time_since: datetime object - logs will be filtered to timestamp >= time_since
        service_filter: str - 'all', 'fetcher', 'extractor', or 'celery' (default: 'all')
        limit: int - maximum number of logs to fetch (default: 200)

    Returns:
        dict with keys:
            - job_groups: list of job summary dicts (sorted by start_time, limited to 50)
            - ungrouped_logs: list of logs without task_id
            - operation_logs: list of all fetched logs
            - log_stats: dict with total, errors, warnings, service_counts
            - service_filter: str - the service filter that was applied
    """
    # Base query: logs for this product
    base_logs_query = product.operation_logs.filter(
        timestamp__gte=time_since
    ).select_related("listing", "listing__store")

    # Calculate statistics on the FULL queryset (before applying service filter)
    # This ensures accurate counts even when a service filter is active
    total_logs_all_services = base_logs_query.count()
    error_count_all_services = base_logs_query.filter(level="ERROR").count()
    warning_count_all_services = base_logs_query.filter(level="WARNING").count()

    # Count by service (always from unfiltered query for accurate breakdown)
    service_counts = {
        "fetcher": base_logs_query.filter(service="fetcher").count(),
        "extractor": base_logs_query.filter(service="extractor").count(),
        "celery": base_logs_query.filter(service="celery").count(),
    }

    # Apply service filter for display (after stats calculation)
    if service_filter != "all":
        filtered_logs_query = base_logs_query.filter(service=service_filter)
    else:
        filtered_logs_query = base_logs_query

    # Fetch logs
    logs_list = list(filtered_logs_query.order_by("-timestamp")[:limit])

    # Group logs by task_id
    job_groups = defaultdict(list)
    ungrouped_logs = []

    try:
        for log in logs_list:
            if log.task_id:
                job_groups[log.task_id].append(log)
            else:
                ungrouped_logs.append(log)

        # Process each job group
        job_summaries = []
        level_priority = {
            "CRITICAL": 5,
            "ERROR": 4,
            "WARNING": 3,
            "INFO": 2,
            "DEBUG": 1,
        }

        for task_id, logs in job_groups.items():
            # Sort logs chronologically within job
            logs_sorted = sorted(logs, key=lambda x: x.timestamp)

            # Calculate job metadata
            start_time = logs_sorted[0].timestamp
            end_time = logs_sorted[-1].timestamp
            duration = (end_time - start_time).total_seconds()

            # Determine worst status (ERROR > WARNING > INFO > DEBUG)
            worst_level = max(
                logs, key=lambda x: level_priority.get(x.level, 0)
            ).level

            # Status for display (success/warning/error)
            if worst_level in ["CRITICAL", "ERROR"]:
                status = "error"
            elif worst_level == "WARNING":
                status = "warning"
            else:
                status = "success"

            # Count services involved
            services_involved = list(set(log.service for log in logs))

            # Extract common job-level fields from logs
            listing_id = None
            product_id = None
            store_domain = None
            url = None

            for log in logs:
                if log.context:
                    if not listing_id and log.context.get("listing_id"):
                        listing_id = log.context.get("listing_id")
                    if not product_id and log.context.get("product_id"):
                        product_id = log.context.get("product_id")
                    if not store_domain:
                        store_domain = log.context.get("store") or log.context.get("domain")
                    if not url and log.context.get("url"):
                        url = log.context.get("url")
                if listing_id and product_id and store_domain and url:
                    break

            # Format duration for display
            if duration < 1:
                duration_display = "< 1s"
            elif duration < 60:
                duration_display = f"{duration:.1f}s"
            elif duration < 3600:
                minutes = int(duration // 60)
                seconds = int(duration % 60)
                duration_display = f"{minutes}m {seconds}s"
            else:
                hours = int(duration // 3600)
                minutes = int((duration % 3600) // 60)
                duration_display = f"{hours}h {minutes}m"

            job_summaries.append({
                "task_id": task_id,
                "task_id_short": task_id[:8] if len(task_id) > 8 else task_id,
                "status": status,
                "worst_level": worst_level,
                "start_time": start_time,
                "end_time": end_time,
                "duration_seconds": duration,
                "duration_display": duration_display,
                "log_count": len(logs),
                "services": services_involved,
                "logs": logs_sorted,
                "listing_id": listing_id,
                "product_id": product_id,
                "store_domain": store_domain,
                "url": url,
            })

        # Sort jobs by start time (most recent first), limit to 50 jobs
        job_summaries.sort(key=lambda x: x["start_time"], reverse=True)
        job_summaries = job_summaries[:50]

    except Exception as e:
        # Fallback to ungrouped view on error
        logger.error(f"Error grouping operation logs: {e}", exc_info=True)
        job_summaries = []
        ungrouped_logs = logs_list

    # Return context dict
    return {
        "job_groups": job_summaries,
        "ungrouped_logs": ungrouped_logs,
        "operation_logs": logs_list,  # Keep for backward compatibility
        "log_stats": {
            "total": total_logs_all_services,  # Always show total across all services
            "errors": error_count_all_services,
            "warnings": warning_count_all_services,
            "service_counts": service_counts,
        },
        "service_filter": service_filter,
    }
