"""
Views for PriceTracker WebUI.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods
from .models import Product, Notification


# Authentication views
def login_view(request):
    """User login view."""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f'Welcome back, {username}!')
                return redirect('dashboard')
        else:
            messages.error(request, 'Invalid username or password.')
    else:
        form = AuthenticationForm()

    return render(request, 'auth/login.html', {'form': form})


def register_view(request):
    """User registration view."""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Account created successfully!')
            return redirect('dashboard')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = UserCreationForm()

    return render(request, 'auth/register.html', {'form': form})


def logout_view(request):
    """User logout view."""
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('login')


# Main views
def dashboard(request):
    """Main dashboard view - accessible to everyone."""
    if request.user.is_authenticated:
        products = Product.objects.filter(
            user=request.user,
            active=True
        ).order_by('-last_viewed', '-created_at')[:20]

        notifications = Notification.objects.filter(
            user=request.user,
            read=False
        )[:5]

        unread_count = notifications.count()

        stats = {
            'total_products': Product.objects.filter(user=request.user, active=True).count(),
            'price_drops_24h': 0,  # TODO: Implement
            'total_saved': 0,  # TODO: Implement
            'active_alerts': Product.objects.filter(user=request.user, active=True, target_price__isnull=False).count(),
        }

        context = {
            'products': products,
            'notifications': notifications,
            'unread_count': unread_count,
            'stats': stats,
        }
    else:
        # Non-authenticated users see the search page
        context = {
            'products': [],
            'notifications': [],
            'unread_count': 0,
            'stats': {
                'total_products': 0,
                'price_drops_24h': 0,
                'total_saved': 0,
                'active_alerts': 0,
            },
        }

    return render(request, 'dashboard.html', context)


@login_required
def product_list(request):
    """List all products."""
    products = Product.objects.filter(user=request.user, active=True)

    # TODO: Add filtering and search

    context = {'products': products}
    return render(request, 'product/list.html', context)


@login_required
def product_detail(request, product_id):
    """Product detail page."""
    product = get_object_or_404(Product, id=product_id, user=request.user)

    # Record view
    product.record_view()

    # Get price history
    price_history = product.price_history.all()[:100]

    context = {
        'product': product,
        'price_history': price_history,
    }
    return render(request, 'product/detail.html', context)


def add_product(request):
    """Add new product or preview for non-authenticated users."""
    if request.method == 'GET':
        url = request.GET.get('url', '').strip()

        if not url:
            # Show form
            if not request.user.is_authenticated:
                return redirect('dashboard')
            return render(request, 'product/add_form.html')

        # User submitted a URL to search
        if not request.user.is_authenticated:
            # For non-authenticated users, show preview with prompt to register
            context = {
                'url': url,
                'preview_mode': True,
            }
            return render(request, 'product/preview.html', context)

        # Authenticated user - proceed with adding product
        # TODO: Implement actual product adding
        messages.info(request, 'Product tracking will be implemented soon!')
        return redirect('dashboard')

    # POST - only for authenticated users
    if not request.user.is_authenticated:
        messages.error(request, 'Please log in to track products.')
        return redirect('login')

    url = request.POST.get('url', '').strip()

    if not url:
        messages.error(request, 'Please provide a valid product URL.')
        return redirect('dashboard')

    # Check if product already exists
    existing_product = Product.objects.filter(
        user=request.user,
        url=url,
        active=True
    ).first()

    if existing_product:
        messages.info(request, f'You are already tracking {existing_product.name}')
        return redirect('product_detail', product_id=existing_product.id)

    # Extract domain from URL
    from urllib.parse import urlparse
    parsed_url = urlparse(url)
    domain = parsed_url.netloc

    # Create product
    product = Product.objects.create(
        user=request.user,
        url=url,
        domain=domain,
        name='Loading...',  # Will be updated by fetcher
        active=True,
        priority='normal'
    )

    # TODO: Trigger pattern generation and price fetching
    # This will be implemented when integrating with ExtractorPatternAgent and PriceFetcher

    messages.success(request, 'Product added! We are fetching the details now.')
    return redirect('product_detail', product_id=product.id)


@login_required
@require_http_methods(["DELETE"])
def delete_product(request, product_id):
    """Delete (deactivate) product."""
    product = get_object_or_404(Product, id=product_id, user=request.user)
    product.active = False
    product.save()

    if request.headers.get('HX-Request'):
        return HttpResponse('')
    return redirect('dashboard')


@login_required
@require_http_methods(["POST"])
def update_product_settings(request, product_id):
    """Update product settings."""
    # TODO: Implement
    return HttpResponse('Not implemented yet')


@login_required
@require_http_methods(["POST"])
def refresh_price(request, product_id):
    """Trigger immediate price refresh."""
    # TODO: Implement
    return JsonResponse({'status': 'queued'})


# HTMX endpoints
@require_http_methods(["POST"])
def search_product(request):
    """Dynamic search endpoint for products."""
    query = request.POST.get('query', '').strip()

    # Empty query - clear results
    if not query:
        return HttpResponse('')

    # Check if query is a URL
    is_url = query.startswith(('http://', 'https://'))

    if is_url:
        # Query is a URL - show confirmation dialog
        if not request.user.is_authenticated:
            # Guest user - prompt to register
            context = {'url': query}
            return render(request, 'search/guest_prompt.html', context)

        # Check if product already exists
        existing_product = Product.objects.filter(
            user=request.user,
            url=query,
            active=True
        ).first()

        if existing_product:
            # Product already tracked
            context = {'product': existing_product}
            return render(request, 'search/already_tracked.html', context)

        # Show URL confirmation
        context = {'url': query}
        return render(request, 'search/url_confirm.html', context)

    else:
        # Query is a product name - search for existing products
        if not request.user.is_authenticated:
            # Guest user - prompt to register
            context = {'query': query}
            return render(request, 'search/guest_prompt.html', context)

        # Search existing products
        products = Product.objects.filter(
            user=request.user,
            active=True,
            name__icontains=query
        ).order_by('-last_viewed')[:5]

        if products.exists():
            # Found matching products
            context = {'products': products, 'query': query}
            return render(request, 'search/results_found.html', context)
        else:
            # No products found - prompt for URL
            context = {'query': query}
            return render(request, 'search/name_not_found.html', context)


@login_required
def search_autocomplete(request):
    """Search autocomplete endpoint."""
    query = request.GET.get('q', '').strip()

    if len(query) < 3:
        return HttpResponse('')

    products = Product.objects.filter(
        user=request.user,
        active=True,
        name__icontains=query
    ).order_by('-last_viewed')[:5]

    return render(request, 'search/autocomplete.html', {'products': products})


@login_required
def price_history_chart(request, product_id):
    """Price history chart data."""
    # TODO: Implement
    return HttpResponse('Chart data')


@login_required
def product_status(request, product_id):
    """Get product status (for polling during add)."""
    # TODO: Implement
    return HttpResponse('Status')


# Notifications
@login_required
def notifications_list(request):
    """List user notifications."""
    notifications = Notification.objects.filter(
        user=request.user
    ).order_by('-created_at')[:50]

    unread_count = Notification.objects.filter(user=request.user, read=False).count()

    if request.headers.get('HX-Request'):
        context = {'notifications': notifications}
        return render(request, 'partials/notification_list.html', context)

    context = {
        'notifications': notifications,
        'unread_count': unread_count,
    }
    return render(request, 'notifications.html', context)


@login_required
@require_http_methods(["POST"])
def mark_notifications_read(request):
    """Mark all notifications as read."""
    Notification.objects.filter(user=request.user, read=False).update(read=True)
    return redirect('notifications_list')


# Admin views
@login_required
def admin_dashboard(request):
    """Admin dashboard."""
    if not request.user.is_staff:
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    # TODO: Implement
    return render(request, 'admin/dashboard.html')


@login_required
def patterns_status(request):
    """Pattern health status."""
    if not request.user.is_staff:
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    # TODO: Implement
    return render(request, 'admin/patterns.html')


@login_required
def admin_flags_list(request):
    """List admin flags."""
    if not request.user.is_staff:
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    # TODO: Implement
    return render(request, 'admin/flags.html')


@login_required
@require_http_methods(["POST"])
def resolve_admin_flag(request, flag_id):
    """Resolve an admin flag."""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Access denied'}, status=403)

    # TODO: Implement
    return JsonResponse({'status': 'resolved'})


# Settings
@login_required
def user_settings(request):
    """User settings page."""
    # TODO: Implement
    return render(request, 'settings.html')
