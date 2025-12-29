"""
Admin products view for PriceTracker WebUI.

Shows top subscribed products and product statistics.
"""

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages


@login_required
def top_subscribed_products(request):
    """Display top 3 most subscribed products for admin use."""
    if not request.user.is_staff:
        messages.error(request, "Access denied.")
        return redirect("dashboard")

    from ...models import Product

    # Get top 3 most subscribed products
    top_products = Product.objects.all().order_by('-subscriber_count')[:3]

    context = {
        'top_products': top_products,
    }

    return render(request, "admin/top_subscribed_products.html", context)
