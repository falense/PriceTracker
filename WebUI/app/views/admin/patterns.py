"""
Admin pattern management views for PriceTracker WebUI.

Handles extractor pattern health monitoring and versioning.
"""

import logging

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages

logger = logging.getLogger(__name__)


@login_required
def patterns_status(request):
    """
    Extractor module health status with dual-mode display.

    Modes:
    - Overview: Display all active extractors with health metrics
    - Detail: Show version history for a specific extractor module
    """
    if not request.user.is_staff:
        messages.error(request, "Access denied.")
        return redirect("dashboard")

    from ...version_services import VersionAnalyticsService

    # Check if requesting detail view for specific module
    selected_module = request.GET.get('module')

    if selected_module:
        # DETAIL MODE: Show version history for specific module
        module_data = VersionAnalyticsService.get_module_version_history(selected_module)

        # Get list of all modules for navigation
        overview_data = VersionAnalyticsService.get_module_health_overview()
        all_modules = overview_data['modules']

        context = {
            'view_mode': 'detail',
            'module_data': module_data,
            'all_modules': all_modules,
            'selected_module': selected_module,
        }
    else:
        # OVERVIEW MODE: Show all active extractors
        overview_data = VersionAnalyticsService.get_module_health_overview()

        context = {
            'view_mode': 'overview',
            'modules': overview_data['modules'],
            'summary_stats': overview_data['summary_stats'],
        }

    return render(request, "admin/patterns.html", context)


# Note: api_regenerate_pattern is in utilities.py but is exported from admin/ for compatibility
