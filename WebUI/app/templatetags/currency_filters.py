"""
Django template filters for currency formatting and JSON serialization.
"""

import json
from django import template
from django.utils.safestring import mark_safe
from app.utils.currency import format_price, get_currency_from_domain

register = template.Library()


@register.filter(name="format_currency")
def format_currency(price, currency_or_domain):
    """
    Format price with appropriate currency symbol.

    Intelligently detects whether the argument is a currency code or domain.

    Args:
        price: Price value
        currency_or_domain: Either:
            - Currency code (e.g., 'NOK', 'USD') - PREFERRED for accuracy
            - Domain (e.g., 'oda.com') - fallback for backward compatibility

    Usage in templates:
        {{ listing.current_price|format_currency:listing.currency }}  # Preferred
        {{ listing.current_price|format_currency:listing.store.domain }}  # Fallback

    Examples:
        {{ 499.00|format_currency:"NOK" }}  → "499.00 kr"
        {{ 499.00|format_currency:"USD" }}  → "$499.00"
        {{ 499.00|format_currency:"oda.com" }}  → "$499.00" (domain fallback)
    """
    if not currency_or_domain:
        return format_price(price)

    # Check if it's a currency code (2-4 letter uppercase, no dots)
    # Currency codes: NOK, USD, EUR, GBP, etc.
    if (
        isinstance(currency_or_domain, str)
        and 2 <= len(currency_or_domain) <= 4
        and currency_or_domain.isupper()
        and "." not in currency_or_domain
    ):
        # It's a currency code - use it directly (preferred)
        return format_price(price, currency_code=currency_or_domain)
    else:
        # It's a domain - use domain-based detection (fallback)
        return format_price(price, domain=currency_or_domain)


@register.filter(name="currency_symbol")
def currency_symbol(domain):
    """
    Get currency symbol for a domain.

    Usage in template:
        {{ product.domain|currency_symbol }}
    """
    _, symbol = get_currency_from_domain(domain)
    return symbol


@register.filter(name="to_json")
def to_json(value):
    """
    Convert a Python object to JSON string.

    Usage in template:
        {{ log.context|to_json }}
    """
    if value is None:
        return "null"
    try:
        return mark_safe(json.dumps(value, default=str, ensure_ascii=False))
    except (TypeError, ValueError):
        return "{}"


@register.filter(name="truncate_path")
def truncate_path(url, max_length=50):
    """
    Truncate URL to show only path, with intelligent truncation.

    Usage in template:
        {{ log.context.url|truncate_path }}
        {{ log.context.url|truncate_path:40 }}
    """
    if not url:
        return ""
    try:
        from urllib.parse import urlparse

        parsed = urlparse(str(url))
        path = parsed.path or url

        if len(path) > max_length:
            # Keep start and end, truncate middle
            keep_each = (max_length - 3) // 2
            return path[:keep_each] + "..." + path[-keep_each:]
        return path
    except Exception:
        # Fallback: simple string truncation
        url_str = str(url)
        if len(url_str) > max_length:
            return url_str[: max_length - 3] + "..."
        return url_str


@register.filter(name="context_value")
def context_value(context_dict, key):
    """
    Safely get a value from context dict.

    Usage in template:
        {{ log.context|context_value:"url" }}
    """
    if not context_dict or not isinstance(context_dict, dict):
        return None
    return context_dict.get(key)
