"""
Subscription views for PriceTracker WebUI.

Handles subscription details, status updates, and price refresh.
"""

import logging
from decimal import Decimal, InvalidOperation
from datetime import timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.urls import reverse

from ..models import UserSubscription, ProductListing
from .helpers import build_operation_log_context

logger = logging.getLogger(__name__)


def subscription_detail(request, subscription_id):
    """Subscription detail page showing all store listings."""
    subscription = get_object_or_404(
        UserSubscription, id=subscription_id, user=request.user
    )

    # Record view
    subscription.record_view()

    # Check if store is being added (pattern generation + initial fetch in progress)
    from ..services import SubscriptionStatusService

    is_being_added = SubscriptionStatusService.is_being_added(subscription)

    if is_being_added:
        # Show loading state with auto-refresh
        store_name = SubscriptionStatusService.get_store_name(subscription)
        context = {
            "subscription": subscription,
            "is_being_added": True,
            "store_name": store_name,
        }

        # Admin-only: Add operation logs for debugging store setup
        if request.user.is_staff:
            # Get logs from the last hour (store setup should be recent)
            time_since = timezone.now() - timedelta(hours=1)
            service_filter = request.GET.get("service", "all")

            # Use helper to build operation log context
            log_context = build_operation_log_context(
                product=subscription.product,
                time_since=time_since,
                service_filter=service_filter,
                limit=200
            )
            context.update(log_context)

        return render(request, "product/subscription_detail.html", context)

    # Get all active listings for this product
    listings = (
        ProductListing.objects.filter(product=subscription.product, active=True)
        .select_related("store")
        .prefetch_related("price_history")
    )

    # Get price history for each listing (last 100 records)
    for listing in listings:
        listing.history_data = listing.price_history.all()[:100]

    # Find best current price
    best_listing = min(
        listings, key=lambda l: l.current_price or float("inf"), default=None
    )

    # Fetch similar products and create unified list
    from ..services import ProductSimilarityService, ProductRelationService

    similar_products = ProductSimilarityService.find_similar_products(
        target_product=subscription.product,
        limit=5
    )

    # Enrich with votes and stats
    similar_suggestions = []
    for product, similarity_score in similar_products:
        user_vote = ProductRelationService.get_user_vote(
            user=request.user,
            product_id_1=subscription.product.id,
            product_id_2=product.id
        )

        # Skip dismissed products
        if user_vote == 0:
            continue

        aggregate = ProductRelationService.get_aggregate_votes(
            product_id_1=subscription.product.id,
            product_id_2=product.id
        )

        best_listing_for_similar = product.listings.filter(active=True).order_by('current_price').first()
        user_subscription = UserSubscription.objects.filter(
            user=request.user,
            product=product,
            active=True
        ).first()

        similar_suggestions.append({
            'type': 'similar',
            'product': product,
            'similarity_score': similarity_score,
            'user_vote': user_vote,
            'aggregate': aggregate,
            'best_listing': best_listing_for_similar,
            'user_subscription': user_subscription,
            'price': best_listing_for_similar.current_price if best_listing_for_similar and best_listing_for_similar.current_price else None,
        })

    # Create unified items list
    unified_items = []

    # Add listings as unified items
    for listing in listings:
        unified_items.append({
            'type': 'listing',
            'listing': listing,
            'price': listing.current_price,
            'is_best': False,  # Will be set after sorting
        })

    # Add similar products (limit to 4)
    unified_items.extend(similar_suggestions[:4])

    # Sort by price (None prices go to end)
    unified_items.sort(key=lambda x: x['price'] if x['price'] else float('inf'))

    # Mark the first item with a price as best
    for item in unified_items:
        if item['price'] is not None:
            item['is_best'] = True
            break

    # Identify best price item
    best_item = unified_items[0] if unified_items and unified_items[0]['price'] else None

    context = {
        "subscription": subscription,
        "product": subscription.product,
        "listings": listings,
        "best_listing": best_listing,
        "unified_items": unified_items,
        "best_item": best_item,
    }

    # Admin-only: Add operation logs
    if request.user.is_staff:
        # Get time range (last 24 hours)
        time_since = timezone.now() - timedelta(hours=24)
        service_filter = request.GET.get("service", "all")

        # Use helper to build operation log context
        log_context = build_operation_log_context(
            product=subscription.product,
            time_since=time_since,
            service_filter=service_filter,
            limit=200
        )
        context.update(log_context)

    return render(request, "product/subscription_detail.html", context)


@login_required
def subscription_status(request, subscription_id):
    """
    HTMX endpoint: Check if subscription data is ready.
    Returns updated content when status changes.

    This endpoint is polled by the loading view to detect when
    the store has been added and data is available.
    """
    subscription = get_object_or_404(
        UserSubscription, id=subscription_id, user=request.user
    )

    from ..services import SubscriptionStatusService

    is_being_added = SubscriptionStatusService.is_being_added(subscription)

    if is_being_added:
        # Still loading - return loading partial
        store_name = SubscriptionStatusService.get_store_name(subscription)
        context = {
            "subscription": subscription,
            "is_being_added": True,
            "store_name": store_name,
        }

        # Admin-only: Add operation logs for debugging store setup
        if request.user.is_staff:
            # Get logs from the last hour (store setup should be recent)
            time_since = timezone.now() - timedelta(hours=1)
            service_filter = request.GET.get("service", "all")

            # Use helper to build operation log context
            log_context = build_operation_log_context(
                product=subscription.product,
                time_since=time_since,
                service_filter=service_filter,
                limit=200
            )
            context.update(log_context)

        return render(request, "product/partials/store_being_added.html", context)

    # Data is ready! Return full page content
    # This will trigger a full page refresh with complete data
    return redirect("subscription_detail", subscription_id=subscription_id)


@login_required
@require_http_methods(["POST", "DELETE"])
def unsubscribe(request, subscription_id):
    """Unsubscribe from a product."""
    subscription = get_object_or_404(
        UserSubscription, id=subscription_id, user=request.user
    )
    product_name = subscription.product.name

    subscription.active = False
    subscription.save()

    messages.success(request, f'Følger ikke lenger "{product_name}"')

    if request.headers.get("HX-Request"):
        return HttpResponse("")
    return redirect("dashboard")


@login_required
@require_http_methods(["POST"])
def update_subscription(request, subscription_id):
    """Update subscription settings."""
    subscription = get_object_or_404(
        UserSubscription, id=subscription_id, user=request.user
    )

    # Collect updated settings
    if "priority" in request.POST:
        priority_str = request.POST["priority"]
        priority_map = {"high": 3, "normal": 2, "low": 1}
        subscription.priority = priority_map.get(priority_str, 2)

    if "target_price" in request.POST:
        target_price = request.POST["target_price"].strip()
        if target_price:
            try:
                subscription.target_price = Decimal(target_price)
            except (InvalidOperation, ValueError):
                messages.error(request, "Invalid target price")
                return redirect("subscription_detail", subscription_id=subscription_id)
        else:
            subscription.target_price = None

    if "notify_on_drop" in request.POST:
        subscription.notify_on_drop = request.POST["notify_on_drop"] == "on"
    else:
        subscription.notify_on_drop = False

    if "notify_on_restock" in request.POST:
        subscription.notify_on_restock = request.POST["notify_on_restock"] == "on"
    else:
        subscription.notify_on_restock = False

    subscription.save()

    messages.success(request, "Innstillinger oppdatert")

    if request.headers.get("HX-Request"):
        # Return updated settings form for HTMX
        return render(
            request,
            "product/partials/subscription_settings_form.html",
            {"subscription": subscription},
        )

    return redirect("subscription_detail", subscription_id=subscription_id)


@login_required
@require_http_methods(["POST"])
def refresh_price(request, subscription_id):
    """Trigger immediate price refresh for all listings."""
    from app.tasks import fetch_listing_price

    subscription = get_object_or_404(
        UserSubscription, id=subscription_id, user=request.user
    )

    try:
        # Fetch all active listings for this product
        listings = ProductListing.objects.filter(
            product=subscription.product, active=True
        )

        count = 0
        for listing in listings:
            fetch_listing_price.delay(str(listing.id))
            count += 1

        messages.success(
            request,
            f"Price refresh triggered for {count} store(s)! Check back in a moment.",
        )
    except Exception as e:
        messages.error(request, f"Failed to refresh prices: {str(e)}")

    if request.headers.get("HX-Request"):
        return render(
            request,
            "product/partials/subscription_status.html",
            {"subscription": subscription},
        )

    # Add query parameter to indicate refresh was triggered
    url = reverse("subscription_detail", kwargs={"subscription_id": subscription_id})
    return redirect(f"{url}?refreshed=1")
