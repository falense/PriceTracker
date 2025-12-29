"""
Product views for PriceTracker WebUI.

Handles product listing, details, adding products, and product relation voting.
"""

import logging
import uuid
from decimal import Decimal, InvalidOperation

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Min, Count

from ..models import Product, ProductListing, UserSubscription
from ..services import TierLimitReached

logger = logging.getLogger(__name__)


@login_required
def product_list(request):
    """List all user subscriptions."""
    # Get user's active subscriptions
    subscriptions = (
        UserSubscription.objects.filter(user=request.user, active=True)
        .select_related("product")
        .prefetch_related("product__listings")
        .annotate(
            store_count=Count("product__listings", distinct=True),
            best_price=Min("product__listings__current_price"),
        )
        .order_by("product__name")
    )

    # TODO: Add filtering and search

    context = {"subscriptions": subscriptions}
    return render(request, "product/list.html", context)


def product_detail(request, product_id):
    """Product detail page - accessible to all."""
    product = get_object_or_404(Product, id=product_id)

    if request.user.is_authenticated:
        # Check if user has a subscription
        subscription = UserSubscription.objects.filter(
            user=request.user, product=product, active=True
        ).first()

        if subscription:
            # Redirect to subscription detail
            return redirect("subscription_detail", subscription_id=subscription.id)

    # Get all active listings for this product
    listings = ProductListing.objects.filter(
        product=product, active=True
    ).select_related("store")

    context = {
        "product": product,
        "listings": listings,
        "is_guest": not request.user.is_authenticated,
    }
    return render(request, "product/detail.html", context)


def add_product(request):
    """Add new product or subscribe to existing product."""
    if request.method == "GET":
        url = request.GET.get("url", "").strip()

        if not url:
            # Show form
            if not request.user.is_authenticated:
                return redirect("dashboard")
            return render(request, "product/add_form.html")

        # User submitted a URL to search
        if not request.user.is_authenticated:
            # For non-authenticated users, show preview with prompt to register
            context = {
                "url": url,
                "preview_mode": True,
            }
            return render(request, "product/preview.html", context)

        # Authenticated user - proceed with adding product
        try:
            from ..services import ProductService

            # Get optional parameters
            priority_str = request.GET.get("priority", "normal")
            priority_map = {"high": 3, "normal": 2, "low": 1}
            priority = priority_map.get(priority_str, 2)

            target_price = request.GET.get("target_price")

            if target_price:
                try:
                    target_price = Decimal(target_price)
                except (InvalidOperation, ValueError):
                    target_price = None

            # Use service to add product for user
            product, subscription, listing, created = (
                ProductService.add_product_for_user(
                    user=request.user,
                    url=url,
                    priority=priority,
                    target_price=target_price,
                )
            )

            if created:
                messages.success(
                    request, f"Følger nå {product.name}! Henter gjeldende pris..."
                )
            else:
                messages.info(request, f"Oppdaterte abonnement på {product.name}")

            return redirect("subscription_detail", subscription_id=subscription.id)

        except TierLimitReached as e:
            messages.error(request, str(e))
            return redirect("dashboard")
        except ValueError as e:
            messages.error(request, str(e))
            return redirect("dashboard")
        except Exception as e:
            messages.error(request, f"Kunne ikke legge til produkt: {str(e)}")
            return redirect("dashboard")

    # POST - only for authenticated users
    if not request.user.is_authenticated:
        messages.error(request, "Vennligst logg inn for å følge produkter.")
        return redirect("login")

    url = request.POST.get("url", "").strip()

    if not url:
        messages.error(request, "Vennligst oppgi en gyldig produkt-URL.")
        return redirect("dashboard")

    # Get optional parameters
    priority_str = request.POST.get("priority", "normal")
    priority_map = {"high": 3, "normal": 2, "low": 1}
    priority = priority_map.get(priority_str, 2)

    target_price = request.POST.get("target_price")

    if target_price:
        try:
            target_price = Decimal(target_price)
        except (InvalidOperation, ValueError):
            target_price = None

    # Use service to add product for user
    try:
        from ..services import ProductService

        product, subscription, listing, created = ProductService.add_product_for_user(
            user=request.user, url=url, priority=priority, target_price=target_price
        )

        if created:
            messages.success(
                request, f"Følger nå {product.name}! Henter gjeldende pris..."
            )
        else:
            messages.info(request, f"Oppdaterte abonnement på {product.name}")

        return redirect("subscription_detail", subscription_id=subscription.id)

    except TierLimitReached as e:
        messages.error(request, str(e))
        return redirect("dashboard")
    except ValueError as e:
        messages.error(request, str(e))
        return redirect("dashboard")
    except Exception as e:
        messages.error(request, f"Kunne ikke legge til produkt: {str(e)}")
        return redirect("dashboard")


@login_required
@require_http_methods(["POST", "DELETE"])
def delete_product(request, product_id):
    """Delete (deactivate) product - redirects to unsubscribe."""
    # Find user's subscription for this product
    subscription = UserSubscription.objects.filter(
        user=request.user, product_id=product_id, active=True
    ).first()

    if subscription:
        # Import here to avoid circular dependency
        from .subscriptions import unsubscribe
        return unsubscribe(request, subscription.id)
    else:
        messages.error(request, "Subscription not found")
        return redirect("dashboard")


@login_required
@require_http_methods(["POST"])
def update_product_settings(request, product_id):
    """Update product settings - redirects to update_subscription."""
    subscription = UserSubscription.objects.filter(
        user=request.user, product_id=product_id, active=True
    ).first()

    if subscription:
        # Import here to avoid circular dependency
        from .subscriptions import update_subscription
        return update_subscription(request, subscription.id)
    else:
        messages.error(request, "Subscription not found")
        return redirect("dashboard")


@login_required
@require_http_methods(["POST"])
def vote_product_relation(request, subscription_id):
    """
    HTMX endpoint: User votes on whether a suggested product is the same.

    POST params:
        - suggested_product_id: UUID of the suggested similar product
        - vote: 'same' (1), 'different' (-1), or 'dismiss' (0)
    """
    subscription = get_object_or_404(
        UserSubscription, id=subscription_id, user=request.user
    )

    suggested_product_id = request.POST.get('suggested_product_id')
    vote_str = request.POST.get('vote')

    # Validate inputs
    if not suggested_product_id or not vote_str:
        messages.error(request, "Invalid vote data")
        return redirect('subscription_detail', subscription_id=subscription_id)

    # Convert vote string to weight
    vote_map = {'same': 1, 'different': -1, 'dismiss': 0}
    weight = vote_map.get(vote_str)

    if weight is None:
        messages.error(request, "Invalid vote value")
        return redirect('subscription_detail', subscription_id=subscription_id)

    # Record vote
    try:
        from ..services import ProductRelationService

        # Convert string UUID to UUID object
        suggested_product_uuid = uuid.UUID(suggested_product_id)

        ProductRelationService.vote_on_relation(
            user=request.user,
            product_id_1=subscription.product.id,
            product_id_2=suggested_product_uuid,
            weight=weight
        )

        # HTMX: Return updated card partial
        if request.headers.get('HX-Request'):
            # If dismissed, remove card from DOM
            if weight == 0:
                return HttpResponse("")

            # Otherwise, return updated card with new vote state
            suggested_product = Product.objects.get(id=suggested_product_uuid)

            # Re-fetch similarity score
            from ..services import ProductSimilarityService
            similar_products = ProductSimilarityService.find_similar_products(
                target_product=subscription.product,
                limit=10
            )

            similarity_score = None
            for product, score in similar_products:
                if product.id == suggested_product_uuid:
                    similarity_score = score
                    break

            if similarity_score is None:
                return HttpResponse("")  # Product no longer similar

            # Get updated vote and aggregate
            user_vote = ProductRelationService.get_user_vote(
                user=request.user,
                product_id_1=subscription.product.id,
                product_id_2=suggested_product_uuid
            )

            aggregate = ProductRelationService.get_aggregate_votes(
                product_id_1=subscription.product.id,
                product_id_2=suggested_product_uuid
            )

            best_listing = suggested_product.listings.filter(active=True).order_by('current_price').first()
            user_subscription = UserSubscription.objects.filter(
                user=request.user,
                product=suggested_product,
                active=True
            ).first()

            suggestion = {
                'product': suggested_product,
                'similarity_score': similarity_score,
                'user_vote': user_vote,
                'aggregate': aggregate,
                'best_listing': best_listing,
                'user_subscription': user_subscription,
            }

            return render(request, 'product/partials/similar_product_card.html', {
                'suggestion': suggestion,
                'subscription': subscription,
            })

        messages.success(request, "Thanks for your feedback!")
        return redirect('subscription_detail', subscription_id=subscription_id)

    except Exception as e:
        logger.error(f"Vote error: {e}")
        messages.error(request, "Failed to record vote")
        return redirect('subscription_detail', subscription_id=subscription_id)


@login_required
def get_similar_products_partial(request, subscription_id):
    """
    HTMX endpoint: Get similar products suggestions for display.
    Returns HTML partial for injection.
    """
    subscription = get_object_or_404(
        UserSubscription, id=subscription_id, user=request.user
    )

    from ..services import ProductSimilarityService, ProductRelationService

    # Find similar products
    similar_products = ProductSimilarityService.find_similar_products(
        target_product=subscription.product,
        limit=5
    )

    # Enrich with user's existing votes and aggregate stats
    suggestions = []
    for product, similarity_score in similar_products:
        user_vote = ProductRelationService.get_user_vote(
            user=request.user,
            product_id_1=subscription.product.id,
            product_id_2=product.id
        )

        # Skip if user already voted (except if they want to see it)
        if user_vote == 0:  # Dismissed
            continue

        aggregate = ProductRelationService.get_aggregate_votes(
            product_id_1=subscription.product.id,
            product_id_2=product.id
        )

        # Get best price for this product
        best_listing = product.listings.filter(active=True).order_by('current_price').first()

        # Check if user has a subscription to this product
        user_subscription = UserSubscription.objects.filter(
            user=request.user,
            product=product,
            active=True
        ).first()

        suggestions.append({
            'product': product,
            'similarity_score': similarity_score,
            'user_vote': user_vote,
            'aggregate': aggregate,
            'best_listing': best_listing,
            'user_subscription': user_subscription,
        })

    context = {
        'subscription': subscription,
        'suggestions': suggestions[:4],  # Show top 4
    }

    return render(
        request,
        'product/partials/similar_products.html',
        context
    )
