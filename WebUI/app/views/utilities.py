"""
Utility views for PriceTracker WebUI.

Contains miscellaneous utility views like image proxy, feedback submission,
and public information pages.
"""

import logging
import json
import httpx
from urllib.parse import unquote

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods

from ..models import ProductListing

logger = logging.getLogger(__name__)


def proxy_image(request):
    """
    Proxy external images to bypass hotlink protection.

    Usage: /proxy-image/?url=https://example.com/image.jpg
    """
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
        from ..models import ExtractorVersion

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
        from ..models import UserFeedback
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


def pricing_view(request):
    """Pricing tiers page."""
    return render(request, 'pricing.html')


def about_view(request):
    """About us page."""
    return render(request, 'about.html')
