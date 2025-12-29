"""
Authentication views for PriceTracker WebUI.

Handles user login, registration, and logout.
"""

import logging
from datetime import timedelta

from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q

logger = logging.getLogger(__name__)


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

            # Track referral conversion
            referral_code_str = request.session.get('referral_code')
            if referral_code_str:
                try:
                    from ..models import ReferralCode, ReferralVisit

                    referral_code = ReferralCode.objects.get(code=referral_code_str)

                    # Find the visit that led to this registration
                    # Look for recent visit from this session or cookie
                    cookie_id = request.COOKIES.get('ref_visitor_id')
                    recent_visit = ReferralVisit.objects.filter(
                        referral_code=referral_code,
                        converted_user__isnull=True,
                        visited_at__gte=timezone.now() - timedelta(days=30)
                    ).filter(
                        Q(session_key=request.session.session_key) |
                        Q(visitor_cookie_id=cookie_id) if cookie_id else Q()
                    ).first()

                    if recent_visit:
                        recent_visit.converted_user = user
                        recent_visit.converted_at = timezone.now()
                        recent_visit.save()

                        # Update referral code conversion count
                        referral_code.conversions += 1
                        referral_code.save()

                        logger.info(
                            f"Referral conversion tracked: {user.username} via {referral_code.code}",
                            extra={'user_id': user.id, 'referral_code': referral_code.code}
                        )

                    # Clear referral from session
                    del request.session['referral_code']
                except Exception as e:
                    logger.error(f"Failed to track referral conversion: {e}")

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
