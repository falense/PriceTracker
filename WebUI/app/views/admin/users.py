"""
Admin user management views for PriceTracker WebUI.

Handles user listing, tier management, and user deletion.
"""

import logging

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Count, Q
from django.core.paginator import Paginator

from ...models import CustomUser, UserSubscription

logger = logging.getLogger(__name__)


@login_required
def admin_users_list(request):
    """List all users with tier information and management capabilities."""
    if not request.user.is_staff:
        messages.error(request, 'Du må være administrator for å se denne siden.')
        return redirect('dashboard')

    # Get search and filter parameters
    search_query = request.GET.get('search', '').strip()
    tier_filter = request.GET.get('tier', 'all')

    # Base queryset with optimizations
    users = CustomUser.objects.all().annotate(
        active_product_count=Count('subscriptions', filter=Q(subscriptions__active=True))
    ).select_related('tier_updated_by').order_by('-date_joined')

    # Apply search filter
    if search_query:
        users = users.filter(
            Q(username__icontains=search_query) |
            Q(email__icontains=search_query)
        )

    # Apply tier filter
    if tier_filter != 'all':
        users = users.filter(tier=tier_filter)

    # Calculate tier statistics
    tier_stats = {
        'total': CustomUser.objects.count(),
        'free': CustomUser.objects.filter(tier='free').count(),
        'supporter': CustomUser.objects.filter(tier='supporter').count(),
        'ultimate': CustomUser.objects.filter(tier='ultimate').count(),
    }

    # Pagination
    page_number = request.GET.get('page', 1)
    paginator = Paginator(users, 20)  # 20 users per page
    page_obj = paginator.get_page(page_number)

    # Calculate usage percentage for each user
    for user in page_obj:
        limit = user.get_product_limit()
        if limit is None:
            user.usage_percentage = 0
        elif limit > 0:
            user.usage_percentage = int((user.active_product_count / limit) * 100)
        else:
            user.usage_percentage = 0
        user.products_remaining = user.get_products_remaining()

    context = {
        'users': page_obj,
        'page_obj': page_obj,
        'search_query': search_query,
        'tier_filter': tier_filter,
        'tier_stats': tier_stats,
    }

    return render(request, 'admin/users.html', context)


@login_required
@require_http_methods(["POST"])
def admin_update_user_tier(request, user_id):
    """Update a user's tier (HTMX endpoint)."""
    if not request.user.is_staff:
        return HttpResponse(
            '<tr><td colspan="8" class="px-6 py-4 text-red-600 dark:text-red-400">Ingen tilgang</td></tr>',
            status=403
        )

    # Validate tier
    VALID_TIERS = ['free', 'supporter', 'ultimate']
    new_tier = request.POST.get('tier')

    if not new_tier or new_tier not in VALID_TIERS:
        return HttpResponse(
            f'<tr><td colspan="8" class="px-6 py-4 text-red-600 dark:text-red-400">Ugyldig abonnementstype</td></tr>',
            status=400
        )

    # Get user
    try:
        user = CustomUser.objects.annotate(
            active_product_count=Count('subscriptions', filter=Q(subscriptions__active=True))
        ).select_related('tier_updated_by').get(id=user_id)
    except CustomUser.DoesNotExist:
        return HttpResponse(
            '<tr><td colspan="8" class="px-6 py-4 text-red-600 dark:text-red-400">Bruker ikke funnet</td></tr>',
            status=404
        )

    # Update tier if changed
    if new_tier != user.tier:
        user.tier = new_tier
        user.tier_updated_by = request.user
        # Mark tier as admin-assigned to prevent referral system from overriding
        user.referral_tier_source = 'admin'
        user.referral_tier_expires_at = None  # Admin tiers don't expire
        user.save()
        logger.info(f"Admin {request.user.username} updated tier for user {user.username} to {new_tier}")

    # Calculate usage percentage
    limit = user.get_product_limit()
    if limit is None:
        user.usage_percentage = 0
    elif limit > 0:
        user.usage_percentage = int((user.active_product_count / limit) * 100)
    else:
        user.usage_percentage = 0
    user.products_remaining = user.get_products_remaining()

    # Return updated row
    return render(request, 'admin/partials/user_row.html', {'user': user})


@login_required
def admin_user_detail(request, user_id):
    """Display detailed information about a specific user."""
    if not request.user.is_staff:
        messages.error(request, 'Du må være administrator for å se denne siden.')
        return redirect('dashboard')

    # Get user with related data
    user = get_object_or_404(
        CustomUser.objects.annotate(
            active_product_count=Count('subscriptions', filter=Q(subscriptions__active=True))
        ).select_related('tier_updated_by'),
        id=user_id
    )

    # Get user's active subscriptions
    subscriptions = UserSubscription.objects.filter(
        user=user, active=True
    ).select_related('product').order_by('-created_at')[:10]

    # Calculate usage stats
    limit = user.get_product_limit()
    if limit is None:
        usage_percentage = 0
    elif limit > 0:
        usage_percentage = int((user.active_product_count / limit) * 100)
    else:
        usage_percentage = 0

    context = {
        'viewed_user': user,
        'subscriptions': subscriptions,
        'usage_percentage': usage_percentage,
        'products_remaining': user.get_products_remaining(),
    }

    return render(request, 'admin/user_detail.html', context)


@login_required
def admin_delete_user(request, user_id):
    """Delete a user (admin only)."""
    if not request.user.is_staff:
        messages.error(request, 'Du må være administrator for å utføre denne handlingen.')
        return redirect('dashboard')

    if request.method != 'POST':
        messages.error(request, 'Ugyldig forespørsel.')
        return redirect('admin_users_list')

    # Get user
    try:
        user = CustomUser.objects.get(id=user_id)
    except CustomUser.DoesNotExist:
        messages.error(request, 'Bruker ikke funnet.')
        return redirect('admin_users_list')

    # Prevent deleting yourself
    if user.id == request.user.id:
        messages.error(request, 'Du kan ikke slette din egen bruker.')
        return redirect('admin_users_list')

    # Store username for message
    username = user.username

    # Delete the user (CASCADE will handle related objects)
    user.delete()

    messages.success(request, f'Brukeren "{username}" ble slettet.')
    return redirect('admin_users_list')
