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
from .models import (
    Product,
    ProductListing,
    UserSubscription,
    Notification,
    Pattern,
    FetchLog,
)

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
                messages.success(request, f"Welcome back, {username}!")
                return redirect("dashboard")
        else:
            messages.error(request, "Invalid username or password.")
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
            messages.success(request, "Account created successfully!")
            return redirect("dashboard")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = UserCreationForm()

    return render(request, "auth/register.html", {"form": form})


def logout_view(request):
    """User logout view."""
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect("login")


# Main views
def dashboard(request):
    """Main dashboard view - accessible to everyone."""
    if request.user.is_authenticated:
        from django.db.models import Min, Count

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
    from django.db.models import Min, Count

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

    context = {
        "subscription": subscription,
        "product": subscription.product,
        "listings": listings,
        "best_listing": best_listing,
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
            import logging

            logger = logging.getLogger(__name__)
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
                    request, f"Subscribed to {product.name}! Fetching current price..."
                )
            else:
                messages.info(request, f"Updated subscription to {product.name}")

            return redirect("subscription_detail", subscription_id=subscription.id)

        except ValueError as e:
            messages.error(request, str(e))
            return redirect("dashboard")
        except Exception as e:
            messages.error(request, f"Failed to add product: {str(e)}")
            return redirect("dashboard")

    # POST - only for authenticated users
    if not request.user.is_authenticated:
        messages.error(request, "Please log in to track products.")
        return redirect("login")

    url = request.POST.get("url", "").strip()

    if not url:
        messages.error(request, "Please provide a valid product URL.")
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
                request, f"Subscribed to {product.name}! Fetching current price..."
            )
        else:
            messages.info(request, f"Updated subscription to {product.name}")

        return redirect("subscription_detail", subscription_id=subscription.id)

    except ValueError as e:
        messages.error(request, str(e))
        return redirect("dashboard")
    except Exception as e:
        messages.error(request, f"Failed to add product: {str(e)}")
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

    messages.success(request, f'Unsubscribed from "{product_name}"')

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

    messages.success(request, "Subscription settings updated successfully")

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

    return redirect("subscription_detail", subscription_id=subscription_id)


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
            from django.db.models import Min

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

    products = Product.objects.filter(
        user=request.user, active=True, name__icontains=query
    ).order_by("-last_viewed")[:5]

    return render(request, "search/autocomplete.html", {"products": products})


@login_required
def price_history_chart(request, product_id):
    """Price history chart data."""
    # TODO: Implement
    return HttpResponse("Chart data")


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
    """Admin dashboard."""
    if not request.user.is_staff:
        messages.error(request, "Access denied.")
        return redirect("dashboard")

    # TODO: Implement
    return render(request, "admin/dashboard.html")


@login_required
def admin_logs(request):
    """Admin logs view - display logs sorted by task type."""
    if not request.user.is_staff:
        messages.error(request, "Access denied.")
        return redirect("dashboard")

    from django.db.models import Count, Avg, Q
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

    # ========== PRICE FETCHES ==========
    fetch_logs_query = FetchLog.objects.select_related(
        "listing__product", "listing__store"
    ).order_by("-fetched_at")

    if time_since:
        fetch_logs_query = fetch_logs_query.filter(fetched_at__gte=time_since)

    if status_filter == "success":
        fetch_logs_query = fetch_logs_query.filter(success=True)
    elif status_filter == "failed":
        fetch_logs_query = fetch_logs_query.filter(success=False)

    # Get fetch log statistics
    fetch_stats = fetch_logs_query.aggregate(
        total=Count("id"),
        success_count=Count("id", filter=Q(success=True)),
        failed_count=Count("id", filter=Q(success=False)),
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
    from .models import PatternHistory

    pattern_history_query = PatternHistory.objects.select_related(
        "pattern", "changed_by"
    ).order_by("-created_at")

    if time_since:
        pattern_history_query = pattern_history_query.filter(created_at__gte=time_since)

    # Get pattern history statistics
    pattern_stats = {
        "total": pattern_history_query.count(),
        "auto_generated": pattern_history_query.filter(
            change_type="auto_generated"
        ).count(),
        "manual_edit": pattern_history_query.filter(change_type="manual_edit").count(),
        "rollback": pattern_history_query.filter(change_type="rollback").count(),
    }

    # Get recent pattern changes
    recent_pattern_changes = (
        pattern_history_query[:50] if task_type in ["all", "pattern"] else []
    )

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
def patterns_status(request):
    """Pattern health status."""
    if not request.user.is_staff:
        messages.error(request, "Access denied.")
        return redirect("dashboard")

    # TODO: Implement
    return render(request, "admin/patterns.html")


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
    from django.db.models import Count

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
        messages.success(request, "Your password was successfully updated!")
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
def pattern_list(request):
    """List all patterns with statistics."""
    if not request.user.is_staff:
        messages.error(request, "Staff access required.")
        return redirect("dashboard")

    from .pattern_services import PatternManagementService

    # Get search/filter params
    search_query = request.GET.get("search", "").strip()
    filter_status = request.GET.get("status", "all")

    # Get all patterns with stats
    result = PatternManagementService.get_all_patterns(with_stats=True)
    patterns = result["patterns"]
    stats = result["stats"]

    # Apply search filter
    if search_query:
        patterns = patterns.filter(domain__icontains=search_query)

    # Apply status filter
    if filter_status == "healthy":
        patterns = patterns.filter(success_rate__gte=0.8)
    elif filter_status == "warning":
        patterns = patterns.filter(success_rate__gte=0.6, success_rate__lt=0.8)
    elif filter_status == "failing":
        patterns = patterns.filter(success_rate__lt=0.6)
    elif filter_status == "pending":
        patterns = patterns.filter(total_attempts=0)

    context = {
        "patterns": patterns,
        "stats": stats,
        "search_query": search_query,
        "filter_status": filter_status,
    }

    return render(request, "admin/patterns/list.html", context)


@login_required
def pattern_detail(request, domain):
    """Pattern visualization view - read-only with live test results."""
    if not request.user.is_staff:
        messages.error(request, "Staff access required.")
        return redirect("dashboard")

    from .pattern_services import PatternTestService

    pattern = get_object_or_404(Pattern, domain=domain)

    # Test pattern for visualization
    test_results = PatternTestService.test_pattern_for_visualization(pattern)

    # Get history count for header
    history_count = pattern.history.count()

    context = {
        "pattern": pattern,
        "test_results": test_results,
        "history_count": history_count,
    }

    return render(request, "admin/patterns/detail_visualization.html", context)


@login_required
@require_http_methods(["GET", "POST"])
def pattern_create(request):
    """Create new pattern."""
    if not request.user.is_staff:
        messages.error(request, "Staff access required.")
        return redirect("dashboard")

    if request.method == "POST":
        from .pattern_services import PatternManagementService
        from . import pattern_validators
        import json

        domain = request.POST.get("domain", "").strip()
        pattern_json_str = request.POST.get("pattern_json", "").strip()
        change_reason = request.POST.get("change_reason", "Initial creation")

        try:
            # Parse JSON
            pattern_json = json.loads(pattern_json_str)

            # Validate structure
            validation = pattern_validators.validate_pattern_structure(pattern_json)
            if not validation["valid"]:
                messages.error(
                    request, f"Invalid pattern: {', '.join(validation['errors'])}"
                )
                return render(
                    request,
                    "admin/patterns/create.html",
                    {
                        "domain": domain,
                        "pattern_json": pattern_json_str,
                        "change_reason": change_reason,
                    },
                )

            # Sanitize
            pattern_json = pattern_validators.sanitize_pattern_json(pattern_json)

            # Create pattern
            pattern, created = PatternManagementService.create_pattern(
                domain=domain,
                pattern_json=pattern_json,
                user=request.user,
                change_reason=change_reason,
            )

            if created:
                messages.success(request, f"Pattern for {domain} created successfully!")
            else:
                messages.info(
                    request, f"Pattern for {domain} already exists and was updated."
                )

            return redirect("pattern_detail", domain=domain)

        except json.JSONDecodeError as e:
            messages.error(request, f"Invalid JSON: {str(e)}")
            return render(
                request,
                "admin/patterns/create.html",
                {
                    "domain": domain,
                    "pattern_json": pattern_json_str,
                    "change_reason": change_reason,
                },
            )
        except Exception as e:
            messages.error(request, f"Error creating pattern: {str(e)}")
            return render(
                request,
                "admin/patterns/create.html",
                {
                    "domain": domain,
                    "pattern_json": pattern_json_str,
                    "change_reason": change_reason,
                },
            )

    # GET - show form
    # Provide template pattern JSON
    template_pattern = {
        "store_domain": "",
        "patterns": {
            "price": {
                "primary": {
                    "type": "css",
                    "selector": ".price",
                    "confidence": 0.95,
                    "description": "Primary price selector",
                },
                "fallbacks": [],
            },
            "title": {
                "primary": {
                    "type": "css",
                    "selector": "h1.product-title",
                    "confidence": 0.90,
                    "description": "Product title",
                },
                "fallbacks": [],
            },
            "image": {
                "primary": {
                    "type": "meta",
                    "selector": "og:image",
                    "confidence": 0.85,
                    "description": "Open Graph image",
                },
                "fallbacks": [],
            },
            "availability": {
                "primary": {
                    "type": "css",
                    "selector": ".stock-status",
                    "confidence": 0.80,
                    "description": "Stock availability",
                },
                "fallbacks": [],
            },
        },
        "metadata": {"validated_count": 0, "confidence_score": 0.0},
    }

    import json

    template_json = json.dumps(template_pattern, indent=2)

    return render(
        request, "admin/patterns/create.html", {"template_json": template_json}
    )


@login_required
@require_http_methods(["POST"])
def pattern_edit(request, domain):
    """Update pattern."""
    if not request.user.is_staff:
        return JsonResponse({"error": "Staff access required"}, status=403)

    from .pattern_services import PatternManagementService
    from . import pattern_validators
    import json

    pattern_json_str = request.POST.get("pattern_json", "").strip()
    change_reason = request.POST.get("change_reason", "Manual edit")

    try:
        # Parse JSON
        pattern_json = json.loads(pattern_json_str)

        # Validate
        validation = pattern_validators.validate_pattern_structure(pattern_json)
        if not validation["valid"]:
            messages.error(
                request, f"Invalid pattern: {', '.join(validation['errors'])}"
            )
            return redirect("pattern_detail", domain=domain)

        # Sanitize
        pattern_json = pattern_validators.sanitize_pattern_json(pattern_json)

        # Update pattern
        pattern = PatternManagementService.update_pattern(
            domain=domain,
            pattern_json=pattern_json,
            user=request.user,
            change_reason=change_reason,
        )

        messages.success(request, f"Pattern for {domain} updated successfully!")
        return redirect("pattern_detail", domain=domain)

    except json.JSONDecodeError as e:
        messages.error(request, f"Invalid JSON: {str(e)}")
        return redirect("pattern_detail", domain=domain)
    except Exception as e:
        messages.error(request, f"Error updating pattern: {str(e)}")
        return redirect("pattern_detail", domain=domain)


@login_required
@require_http_methods(["POST"])
def pattern_delete(request, domain):
    """Delete pattern."""
    if not request.user.is_staff:
        return JsonResponse({"error": "Staff access required"}, status=403)

    from .pattern_services import PatternManagementService

    if PatternManagementService.delete_pattern(domain):
        messages.success(request, f"Pattern for {domain} deleted successfully.")
    else:
        messages.error(request, f"Pattern for {domain} not found.")

    return redirect("pattern_list")


@login_required
def pattern_history(request, domain):
    """Pattern version history."""
    if not request.user.is_staff:
        messages.error(request, "Staff access required.")
        return redirect("dashboard")

    from .pattern_services import PatternHistoryService

    pattern = get_object_or_404(Pattern, domain=domain)
    history = PatternHistoryService.get_pattern_history(domain, limit=100)

    context = {
        "pattern": pattern,
        "history": history,
    }

    return render(request, "admin/patterns/history.html", context)


@login_required
def pattern_compare(request, domain, v1, v2):
    """Compare two pattern versions."""
    if not request.user.is_staff:
        messages.error(request, "Staff access required.")
        return redirect("dashboard")

    from .pattern_services import PatternHistoryService
    import json

    pattern = get_object_or_404(Pattern, domain=domain)
    version1 = PatternHistoryService.get_pattern_version(domain, v1)
    version2 = PatternHistoryService.get_pattern_version(domain, v2)

    if not version1 or not version2:
        messages.error(request, "One or both versions not found.")
        return redirect("pattern_history", domain=domain)

    # Generate diff
    diff = PatternHistoryService.compare_versions(
        version1.pattern_json, version2.pattern_json
    )

    context = {
        "pattern": pattern,
        "version1": version1,
        "version2": version2,
        "diff": diff,
        "version1_json": json.dumps(version1.pattern_json, indent=2),
        "version2_json": json.dumps(version2.pattern_json, indent=2),
    }

    return render(request, "admin/patterns/compare.html", context)


@login_required
@require_http_methods(["POST"])
def pattern_rollback(request, domain, version):
    """Rollback to previous pattern version."""
    if not request.user.is_staff:
        return JsonResponse({"error": "Staff access required"}, status=403)

    from .pattern_services import PatternManagementService

    try:
        change_reason = request.POST.get("reason", f"Rollback to version {version}")

        pattern = PatternManagementService.rollback_pattern(
            domain=domain,
            version_number=version,
            user=request.user,
            change_reason=change_reason,
        )

        messages.success(
            request, f"Pattern rolled back to version {version} successfully!"
        )
        return redirect("pattern_detail", domain=domain)

    except Exception as e:
        messages.error(request, f"Error rolling back pattern: {str(e)}")
        return redirect("pattern_history", domain=domain)


# ========== Pattern HTMX API Endpoints ==========


@login_required
@require_http_methods(["POST"])
def api_test_pattern(request):
    """HTMX endpoint: Test pattern against URL."""
    if not request.user.is_staff:
        return JsonResponse({"error": "Staff access required"}, status=403)

    from .pattern_services import PatternTestService
    import json

    url = request.POST.get("test_url", "").strip()
    pattern_json_str = request.POST.get("pattern_json", "").strip()

    if not url:
        return HttpResponse(
            '<div class="text-red-600">Please enter a URL to test.</div>'
        )

    if not pattern_json_str:
        return HttpResponse('<div class="text-red-600">Pattern JSON is required.</div>')

    try:
        pattern_json = json.loads(pattern_json_str)

        # Test pattern
        result = PatternTestService.test_pattern_against_url(url, pattern_json)

        context = {"result": result, "url": url}
        return render(request, "admin/patterns/partials/test_result.html", context)

    except json.JSONDecodeError as e:
        return HttpResponse(f'<div class="text-red-600">Invalid JSON: {str(e)}</div>')
    except Exception as e:
        return HttpResponse(
            f'<div class="text-red-600">Error testing pattern: {str(e)}</div>'
        )


@login_required
@require_http_methods(["POST"])
def api_validate_pattern(request):
    """HTMX endpoint: Validate pattern syntax."""
    if not request.user.is_staff:
        return JsonResponse({"error": "Staff access required"}, status=403)

    from .pattern_services import PatternTestService
    import json

    pattern_json_str = request.POST.get("pattern_json", "").strip()

    if not pattern_json_str:
        return HttpResponse(
            '<div class="text-yellow-600">No pattern to validate.</div>'
        )

    try:
        pattern_json = json.loads(pattern_json_str)

        # Validate pattern
        validation = PatternTestService.validate_pattern_syntax(pattern_json)

        context = {"validation": validation}
        return render(
            request, "admin/patterns/partials/validation_result.html", context
        )

    except json.JSONDecodeError as e:
        return HttpResponse(f'<div class="text-red-600">Invalid JSON: {str(e)}</div>')
    except Exception as e:
        return HttpResponse(
            f'<div class="text-red-600">Error validating pattern: {str(e)}</div>'
        )


@login_required
@require_http_methods(["POST"])
def api_test_selector(request):
    """HTMX endpoint: Test single selector."""
    if not request.user.is_staff:
        return JsonResponse({"error": "Staff access required"}, status=403)

    from .pattern_services import PatternTestService

    html = request.POST.get("html", "")
    selector_type = request.POST.get("selector_type", "")
    selector = request.POST.get("selector", "")
    attribute = request.POST.get("attribute", None)

    selector_config = {
        "type": selector_type,
        "selector": selector,
        "attribute": attribute,
    }

    result = PatternTestService.test_single_selector(html, selector_config)

    return JsonResponse(result)


@login_required
@require_http_methods(["POST"])
def api_fetch_html(request):
    """HTMX endpoint: Fetch HTML from URL."""
    if not request.user.is_staff:
        return JsonResponse({"error": "Staff access required"}, status=403)

    from .pattern_services import PatternTestService
    from django.core.cache import cache

    url = request.POST.get("url", "").strip()

    if not url:
        return JsonResponse({"error": "URL is required"}, status=400)

    # Rate limiting check
    cache_key = f"fetch_html_rate_{request.user.id}"
    if cache.get(cache_key):
        return JsonResponse(
            {"error": "Rate limited. Please wait 30 seconds before fetching again."},
            status=429,
        )

    try:
        html, metadata = PatternTestService.fetch_html(url, use_cache=True)

        # Set rate limit (30 seconds)
        cache.set(cache_key, True, 30)

        # Truncate HTML for response (max 50KB)
        html_truncated = html[:50000]

        return JsonResponse(
            {"success": True, "html": html_truncated, "metadata": metadata}
        )

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def api_retest_pattern_visualization(request):
    """HTMX endpoint: Re-test pattern for visualization page."""
    if not request.user.is_staff:
        return JsonResponse({"error": "Staff access required"}, status=403)

    from .pattern_services import PatternTestService

    domain = request.POST.get("domain", "").strip()

    if not domain:
        return HttpResponse(
            '<div class="text-red-600 dark:text-red-400">Domain is required.</div>'
        )

    try:
        pattern = Pattern.objects.get(domain=domain)
        test_results = PatternTestService.test_pattern_for_visualization(pattern)
        context = {"test_results": test_results}
        return render(request, "admin/patterns/partials/field_cards.html", context)

    except Pattern.DoesNotExist:
        return HttpResponse(
            '<div class="text-red-600 dark:text-red-400">Pattern not found.</div>'
        )
    except Exception as e:
        logger.exception(f"Error re-testing pattern: {e}")
        return HttpResponse(
            f'<div class="text-red-600 dark:text-red-400">Error: {str(e)}</div>'
        )


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
        pattern = Pattern.objects.get(domain=domain)

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

    except Pattern.DoesNotExist:
        return JsonResponse({"error": f"Pattern for {domain} not found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
