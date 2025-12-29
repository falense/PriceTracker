"""
Search and HTMX endpoint views for PriceTracker WebUI.

Handles product search, autocomplete, and price history chart data.
"""

import logging

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Min

from ..models import Product, ProductListing, UserSubscription

logger = logging.getLogger(__name__)


@require_http_methods(["POST"])
def search_product(request):
    """Dynamic search endpoint for products."""
    query = request.POST.get("query", "").strip()

    # Empty query - clear results
    if not query:
        return HttpResponse("")

    # Check if query is a URL
    is_url = query.startswith(("http://", "https://"))

    if is_url:
        # Query is a URL - show confirmation dialog
        if not request.user.is_authenticated:
            # Guest user - prompt to register
            context = {"url": query}
            return render(request, "search/guest_prompt.html", context)

        # Check if user already has a subscription to this URL
        existing_listing = ProductListing.objects.filter(url=query).first()

        if existing_listing:
            existing_subscription = UserSubscription.objects.filter(
                user=request.user, product=existing_listing.product, active=True
            ).first()

            if existing_subscription:
                # User already subscribed to this product
                context = {"subscription": existing_subscription}
                return render(request, "search/already_subscribed.html", context)

        # Show URL confirmation
        context = {"url": query}
        return render(request, "search/url_confirm.html", context)

    else:
        # Query is a product name - search for existing products
        if request.user.is_authenticated:
            # Authenticated user - search their subscriptions
            subscriptions = (
                UserSubscription.objects.filter(
                    user=request.user, active=True, product__name__icontains=query
                )
                .select_related("product")
                .prefetch_related("product__listings")
                .annotate(best_price=Min("product__listings__current_price"))
                .order_by("-last_viewed")[:5]
            )

            if subscriptions:
                context = {"subscriptions": subscriptions, "query": query}
                return render(request, "search/subscriptions_found.html", context)
        else:
            # Guest user - search all products in the database
            products = Product.objects.filter(name__icontains=query).prefetch_related(
                "listings"
            )[:5]

            if products:
                context = {"products": products, "query": query}
                return render(request, "search/results_found.html", context)

        # No products found
        if request.user.is_authenticated:
            # Authenticated user - prompt for URL
            context = {"query": query}
            return render(request, "search/name_not_found.html", context)
        else:
            # Guest user - prompt to register
            context = {"query": query}
            return render(request, "search/guest_prompt.html", context)


@login_required
def search_autocomplete(request):
    """Search autocomplete endpoint."""
    query = request.GET.get("q", "").strip()

    if len(query) < 3:
        return HttpResponse("")

    # Query user's active subscriptions with matching product names
    subscriptions = UserSubscription.objects.filter(
        user=request.user, active=True, product__name__icontains=query
    ).select_related("product").order_by("-last_viewed")[:5]

    # Extract unique products from subscriptions
    products = [sub.product for sub in subscriptions]

    return render(request, "search/autocomplete.html", {"products": products})


@login_required
def price_history_chart(request, product_id):
    """Price history chart data for multi-store comparison."""
    try:
        # Get product
        product = get_object_or_404(Product, id=product_id)

        # Verify user has subscription to this product
        subscription = UserSubscription.objects.filter(
            user=request.user, product=product, active=True
        ).first()

        if not subscription:
            return JsonResponse(
                {"error": "You don't have an active subscription to this product"},
                status=403
            )

        # Get all listings for this product
        listings = ProductListing.objects.filter(product=product).select_related('store')

        if not listings.exists():
            return JsonResponse({
                "labels": [],
                "datasets": [],
                "meta": {
                    "currency": "NOK",
                    "product_name": product.name,
                    "message": "No stores available for this product"
                }
            })

        # Color palette for stores (Tailwind-based)
        STORE_COLORS = [
            {"border": "#3b82f6", "bg": "rgba(59, 130, 246, 0.1)"},    # Blue
            {"border": "#ef4444", "bg": "rgba(239, 68, 68, 0.1)"},    # Red
            {"border": "#10b981", "bg": "rgba(16, 185, 129, 0.1)"},   # Green
            {"border": "#f59e0b", "bg": "rgba(245, 158, 11, 0.1)"},   # Amber
            {"border": "#8b5cf6", "bg": "rgba(139, 92, 246, 0.1)"},   # Violet
            {"border": "#ec4899", "bg": "rgba(236, 72, 153, 0.1)"},   # Pink
            {"border": "#14b8a6", "bg": "rgba(20, 184, 166, 0.1)"},   # Teal
            {"border": "#f97316", "bg": "rgba(249, 115, 22, 0.1)"},   # Orange
        ]

        # Build datasets for each store
        datasets = []
        all_timestamps = set()
        currency = "NOK"  # Default
        best_store = None
        best_price = None

        for idx, listing in enumerate(listings):
            # Get price history for this listing (last 100 records)
            price_history = listing.price_history.all().order_by('recorded_at')[:100]

            if not price_history.exists():
                continue

            # Extract data points
            data_points = []
            for history in price_history:
                timestamp = history.recorded_at.strftime("%Y-%m-%d %H:%M")
                all_timestamps.add(timestamp)
                data_points.append({
                    "x": timestamp,
                    "y": float(history.price) if history.price else None
                })
                currency = history.currency  # Update currency from data

                # Track best price
                if history.price and (best_price is None or history.price < best_price):
                    best_price = history.price
                    best_store = listing.store.name

            # Assign color (cycle through palette)
            color = STORE_COLORS[idx % len(STORE_COLORS)]

            datasets.append({
                "label": listing.store.name,
                "data": data_points,
                "borderColor": color["border"],
                "backgroundColor": color["bg"],
                "tension": 0.4,
                "storeId": str(listing.store.id),
                "fill": False,
                "pointRadius": 2,
                "pointHoverRadius": 5
            })

        # Check if we have any data
        if not datasets:
            return JsonResponse({
                "labels": [],
                "datasets": [],
                "meta": {
                    "currency": currency,
                    "product_name": product.name,
                    "message": "No price history data available yet"
                }
            })

        # Sort timestamps for labels
        labels = sorted(list(all_timestamps))

        return JsonResponse({
            "labels": labels,
            "datasets": datasets,
            "meta": {
                "currency": currency,
                "product_name": product.name,
                "best_store": best_store or "N/A",
                "best_price": float(best_price) if best_price else None
            }
        })

    except Exception as e:
        logger.error(f"Error generating chart data for product {product_id}: {str(e)}")
        return JsonResponse(
            {"error": "Failed to generate chart data"},
            status=500
        )


@login_required
def product_status(request, product_id):
    """Get product status (for polling during add)."""
    # TODO: Implement
    return HttpResponse("Status")
