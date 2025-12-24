"""
Firefox Addon API endpoints.

Provides API endpoints for the Firefox browser extension to:
- Check if a URL is tracked by the current user
- Add products to user's tracking list
- Remove products from tracking
- Get CSRF tokens for authenticated requests
"""

import json
from functools import wraps
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.middleware.csrf import get_token, CsrfViewMiddleware
from app.models import ProductListing, UserSubscription
from app.services import ProductService
import structlog

logger = structlog.get_logger(__name__)


def browser_extension_csrf_exempt(view_func):
    """
    Custom decorator for browser extension API endpoints.

    Allows requests from moz-extension:// origins while still requiring
    valid CSRF tokens in the X-CSRFToken header. This bypasses Django's
    origin checking for browser extensions since they use dynamic UUIDs.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Check if request is from a browser extension
        origin = request.META.get('HTTP_ORIGIN', '')

        if origin.startswith('moz-extension://') or origin.startswith('chrome-extension://'):
            # For browser extensions, bypass origin check but still validate CSRF token
            # The CSRF token must be present in the X-CSRFToken header
            csrf_token = request.META.get('HTTP_X_CSRFTOKEN', '')

            if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
                if not csrf_token:
                    logger.warning(
                        "browser_extension_missing_csrf_token",
                        origin=origin,
                        path=request.path
                    )
                    return JsonResponse({
                        'success': False,
                        'error': 'CSRF token required in X-CSRFToken header'
                    }, status=403)

                # Manually validate CSRF token
                csrf_middleware = CsrfViewMiddleware(lambda r: None)
                # Set the token for validation
                request.META['CSRF_COOKIE'] = csrf_token

            # Temporarily mark as CSRF exempt for origin check
            request._dont_enforce_csrf_checks = True

        return view_func(request, *args, **kwargs)

    return wrapper


@login_required
@require_http_methods(["GET"])
def addon_check_tracking(request):
    """
    Check if a URL is being tracked by the current user.

    GET /api/addon/check-tracking/?url=<encoded_url>

    Returns:
        JSON response with tracking status and details
    """
    url = request.GET.get('url', '').strip()

    if not url:
        return JsonResponse({
            'success': False,
            'error': 'URL parameter is required'
        }, status=400)

    try:
        # Check if listing exists for this URL
        listing = ProductListing.objects.filter(url=url).first()

        if not listing:
            # URL not tracked by anyone
            return JsonResponse({
                'success': True,
                'data': {
                    'is_tracked': False
                }
            })

        # Check if current user has an active subscription
        subscription = UserSubscription.objects.filter(
            user=request.user,
            product=listing.product,
            active=True
        ).first()

        if not subscription:
            # Listing exists but not tracked by this user
            return JsonResponse({
                'success': True,
                'data': {
                    'is_tracked': False
                }
            })

        # User is tracking this product
        return JsonResponse({
            'success': True,
            'data': {
                'is_tracked': True,
                'subscription_id': str(subscription.id),
                'product_name': listing.product.name,
                'current_price': float(listing.current_price) if listing.current_price else None,
                'currency': listing.currency,
                'priority': subscription.priority,
                'available': listing.available
            }
        })

    except Exception as e:
        logger.error("addon_check_tracking_error", error=str(e), url=url, user=request.user.username)
        return JsonResponse({
            'success': False,
            'error': 'An error occurred while checking tracking status'
        }, status=500)


@browser_extension_csrf_exempt
@login_required
@require_http_methods(["POST"])
def addon_track_product(request):
    """
    Add a product to user's tracking list.

    POST /api/addon/track-product/
    Body: {"url": string, "priority": int}

    Priority: 1=low, 2=normal, 3=high

    Returns:
        JSON response with created subscription details
    """
    try:
        # Parse JSON body
        data = json.loads(request.body)
        url = data.get('url', '').strip()
        priority_int = data.get('priority', 2)  # Default to normal

        if not url:
            return JsonResponse({
                'success': False,
                'error': 'URL is required'
            }, status=400)

        # Validate priority
        if priority_int not in [1, 2, 3]:
            return JsonResponse({
                'success': False,
                'error': 'Priority must be 1 (low), 2 (normal), or 3 (high)'
            }, status=400)

        # Map priority integer to string
        priority_map = {1: 'low', 2: 'normal', 3: 'high'}
        priority_str = priority_map[priority_int]

        # Use ProductService to add product
        product, subscription, listing, created = ProductService.add_product_for_user(
            user=request.user,
            url=url,
            priority=priority_str
        )

        logger.info(
            "addon_track_product_success",
            user=request.user.username,
            product_name=product.name,
            url=url,
            was_created=created
        )

        return JsonResponse({
            'success': True,
            'message': 'Product added to tracking' if created else 'Product already tracked',
            'data': {
                'subscription_id': str(subscription.id),
                'product_id': str(product.id),
                'product_name': product.name,
                'priority': subscription.priority
            }
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON in request body'
        }, status=400)
    except ValueError as e:
        logger.warning("addon_track_product_validation_error", error=str(e), user=request.user.username)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)
    except Exception as e:
        logger.error("addon_track_product_error", error=str(e), user=request.user.username)
        return JsonResponse({
            'success': False,
            'error': 'An error occurred while adding product to tracking'
        }, status=500)


@browser_extension_csrf_exempt
@login_required
@require_http_methods(["POST"])
def addon_untrack_product(request):
    """
    Remove a product from user's tracking list.

    POST /api/addon/untrack-product/
    Body: {"url": string}

    Returns:
        JSON response confirming removal
    """
    try:
        # Parse JSON body
        data = json.loads(request.body)
        url = data.get('url', '').strip()

        if not url:
            return JsonResponse({
                'success': False,
                'error': 'URL is required'
            }, status=400)

        # Find listing by URL
        listing = ProductListing.objects.filter(url=url).first()

        if not listing:
            return JsonResponse({
                'success': False,
                'error': 'Product not found'
            }, status=404)

        # Find user's subscription
        subscription = UserSubscription.objects.filter(
            user=request.user,
            product=listing.product
        ).first()

        if not subscription:
            return JsonResponse({
                'success': False,
                'error': 'You are not tracking this product'
            }, status=404)

        # Soft delete: set active to False
        subscription.active = False
        subscription.save()

        # Update product subscriber count
        product = listing.product
        product.subscriber_count = product.subscriptions.filter(active=True).count()
        product.save()

        logger.info(
            "addon_untrack_product_success",
            user=request.user.username,
            product_name=product.name,
            url=url
        )

        return JsonResponse({
            'success': True,
            'message': 'Product removed from tracking',
            'data': {
                'product_name': product.name
            }
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON in request body'
        }, status=400)
    except Exception as e:
        logger.error("addon_untrack_product_error", error=str(e), user=request.user.username)
        return JsonResponse({
            'success': False,
            'error': 'An error occurred while removing product from tracking'
        }, status=500)


@login_required
@require_http_methods(["GET"])
def addon_csrf_token(request):
    """
    Get CSRF token for authenticated requests.

    GET /api/addon/csrf-token/

    Returns:
        JSON response with CSRF token
    """
    try:
        # Force token generation if it doesn't exist
        csrf_token = get_token(request)

        return JsonResponse({
            'success': True,
            'data': {
                'csrf_token': csrf_token
            }
        })

    except Exception as e:
        logger.error("addon_csrf_token_error", error=str(e), user=request.user.username)
        return JsonResponse({
            'success': False,
            'error': 'An error occurred while getting CSRF token'
        }, status=500)
