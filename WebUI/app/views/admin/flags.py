"""
Admin flag management views for PriceTracker WebUI.

Handles admin flags for manual review and resolution.
"""

import logging

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

logger = logging.getLogger(__name__)


@login_required
def admin_flags_list(request):
    """List admin flags."""
    if not request.user.is_staff:
        messages.error(request, "Access denied.")
        return redirect("dashboard")

    # TODO: Implement
    return render(request, "admin/flags.html")


@login_required
@require_http_methods(["POST"])
def resolve_admin_flag(request, flag_id):
    """Resolve an admin flag."""
    if not request.user.is_staff:
        return JsonResponse({"error": "Access denied"}, status=403)

    # TODO: Implement
    return JsonResponse({"status": "resolved"})
