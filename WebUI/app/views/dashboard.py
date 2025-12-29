"""
Dashboard view for PriceTracker WebUI.

Main landing page showing user subscriptions and statistics.
"""

import logging

from django.shortcuts import render
from django.db.models import Min, Count

from ..models import UserSubscription, ProductListing, Notification

logger = logging.getLogger(__name__)


def dashboard(request):
    """Main dashboard view - accessible to everyone."""
    if request.user.is_authenticated:
        from ..services import TierService

        # Get user's active subscriptions with product and best price info
        subscriptions = (
            UserSubscription.objects.filter(user=request.user, active=True)
            .select_related("product")
            .prefetch_related("product__listings")
            .annotate(
                store_count=Count("product__listings", distinct=True),
                best_price=Min("product__listings__current_price"),
            )
            .order_by("-last_viewed", "-created_at")[:20]
        )

        notifications = Notification.objects.filter(
            subscription__user=request.user, read=False
        ).select_related("subscription", "listing")[:5]

        unread_count = notifications.count()

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

        stats = {
            "total_products": UserSubscription.objects.filter(
                user=request.user, active=True
            ).count(),
            "price_drops_24h": 0,  # TODO: Implement
            "total_saved": 0,  # TODO: Implement
            "active_alerts": UserSubscription.objects.filter(
                user=request.user, active=True, target_price__isnull=False
            ).count(),
        }

        # Get tier usage information
        tier_info = TierService.get_user_tier_info(request.user)

        context = {
            "subscriptions": subscriptions,
            "notifications": notifications,
            "unread_count": unread_count,
            "stats": stats,
            "tier_info": tier_info,
            "stores_tracked": stores_tracked,
        }
    else:
        # Non-authenticated users see the search page
        context = {
            "subscriptions": [],
            "notifications": [],
            "unread_count": 0,
            "stats": {
                "total_products": 0,
                "price_drops_24h": 0,
                "total_saved": 0,
                "active_alerts": 0,
            },
        }

    return render(request, "dashboard.html", context)
