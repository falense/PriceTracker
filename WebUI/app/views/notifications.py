"""
Notification views for PriceTracker WebUI.

Handles user notification listing and management.
"""

import logging

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods

from ..models import Notification

logger = logging.getLogger(__name__)


@login_required
def notifications_list(request):
    """List user notifications."""
    notifications = Notification.objects.filter(user=request.user).order_by(
        "-created_at"
    )[:50]

    unread_count = Notification.objects.filter(user=request.user, read=False).count()

    if request.headers.get("HX-Request"):
        context = {"notifications": notifications}
        return render(request, "partials/notification_list.html", context)

    context = {
        "notifications": notifications,
        "unread_count": unread_count,
    }
    return render(request, "notifications.html", context)


@login_required
@require_http_methods(["POST"])
def mark_notifications_read(request):
    """Mark all notifications as read."""
    Notification.objects.filter(user=request.user, read=False).update(read=True)
    return redirect("notifications_list")
