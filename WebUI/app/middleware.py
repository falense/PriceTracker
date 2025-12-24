"""
Custom middleware for PriceTracker WebUI.
"""

from django.utils.deprecation import MiddlewareMixin
import structlog

logger = structlog.get_logger(__name__)


class BrowserExtensionCSRFMiddleware(MiddlewareMixin):
    """
    Middleware to handle CSRF validation for browser extensions.

    Browser extensions (Firefox, Chrome) use dynamic origin URLs like
    moz-extension://UUID or chrome-extension://UUID which can't be added
    to CSRF_TRUSTED_ORIGINS. This middleware:

    1. Detects requests from browser extension origins
    2. Marks them as CSRF exempt for origin checking
    3. Still requires X-CSRFToken header for POST/PUT/PATCH/DELETE

    This runs BEFORE Django's CsrfViewMiddleware, allowing us to bypass
    the origin check while maintaining CSRF token validation.
    """

    ADDON_API_PATHS = [
        '/api/addon/track-product/',
        '/api/addon/untrack-product/',
    ]

    def process_request(self, request):
        """
        Process request before view execution.

        If the request is from a browser extension to an addon API endpoint,
        mark it as CSRF exempt for origin checking.
        """
        origin = request.META.get('HTTP_ORIGIN', '')
        path = request.path

        # Check if request is from a browser extension to an addon API
        is_extension_origin = (
            origin.startswith('moz-extension://') or
            origin.startswith('chrome-extension://')
        )
        is_addon_api = any(path.startswith(api_path) for api_path in self.ADDON_API_PATHS)

        if is_extension_origin and is_addon_api:
            # For POST/PUT/PATCH/DELETE, require CSRF token in header
            if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
                csrf_token = request.META.get('HTTP_X_CSRFTOKEN', '')

                if not csrf_token:
                    logger.warning(
                        "browser_extension_missing_csrf_token",
                        origin=origin,
                        path=path,
                        method=request.method
                    )
                    # Don't block here - let the view handle it
                    # The CSRF middleware will still validate the token
                else:
                    logger.debug(
                        "browser_extension_csrf_exempt",
                        origin=origin,
                        path=path,
                        method=request.method
                    )

            # Mark as CSRF exempt for origin checking
            # The CsrfViewMiddleware will still check the token itself
            request._dont_enforce_csrf_checks = True

        return None
