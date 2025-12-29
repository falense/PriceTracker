"""
Referral system views for PriceTracker WebUI.

Handles referral link tracking and user referral dashboard.
"""

import logging
import uuid

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.urls import reverse

logger = logging.getLogger(__name__)


def referral_landing(request, code):
    """
    Handle referral link clicks.
    1. Track the visit
    2. Set tracking cookie
    3. Redirect to dashboard (or register if not logged in)
    """
    from ..models import ReferralCode, ReferralVisit
    from ..services import ReferralService

    # Get referral code
    try:
        referral_code = ReferralCode.objects.select_related('user').get(code=code, active=True)
    except ReferralCode.DoesNotExist:
        messages.error(request, "Ugyldig henvisningskode.")
        return redirect('dashboard')

    # Don't track if user is clicking their own referral link (unless staff for testing)
    is_staff_testing = False
    if request.user.is_authenticated and request.user == referral_code.user:
        if not request.user.is_staff:
            messages.info(request, "Du kan ikke bruke din egen henvisningskode.")
            return redirect('dashboard')
        else:
            # Staff bypass - allow for testing (message added later after success)
            is_staff_testing = True

    # Check if this is a unique visit (bypass deduplication for staff testing)
    if is_staff_testing:
        is_unique = True
        duplicate_reason = ''
    else:
        is_unique, duplicate_reason = ReferralService.is_unique_visit(referral_code, request)

    # Get visitor identifiers
    cookie_id = request.COOKIES.get('ref_visitor_id')
    ip_hash = ReferralService.hash_ip_address(ReferralService.get_client_ip(request))

    # Create visit record
    visit = ReferralVisit.objects.create(
        referral_code=referral_code,
        visitor_cookie_id=uuid.UUID(cookie_id) if cookie_id else None,
        visitor_ip_hash=ip_hash,
        visitor_user=request.user if request.user.is_authenticated else None,
        user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
        referer=request.META.get('HTTP_REFERER', '')[:500],
        landing_page=request.path,
        session_key=request.session.session_key or '',  # Use empty string if None
        is_unique=is_unique,
        duplicate_reason=duplicate_reason if not is_unique else ''
    )

    # Update referral code stats
    referral_code.total_visits += 1
    if is_unique:
        referral_code.unique_visits += 1
    referral_code.save()

    # Check if user earned a reward
    if is_unique:
        reward_granted = ReferralService.check_and_grant_reward(referral_code)
        if reward_granted:
            # Notification will be created by the service
            pass

    # Set tracking cookie (1 year expiry)
    response = redirect('dashboard' if request.user.is_authenticated else 'register')

    if not cookie_id:
        # Generate new cookie ID
        new_cookie_id = str(uuid.uuid4())
        response.set_cookie(
            'ref_visitor_id',
            new_cookie_id,
            max_age=365 * 24 * 60 * 60,  # 1 year
            secure=not settings.DEBUG,  # HTTPS only in production
            httponly=True,  # Not accessible via JavaScript
            samesite='Lax'  # CSRF protection
        )

        # Update visit with new cookie
        visit.visitor_cookie_id = uuid.UUID(new_cookie_id)
        visit.save(update_fields=['visitor_cookie_id'])

    # Store referral code in session for conversion tracking
    request.session['referral_code'] = code

    # Add staff testing message only after successful completion
    if is_staff_testing:
        messages.info(request, "🔧 Staff-modus: Besøk registreres for testing.")

    return response


@login_required
def referral_settings(request):
    """
    User referral dashboard showing their code, stats, and rewards.
    """
    from ..models import ReferralCode, UserTierHistory
    from ..services import ReferralService

    # Get or create referral code for this user
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

    # Get tier history for this user (show referral-related changes)
    tier_history = UserTierHistory.objects.filter(
        user=request.user,
        source='referral'
    ).order_by('-changed_at')[:10]

    context = {
        'referral_code': referral_code,
        'referral_url': referral_url,
        'current_progress': current_progress,
        'needed_for_next': needed_for_next,
        'rewards_earned': referral_code.get_reward_count(),
        'tier_history': tier_history,
    }

    return render(request, 'referrals/settings.html', context)
