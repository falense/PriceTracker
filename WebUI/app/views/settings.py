"""
User settings views for PriceTracker WebUI.

Handles user account settings and password management.
"""

import logging

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.urls import reverse

from ..models import UserSubscription, ProductListing, Notification

logger = logging.getLogger(__name__)


@login_required
def user_settings(request):
    """User settings page."""
    from ..models import ReferralCode
    from ..services import ReferralService

    # Get user statistics
    active_subscriptions = UserSubscription.objects.filter(
        user=request.user, active=True
    ).count()

    # Get total stores tracked (distinct stores across all user's subscriptions)
    stores_tracked = (
        ProductListing.objects.filter(
            product__subscriptions__user=request.user,
            product__subscriptions__active=True,
            active=True,
        )
        .values("store")
        .distinct()
        .count()
    )

    # Get unread notifications count
    unread_notifications = Notification.objects.filter(
        user=request.user, read=False
    ).count()

    # Get or create referral code
    referral_code, created = ReferralCode.objects.get_or_create(
        user=request.user,
        defaults={'code': ReferralService.generate_code()}
    )

    # Calculate progress toward next reward
    current_progress, needed_for_next = referral_code.get_next_reward_progress()

    # Get referral URL
    referral_url = request.build_absolute_uri(
        reverse('referral_landing', kwargs={'code': referral_code.code})
    )

    # Get user tier and usage information
    product_limit = request.user.get_product_limit()
    products_remaining = request.user.get_products_remaining()

    # Calculate usage percentage
    if product_limit is not None and product_limit > 0:
        usage_percentage = int((active_subscriptions / product_limit) * 100)
    else:
        usage_percentage = 0

    context = {
        "active_subscriptions": active_subscriptions,
        "stores_tracked": stores_tracked,
        "unread_notifications": unread_notifications,
        # Tier and usage information
        "user_tier": request.user.tier,
        "user_tier_display": request.user.get_tier_display(),
        "product_limit": product_limit,
        "product_limit_display": request.user.get_product_limit_display(),
        "products_remaining": products_remaining,
        "usage_percentage": usage_percentage,
        # Referral system
        "referral_code": referral_code,
        "referral_url": referral_url,
        "referral_progress": current_progress,
        "referral_needed": needed_for_next,
        "referral_rewards_earned": referral_code.get_reward_count(),
    }

    return render(request, "settings.html", context)


@login_required
@require_http_methods(["POST"])
def change_password(request):
    """Handle password change."""
    form = PasswordChangeForm(request.user, request.POST)

    if form.is_valid():
        user = form.save()
        # Update session to prevent logout
        update_session_auth_hash(request, user)
        messages.success(request, "Passordet ditt ble oppdatert!")
    else:
        # Display form errors
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, error)

    return redirect("user_settings")
