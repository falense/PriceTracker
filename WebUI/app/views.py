"""
Views for PriceTracker WebUI.
"""

import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Min, Count, Avg, Q
from .models import (
    Product,
    ProductListing,
    UserSubscription,
    Notification,
    OperationLog,
)
from .services import TierLimitReached

logger = logging.getLogger(__name__)


# Authentication views
def login_view(request):
    """User login view."""
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get("username")
            password = form.cleaned_data.get("password")
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f"Velkommen tilbake, {username}!")
                return redirect("dashboard")
        else:
            messages.error(request, "Ugyldig brukernavn eller passord.")
    else:
        form = AuthenticationForm()

    return render(request, "auth/login.html", {"form": form})


def register_view(request):
    """User registration view."""
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Konto opprettet!")
            return redirect("dashboard")
        else:
            messages.error(request, "Vennligst korriger feilene nedenfor.")
    else:
        form = UserCreationForm()

    return render(request, "auth/register.html", {"form": form})


def logout_view(request):
    """User logout view."""
    logout(request)
    messages.info(request, "Du er logget ut.")
    return redirect("login")


# Main views
def dashboard(request):
    """Main dashboard view - accessible to everyone."""
    if request.user.is_authenticated:
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

        context = {
            "subscriptions": subscriptions,
            "notifications": notifications,
            "unread_count": unread_count,
            "stats": stats,
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


def subscription_detail(request, subscription_id):
    """Subscription detail page showing all store listings."""
    subscription = get_object_or_404(
        UserSubscription, id=subscription_id, user=request.user
    )

    # Record view
    subscription.record_view()

    # Check if store is being added (pattern generation + initial fetch in progress)
    from .services import SubscriptionStatusService

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
            from django.utils import timezone
            from datetime import timedelta
            from collections import defaultdict

            # Get logs from the last hour (store setup should be recent)
            time_since = timezone.now() - timedelta(hours=1)

            # Get service filter from query params
            service_filter = request.GET.get("service", "all")

            # Base query: logs for this product
            base_logs_query = subscription.product.operation_logs.filter(
                timestamp__gte=time_since
            ).select_related("listing", "listing__store")

            # Calculate statistics
            total_logs_all_services = base_logs_query.count()
            error_count_all_services = base_logs_query.filter(level="ERROR").count()
            warning_count_all_services = base_logs_query.filter(level="WARNING").count()

            # Count by service
            service_counts = {
                "fetcher": base_logs_query.filter(service="fetcher").count(),
                "extractor": base_logs_query.filter(service="extractor").count(),
                "celery": base_logs_query.filter(service="celery").count(),
            }

            # Apply service filter
            if service_filter != "all":
                filtered_logs_query = base_logs_query.filter(service=service_filter)
            else:
                filtered_logs_query = base_logs_query

            # Fetch logs (limit 200)
            logs_list = list(filtered_logs_query.order_by("-timestamp")[:200])

            # Group logs by task_id
            job_groups = defaultdict(list)
            ungrouped_logs = []

            try:
                for log in logs_list:
                    if log.task_id:
                        job_groups[log.task_id].append(log)
                    else:
                        ungrouped_logs.append(log)

                # Process job groups (same logic as full view)
                job_summaries = []
                level_priority = {
                    "CRITICAL": 5, "ERROR": 4, "WARNING": 3, "INFO": 2, "DEBUG": 1,
                }

                for task_id, logs in job_groups.items():
                    logs_sorted = sorted(logs, key=lambda x: x.timestamp)
                    start_time = logs_sorted[0].timestamp
                    end_time = logs_sorted[-1].timestamp
                    duration = (end_time - start_time).total_seconds()

                    worst_level = max(logs, key=lambda x: level_priority.get(x.level, 0)).level
                    status = "error" if worst_level in ["CRITICAL", "ERROR"] else "warning" if worst_level == "WARNING" else "success"

                    services_involved = list(set(log.service for log in logs))

                    # Extract job-level fields
                    listing_id = product_id = store_domain = url = None
                    for log in logs:
                        if log.context:
                            if not listing_id: listing_id = log.context.get("listing_id")
                            if not product_id: product_id = log.context.get("product_id")
                            if not store_domain: store_domain = log.context.get("store") or log.context.get("domain")
                            if not url: url = log.context.get("url")
                        if listing_id and product_id and store_domain and url:
                            break

                    # Format duration
                    if duration < 1:
                        duration_display = "< 1s"
                    elif duration < 60:
                        duration_display = f"{duration:.1f}s"
                    elif duration < 3600:
                        duration_display = f"{int(duration // 60)}m {int(duration % 60)}s"
                    else:
                        duration_display = f"{int(duration // 3600)}h {int((duration % 3600) // 60)}m"

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

                job_summaries.sort(key=lambda x: x["start_time"], reverse=True)
                job_summaries = job_summaries[:50]

            except Exception as e:
                logger.error(f"Error grouping operation logs: {e}", exc_info=True)
                job_summaries = []
                ungrouped_logs = logs_list

            context.update({
                "job_groups": job_summaries,
                "ungrouped_logs": ungrouped_logs,
                "operation_logs": logs_list,
                "log_stats": {
                    "total": total_logs_all_services,
                    "errors": error_count_all_services,
                    "warnings": warning_count_all_services,
                    "service_counts": service_counts,
                },
                "service_filter": service_filter,
            })

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
    from .services import ProductSimilarityService, ProductRelationService

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
        from django.utils import timezone
        from datetime import timedelta

        # Get time range (last 24 hours)
        time_since = timezone.now() - timedelta(hours=24)

        # Get service filter from query params
        service_filter = request.GET.get("service", "all")

        # Base query: logs for this product in last 24 hours (unfiltered)
        base_logs_query = subscription.product.operation_logs.filter(
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

        # Fetch logs (increase limit to 200 for better grouping coverage)
        logs_list = list(filtered_logs_query.order_by("-timestamp")[:200])

        # Group logs by task_id
        from collections import defaultdict

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
                            store_domain = log.context.get("store") or log.context.get(
                                "domain"
                            )
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

                job_summaries.append(
                    {
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
                    }
                )

            # Sort jobs by start time (most recent first), limit to 50 jobs
            job_summaries.sort(key=lambda x: x["start_time"], reverse=True)
            job_summaries = job_summaries[:50]

        except Exception as e:
            # Fallback to ungrouped view on error
            logger.error(f"Error grouping operation logs: {e}", exc_info=True)
            job_summaries = []
            ungrouped_logs = logs_list

        # Add to context
        context.update(
            {
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
        )

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

    from .services import SubscriptionStatusService

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
            from django.utils import timezone
            from datetime import timedelta
            from collections import defaultdict

            # Get logs from the last hour (store setup should be recent)
            time_since = timezone.now() - timedelta(hours=1)

            # Get service filter from query params
            service_filter = request.GET.get("service", "all")

            # Base query: logs for this product
            base_logs_query = subscription.product.operation_logs.filter(
                timestamp__gte=time_since
            ).select_related("listing", "listing__store")

            # Calculate statistics
            total_logs_all_services = base_logs_query.count()
            error_count_all_services = base_logs_query.filter(level="ERROR").count()
            warning_count_all_services = base_logs_query.filter(level="WARNING").count()

            # Count by service
            service_counts = {
                "fetcher": base_logs_query.filter(service="fetcher").count(),
                "extractor": base_logs_query.filter(service="extractor").count(),
                "celery": base_logs_query.filter(service="celery").count(),
            }

            # Apply service filter
            if service_filter != "all":
                filtered_logs_query = base_logs_query.filter(service=service_filter)
            else:
                filtered_logs_query = base_logs_query

            # Fetch logs (limit 200)
            logs_list = list(filtered_logs_query.order_by("-timestamp")[:200])

            # Group logs by task_id
            job_groups = defaultdict(list)
            ungrouped_logs = []

            try:
                for log in logs_list:
                    if log.task_id:
                        job_groups[log.task_id].append(log)
                    else:
                        ungrouped_logs.append(log)

                # Process job groups
                job_summaries = []
                level_priority = {
                    "CRITICAL": 5, "ERROR": 4, "WARNING": 3, "INFO": 2, "DEBUG": 1,
                }

                for task_id, logs in job_groups.items():
                    logs_sorted = sorted(logs, key=lambda x: x.timestamp)
                    start_time = logs_sorted[0].timestamp
                    end_time = logs_sorted[-1].timestamp
                    duration = (end_time - start_time).total_seconds()

                    worst_level = max(logs, key=lambda x: level_priority.get(x.level, 0)).level
                    status = "error" if worst_level in ["CRITICAL", "ERROR"] else "warning" if worst_level == "WARNING" else "success"

                    services_involved = list(set(log.service for log in logs))

                    # Extract job-level fields
                    listing_id = product_id = store_domain = url = None
                    for log in logs:
                        if log.context:
                            if not listing_id: listing_id = log.context.get("listing_id")
                            if not product_id: product_id = log.context.get("product_id")
                            if not store_domain: store_domain = log.context.get("store") or log.context.get("domain")
                            if not url: url = log.context.get("url")
                        if listing_id and product_id and store_domain and url:
                            break

                    # Format duration
                    if duration < 1:
                        duration_display = "< 1s"
                    elif duration < 60:
                        duration_display = f"{duration:.1f}s"
                    elif duration < 3600:
                        duration_display = f"{int(duration // 60)}m {int(duration % 60)}s"
                    else:
                        duration_display = f"{int(duration // 3600)}h {int((duration % 3600) // 60)}m"

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

                job_summaries.sort(key=lambda x: x["start_time"], reverse=True)
                job_summaries = job_summaries[:50]

            except Exception as e:
                logger.error(f"Error grouping operation logs: {e}", exc_info=True)
                job_summaries = []
                ungrouped_logs = logs_list

            context.update({
                "job_groups": job_summaries,
                "ungrouped_logs": ungrouped_logs,
                "operation_logs": logs_list,
                "log_stats": {
                    "total": total_logs_all_services,
                    "errors": error_count_all_services,
                    "warnings": warning_count_all_services,
                    "service_counts": service_counts,
                },
                "service_filter": service_filter,
            })

        return render(request, "product/partials/store_being_added.html", context)

    # Data is ready! Return full page content
    # This will trigger a full page refresh with complete data
    return redirect("subscription_detail", subscription_id=subscription_id)


# Keep old product_detail for backward compatibility / guest access
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
            from .services import ProductService

            # Get optional parameters
            priority_str = request.GET.get("priority", "normal")
            priority_map = {"high": 3, "normal": 2, "low": 1}
            priority = priority_map.get(priority_str, 2)

            target_price = request.GET.get("target_price")

            if target_price:
                from decimal import Decimal, InvalidOperation

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
        from decimal import Decimal, InvalidOperation

        try:
            target_price = Decimal(target_price)
        except (InvalidOperation, ValueError):
            target_price = None

    # Use service to add product for user
    try:
        from .services import ProductService

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


# Keep old delete_product for backward compatibility
@login_required
@require_http_methods(["POST", "DELETE"])
def delete_product(request, product_id):
    """Delete (deactivate) product - redirects to unsubscribe."""
    # Find user's subscription for this product
    subscription = UserSubscription.objects.filter(
        user=request.user, product_id=product_id, active=True
    ).first()

    if subscription:
        return unsubscribe(request, subscription.id)
    else:
        messages.error(request, "Subscription not found")
        return redirect("dashboard")


@login_required
@require_http_methods(["POST"])
def update_subscription(request, subscription_id):
    """Update subscription settings."""
    from decimal import Decimal, InvalidOperation

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


# Keep old update_product_settings for backward compatibility
@login_required
@require_http_methods(["POST"])
def update_product_settings(request, product_id):
    """Update product settings - redirects to update_subscription."""
    subscription = UserSubscription.objects.filter(
        user=request.user, product_id=product_id, active=True
    ).first()

    if subscription:
        return update_subscription(request, subscription.id)
    else:
        messages.error(request, "Subscription not found")
        return redirect("dashboard")


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
    from django.urls import reverse
    url = reverse("subscription_detail", kwargs={"subscription_id": subscription_id})
    return redirect(f"{url}?refreshed=1")


# HTMX endpoints
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


# Notifications
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


# Admin views
@login_required
def admin_dashboard(request):
    """Admin dashboard with extractor management and system monitoring."""
    if not request.user.is_staff:
        messages.error(request, "Access denied.")
        return redirect("dashboard")

    from .models import ExtractorVersion

    # Get recent version activity
    recent_versions = ExtractorVersion.objects.all().order_by('-created_at')[:5]

    # PatternHistory was removed - use ExtractorVersion for change tracking
    recent_pattern_changes = []

    # Get extractor version health stats (active versions only)
    active_versions = ExtractorVersion.objects.filter(is_active=True)
    total = active_versions.count()
    healthy = active_versions.filter(success_rate__gte=0.8).count()
    warning = active_versions.filter(success_rate__gte=0.6, success_rate__lt=0.8).count()
    failing = active_versions.filter(success_rate__lt=0.6).count()
    pending = active_versions.filter(total_attempts=0).count()

    pattern_stats = {
        "total": total,
        "healthy": healthy,
        "warning": warning,
        "failing": failing,
        "pending": pending,
    }

    # Celery stats (if available)
    try:
        from .admin_services import CeleryMonitorService
        celery_stats = CeleryMonitorService.get_worker_stats()
    except Exception:
        celery_stats = None

    # OperationLog health summary
    try:
        from .operation_log_services import OperationLogAnalyticsService
        operation_health = OperationLogAnalyticsService.get_service_health_summary()
    except Exception as e:
        logger.warning(f"Error getting operation log health: {e}")
        operation_health = None

    context = {
        'recent_versions': recent_versions,
        'recent_pattern_changes': recent_pattern_changes,
        'pattern_stats': pattern_stats,
        'celery_stats': celery_stats,
        'operation_health': operation_health,
    }

    return render(request, "admin/dashboard.html", context)


@login_required
def admin_logs(request):
    """Admin logs view - display logs sorted by task type."""
    if not request.user.is_staff:
        messages.error(request, "Access denied.")
        return redirect("dashboard")

    from datetime import timedelta
    from django.utils import timezone

    # Get filter parameters
    task_type = request.GET.get(
        "task", "all"
    )  # all, fetch (price fetches), pattern, celery
    status_filter = request.GET.get("status", "all")  # all, success, failed
    time_range = request.GET.get("range", "24h")  # 1h, 24h, 7d, 30d, all

    # Calculate time filter
    now = timezone.now()
    time_filters = {
        "1h": now - timedelta(hours=1),
        "24h": now - timedelta(hours=24),
        "7d": now - timedelta(days=7),
        "30d": now - timedelta(days=30),
        "all": None,
    }
    time_since = time_filters.get(time_range)

    # ========== PRICE FETCHES (from OperationLog) ==========
    fetch_logs_query = OperationLog.objects.filter(
        service='fetcher'
    ).select_related(
        "listing__product", "listing__store"
    ).order_by("-timestamp")

    if time_since:
        fetch_logs_query = fetch_logs_query.filter(timestamp__gte=time_since)

    if status_filter == "success":
        # Success = INFO level, no ERROR/CRITICAL
        fetch_logs_query = fetch_logs_query.filter(level__in=['INFO', 'DEBUG'])
    elif status_filter == "failed":
        # Failed = ERROR or CRITICAL level
        fetch_logs_query = fetch_logs_query.filter(level__in=['ERROR', 'CRITICAL'])

    # Get fetch log statistics
    fetch_stats = fetch_logs_query.aggregate(
        total=Count("id"),
        success_count=Count("id", filter=Q(level__in=['INFO', 'DEBUG'])),
        failed_count=Count("id", filter=Q(level__in=['ERROR', 'CRITICAL'])),
        avg_duration=Avg("duration_ms"),
    )

    # Calculate success rate
    if fetch_stats["total"] > 0:
        fetch_stats["success_rate"] = (
            fetch_stats["success_count"] / fetch_stats["total"]
        ) * 100
    else:
        fetch_stats["success_rate"] = 0

    # Get recent fetch logs (limit to 100 for performance)
    recent_fetch_logs = fetch_logs_query[:100] if task_type in ["all", "fetch"] else []

    # ========== PATTERN HISTORY ==========
    # PatternHistory model was removed - use ExtractorVersion for tracking

    # Get pattern history statistics
    pattern_stats = {
        "total": 0,
        "auto_generated": 0,
        "manual_edit": 0,
        "rollback": 0,
    }

    # Get recent pattern changes (now empty, since PatternHistory was removed)
    recent_pattern_changes = []

    # ========== ADMIN FLAGS ==========
    from .models import AdminFlag

    admin_flags_query = AdminFlag.objects.select_related(
        "store", "resolved_by"
    ).order_by("-created_at")

    if time_since:
        admin_flags_query = admin_flags_query.filter(created_at__gte=time_since)

    if status_filter == "success":
        admin_flags_query = admin_flags_query.filter(status="resolved")
    elif status_filter == "failed":
        admin_flags_query = admin_flags_query.filter(status="pending")

    # Get admin flag statistics
    flag_stats = {
        "total": admin_flags_query.count(),
        "pending": admin_flags_query.filter(status="pending").count(),
        "in_progress": admin_flags_query.filter(status="in_progress").count(),
        "resolved": admin_flags_query.filter(status="resolved").count(),
    }

    # Get recent admin flags
    recent_admin_flags = admin_flags_query[:50] if task_type in ["all", "admin"] else []

    # ========== CELERY TASKS (if available) ==========
    celery_tasks = []
    celery_stats = {"total": 0, "success": 0, "failed": 0, "pending": 0}

    try:
        from django_celery_results.models import TaskResult

        celery_query = TaskResult.objects.order_by("-date_done")

        if time_since:
            celery_query = celery_query.filter(date_done__gte=time_since)

        if status_filter == "success":
            celery_query = celery_query.filter(status="SUCCESS")
        elif status_filter == "failed":
            celery_query = celery_query.filter(status="FAILURE")

        celery_stats = {
            "total": celery_query.count(),
            "success": celery_query.filter(status="SUCCESS").count(),
            "failed": celery_query.filter(status="FAILURE").count(),
            "pending": celery_query.filter(status="PENDING").count(),
        }

        celery_tasks = celery_query[:50] if task_type in ["all", "celery"] else []

    except ImportError:
        # django_celery_results not installed
        pass

    # ========== AGGREGATE STATS ==========
    total_logs = (
        fetch_stats["total"]
        + pattern_stats["total"]
        + flag_stats["total"]
        + celery_stats["total"]
    )

    context = {
        "task_type": task_type,
        "status_filter": status_filter,
        "time_range": time_range,
        "total_logs": total_logs,
        # Price fetches
        "fetch_logs": recent_fetch_logs,
        "fetch_stats": fetch_stats,
        # Pattern changes
        "pattern_changes": recent_pattern_changes,
        "pattern_stats": pattern_stats,
        # Admin flags
        "admin_flags": recent_admin_flags,
        "flag_stats": flag_stats,
        # Celery tasks
        "celery_tasks": celery_tasks,
        "celery_stats": celery_stats,
    }

    return render(request, "admin/logs.html", context)


@login_required
def operation_log_analytics(request):
    """Operation log analytics dashboard with comprehensive statistics."""
    if not request.user.is_staff:
        messages.error(request, "Access denied.")
        return redirect("dashboard")

    from .operation_log_services import OperationLogAnalyticsService
    from datetime import timedelta
    from django.utils import timezone

    # Get filter parameters
    service = request.GET.get('service', None)
    time_range = request.GET.get('range', '24h')

    # Calculate time filter
    now = timezone.now()
    time_filters = {
        '1h': now - timedelta(hours=1),
        '24h': now - timedelta(hours=24),
        '7d': now - timedelta(days=7),
        '30d': now - timedelta(days=30),
        'all': None,
    }
    time_since = time_filters.get(time_range)

    # Get comprehensive statistics
    statistics = OperationLogAnalyticsService.get_statistics(
        service=service,
        time_since=time_since
    )

    # Get failure analysis
    failure_analysis = OperationLogAnalyticsService.get_failure_analysis(
        service=service,
        time_since=time_since,
        limit=20
    )

    # Get performance metrics
    performance_metrics = OperationLogAnalyticsService.get_performance_metrics(
        service=service,
        time_since=time_since
    )

    # Get timeline analysis (hourly for 24h, daily for longer)
    bucket_size = 'hour' if time_range in ['1h', '24h'] else 'day'
    timeline_analysis = OperationLogAnalyticsService.get_timeline_analysis(
        time_since=time_since,
        bucket_size=bucket_size
    )

    context = {
        'service': service,
        'time_range': time_range,
        'statistics': statistics,
        'failure_analysis': failure_analysis,
        'performance_metrics': performance_metrics,
        'timeline_analysis': timeline_analysis,
    }

    return render(request, "admin/operation_analytics.html", context)


@login_required
def task_timeline(request, task_id):
    """View detailed timeline for a specific task."""
    if not request.user.is_staff:
        messages.error(request, "Access denied.")
        return redirect("dashboard")

    from .operation_log_services import OperationLogService

    # Get timeline for this task
    timeline = OperationLogService.get_task_timeline(task_id)

    if not timeline:
        messages.warning(request, f"No logs found for task {task_id}")
        return redirect("admin_logs")

    context = {
        'task_id': task_id,
        'timeline': timeline,
        'total_events': len(timeline),
        'total_duration_ms': timeline[-1]['elapsed_ms'] if timeline else 0,
    }

    return render(request, "admin/task_timeline.html", context)


@login_required
def operation_log_health(request):
    """Service health summary dashboard."""
    if not request.user.is_staff:
        messages.error(request, "Access denied.")
        return redirect("dashboard")

    from .operation_log_services import OperationLogAnalyticsService

    # Get service health summary
    health_summary = OperationLogAnalyticsService.get_service_health_summary()

    context = {
        'health_summary': health_summary,
    }

    return render(request, "admin/operation_health.html", context)


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

    from .version_services import VersionAnalyticsService

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


# Settings
@login_required
def user_settings(request):
    """User settings page."""
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

    context = {
        "active_subscriptions": active_subscriptions,
        "stores_tracked": stores_tracked,
        "unread_notifications": unread_notifications,
    }

    return render(request, "settings.html", context)


@login_required
@require_http_methods(["POST"])
def change_password(request):
    """Handle password change."""
    from django.contrib.auth import update_session_auth_hash
    from django.contrib.auth.forms import PasswordChangeForm

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


def proxy_image(request):
    """
    Proxy external images to bypass hotlink protection.

    Usage: /proxy-image/?url=https://example.com/image.jpg
    """
    import httpx
    from urllib.parse import unquote

    image_url = request.GET.get("url")

    if not image_url:
        return HttpResponse("Missing url parameter", status=400)

    # Decode URL if it's encoded
    image_url = unquote(image_url)

    # Validate it's an image URL
    if not image_url.startswith(("http://", "https://")):
        return HttpResponse("Invalid URL", status=400)

    try:
        # Fetch image with proper headers to bypass hotlink protection
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": image_url.split("/")[0] + "//" + image_url.split("/")[2] + "/",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        }

        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            response = client.get(image_url, headers=headers)

            if response.status_code == 200:
                # Determine content type
                content_type = response.headers.get("Content-Type", "image/jpeg")

                # Return the image
                return HttpResponse(response.content, content_type=content_type)
            else:
                # Return placeholder or error
                return HttpResponse(
                    f"Failed to fetch image: {response.status_code}",
                    status=response.status_code,
                )

    except Exception as e:
        logger.error(f"Image proxy error for {image_url}: {e}")
        return HttpResponse("Failed to fetch image", status=500)


# ========== Pattern Management Views ==========


@login_required
@require_http_methods(["POST"])
def api_regenerate_pattern(request):
    """HTMX endpoint: Trigger pattern regeneration."""
    if not request.user.is_staff:
        return JsonResponse({"error": "Staff access required"}, status=403)

    domain = request.POST.get("domain", "").strip()

    if not domain:
        return JsonResponse({"error": "Domain is required"}, status=400)

    try:
        from .models import ExtractorVersion

        # Check if there's an active extractor for this domain
        extractor = ExtractorVersion.objects.filter(domain=domain, is_active=True).first()

        if not extractor:
            return JsonResponse(
                {"error": f"No active extractor found for {domain}"},
                status=404
            )

        # Find sample listing for this domain
        sample_listing = ProductListing.objects.filter(store__domain=domain).first()

        if not sample_listing:
            return JsonResponse(
                {
                    "error": f"No product listings found for {domain}. Add a product from this store first."
                },
                status=400,
            )

        # Trigger Celery task
        from app.tasks import generate_pattern

        task = generate_pattern.delay(
            url=sample_listing.url, domain=domain, listing_id=str(sample_listing.id)
        )

        return JsonResponse(
            {
                "success": True,
                "task_id": task.id,
                "message": f"Pattern regeneration started (Task ID: {task.id})",
            }
        )
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def submit_feedback(request):
    """Submit user feedback via HTMX form."""
    import json

    try:
        # Extract form data
        message = request.POST.get('message', '').strip()
        page_url = request.POST.get('page_url', '').strip()
        page_title = request.POST.get('page_title', '').strip()
        view_name = request.POST.get('view_name', '').strip()
        context_data_str = request.POST.get('context_data', '{}')

        # Validation
        if not message:
            return JsonResponse({'success': False, 'error': 'Feedback message is required'}, status=400)

        if len(message) > 2000:
            return JsonResponse({'success': False, 'error': 'Feedback message is too long (max 2000 characters)'}, status=400)

        if not page_url:
            return JsonResponse({'success': False, 'error': 'Page URL is required'}, status=400)

        # Parse context data
        try:
            context_data = json.loads(context_data_str)
        except json.JSONDecodeError:
            context_data = {}

        # Create feedback record
        from .models import UserFeedback
        feedback = UserFeedback.objects.create(
            user=request.user,
            message=message,
            page_url=page_url,
            page_title=page_title,
            view_name=view_name,
            context_data=context_data
        )

        logger.info(f"User feedback submitted: user={request.user.username}, feedback_id={feedback.id}, page_url={page_url}")

        return JsonResponse({
            'success': True,
            'message': 'Thank you for your feedback!',
            'data': {'feedback_id': feedback.id}
        })

    except Exception as e:
        logger.error(f"Error submitting feedback: user={request.user.username}, error={str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': 'An error occurred while submitting feedback'}, status=500)


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
        import uuid
        from .services import ProductRelationService

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
            from django.http import HttpResponse

            # If dismissed, remove card from DOM
            if weight == 0:
                return HttpResponse("")

            # Otherwise, return updated card with new vote state
            from .models import Product
            suggested_product = Product.objects.get(id=suggested_product_uuid)

            # Re-fetch similarity score
            from .services import ProductSimilarityService
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

    from .services import ProductSimilarityService, ProductRelationService

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


def pricing_view(request):
    """Pricing tiers page."""
    return render(request, 'pricing.html')


def about_view(request):
    """About us page."""
    return render(request, 'about.html')
